"""First-run window (ST-1): long set-up jobs run on a worker thread while a small window shows progress.

Why: building the word list (a 3 GB download, parsing, compound detection, shuffling) can take
minutes, and used to report only to a console. Now the work reports through a `log(text)`
callback; this module turns those lines into a window.

    value = run_with_progress(root, work)       # work(log) -> value, runs off the UI thread

Behaviour worth knowing
    * The window only appears if the work takes longer than DELAY_MS, so normal launches (nothing
      to build) never flash it.
    * Until the work reports in, the window shows "Initializing..." with the bar at 1%. The bar is
      always present; with no known percentage it sweeps instead of filling, and the detail line
      is never blank.
    * Lines starting with a space are details ("  downloaded 1.20 GB (41%)"); other lines name the
      stage ("Reading entries ..."). A "(NN%)" in a detail line drives the progress bar. Stages with
      no percentage show a sweeping bar and the elapsed time. Bars with a percentage also show an
      estimated time left (EtaTracker): "estimating time left..." at first, then e.g. "about 6 min left".
      Any future progress bar should use EtaTracker and format_eta the same way.
    * A job can name its main steps up front (log(constants.plan_line([...]))): then "Step 2 of 5" shows in
      the bottom right corner as each stage line starting with one of them comes in (step_of). The plan line
      is never shown or printed.
    * Closing the window is safe: downloads resume from their .part file and parsing restarts from
      the saved stage. It raises SystemExit; run the program again to continue.
    * Exceptions (including SystemExit with a message) raised by the work are re-raised in the
      caller, so the caller's error handling is unchanged.
    * If the window itself cannot be drawn, set-up still runs to completion (and the messages still
      go to the console, when there is one).
    * The work thread must not touch tkinter. It may use the Store (opened with
      check_same_thread=False) as long as the UI thread leaves it alone until the work is done.
"""
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

import deps
from constants import parse_plan
from errors import ask_choices, ask_yes_no
from fonts import font
from problems import STOPPED_MESSAGE, SetupError, ensure_streams, open_log
from sizing import ui_factor, usable_area
from theme import PALETTE

DELAY_MS = 400     # show the window only if the work is still running after this long
POLL_MS = 100      # how often the UI thread looks for new messages
_PERCENT = re.compile(r"\((\d{1,3})%\)")

BAR_FLOOR = 3      # minimum drawn fill, in percent, once the percentage is known (see StartupWindow.show)
INITIAL_STAGE = "Initializing..."   # shown (with the bar at 1%) until the work reports its first stage

INTRO = ("This only happens once. The first time it can take several minutes. "
         "You can close this window at any time; next time it picks up where it left off.")


def parse_progress(line):
    """Percent (0..100) found in a log line like '  downloaded 1.20 GB (41%)', else None."""
    m = _PERCENT.search(line)
    return min(100, int(m.group(1))) if m else None


def format_eta(seconds):
    """Friendly time-left text: 'a few seconds left', 'about 40 sec left', 'about 6 min left', 'about 1 hr 5 min left'."""
    s = max(0.0, seconds)
    if s < 10:
        return "a few seconds left"
    if s < 60:
        return f"about {int(round(s / 5.0)) * 5} sec left"
    minutes = int(s / 60.0 + 0.5)
    if minutes < 60:
        return f"about {max(minutes, 1)} min left"
    hours, minutes = divmod(minutes, 60)
    return f"about {hours} hr {minutes} min left" if minutes else f"about {hours} hr left"


class EtaTracker:
    """Estimates the time left for one progress bar from its recent speed. Pure: times are passed in.

    Feed it every percentage reading with add(percent, now); ask remaining(now) for seconds left, or
    None while it cannot tell yet. How it stays honest:
      * the first reading of a stage is ignored: it is usually a stand-in ("opening the file (1%)")
        or, when a download resumes, a big jump from the stand-in, and would give a wild speed;
      * speed comes from the last WINDOW seconds only, so it follows slowdowns and speed-ups;
      * it needs two readings at least MIN_SPAN seconds apart that really moved forward;
      * if the bar stops moving for much longer than its usual gap it goes back to "estimating"
        instead of counting down to zero while nothing happens;
      * between readings the estimate counts down in real time.
    Call reset() when a new stage starts.
    """
    WINDOW = 30.0     # seconds of history used for the speed
    MIN_SPAN = 2.0    # seconds between the readings used

    def __init__(self):
        self.reset()

    def reset(self):
        self.samples = []        # (time, percent), strictly increasing in percent
        self._seen_first = False

    def add(self, percent, now):
        if percent is None:
            return
        if not self._seen_first:
            self._seen_first = True
            return
        if self.samples and percent <= self.samples[-1][1]:
            return
        self.samples.append((now, percent))
        while len(self.samples) > 2 and now - self.samples[0][0] > self.WINDOW:
            self.samples.pop(0)

    def remaining(self, now):
        """Seconds left, or None if unknown (not enough readings yet, or the bar has stalled)."""
        if len(self.samples) < 2:
            return None
        (t0, p0), (t1, p1) = self.samples[0], self.samples[-1]
        if t1 - t0 < self.MIN_SPAN or p1 <= p0:
            return None
        gap = (t1 - t0) / (len(self.samples) - 1)
        if now - t1 > 3 * gap + 5:
            return None
        rate = (p1 - p0) / (t1 - t0)
        return max(0.0, (100.0 - p1) / rate - (now - t1))


def step_of(plan, stage, current):
    """(i, n) for the plan step `stage` starts (a plan line's names are the starts of stage lines), else
    `current` unchanged (a stage line that is not a main step, like a retry note). None for a one-step plan."""
    if len(plan) < 2:
        return None
    for i, name in enumerate(plan, 1):
        if stage.startswith(name):
            return (i, len(plan))
    return current


def format_elapsed(seconds):
    """'0:07' or '12:03' style elapsed time."""
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


class StartupWindow:
    """The progress window itself: a stage line, a detail line, a bar (when a percentage is known)."""

    def __init__(self, root, title, on_close, intro=INTRO):
        self.win = tk.Toplevel(root)
        self.win.title(title)
        self.win.resizable(False, False)
        # Text width: grows with the screen's dpi, and with the actual font (measured), whichever is wider.
        wrap = max(int(420 * ui_factor(root)), font("label").measure("n") * 38)
        self.win.configure(bg=PALETTE["bg"])
        self.win.protocol("WM_DELETE_WINDOW", on_close)
        box = ttk.Frame(self.win, padding=(28, 24))
        box.pack(fill="both", expand=True)
        ttk.Label(box, text=title, font=font("head")).pack(anchor="w")
        self.stage = ttk.Label(box, text="Starting...", font=font("label"), wraplength=wrap, justify="left")
        self.stage.pack(anchor="w", pady=(14, 2))
        self.detail = ttk.Label(box, text="", foreground=PALETTE["muted"], wraplength=wrap, justify="left")
        self.detail.pack(anchor="w")
        # The bar is always there (no jumping layout): determinate when a percentage is known,
        # otherwise a sweep that shows the work is alive.
        self.bar = ttk.Progressbar(box, maximum=100, length=wrap, mode="determinate")
        self.bar.pack(anchor="w", pady=(10, 0))
        self._sweeping = False
        self.elapsed = ttk.Label(box, text="", foreground=PALETTE["muted"])
        self.elapsed.pack(anchor="w", pady=(10, 0))
        ttk.Label(box, text=intro, foreground=PALETTE["muted"], wraplength=wrap, justify="left"
                  ).pack(anchor="w", pady=(14, 0))
        # "Step 2 of 4" in the bottom right corner, when the job said what its main steps are (plan_line)
        self.step = ttk.Label(box, text="", foreground=PALETTE["muted"])
        self.step.pack(anchor="e", pady=(8, 0))
        self.win.update_idletasks()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        ax, ay, aw, ah = usable_area(root)        # the monitor the pointer is on
        self.win.geometry(f"+{max(ax + (aw - w) // 2, 0)}+{max(ay + (ah - h) // 3, 0)}")

    def show(self, stage, detail, percent, elapsed, eta=None, step=None):
        """Update the labels and bar. `percent` None means unknown: the bar sweeps instead of filling.

        `eta` is the time-left text (format_eta); with a known percentage but no `eta` yet the line
        says it is estimating. `step` = (i, n) shows "Step i of n" in the corner (nothing for None).
        """
        self.step.config(text=f"Step {step[0]} of {step[1]}" if step else "")
        self.stage.config(text=stage or "Starting...")
        self.detail.config(text=detail or "Getting started...")   # never blank
        if percent is None:
            if not self._sweeping:
                self.bar.config(mode="indeterminate")
                self.bar.start(15)
                self._sweeping = True
        else:
            if self._sweeping:
                self.bar.stop()
                self.bar.config(mode="determinate")
                self._sweeping = False
            # A very small fill (1%) would be only a few pixels wide and look empty, so the drawn bar
            # never shows less than BAR_FLOOR; the text next to it still reports the real figure.
            self.bar["value"] = max(percent, BAR_FLOOR)
        text = f"Working for {format_elapsed(elapsed)}"
        if percent is not None:      # only a bar with a real percentage can have a time left
            text += f"   -   {eta or 'estimating time left...'}"
        self.elapsed.config(text=text)

    def close(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass


def run_with_progress(root, work, title="Setting up your word list", delay_ms=DELAY_MS,
                      initial_stage=INITIAL_STAGE, intro=INTRO):
    """Run `work(log)` on a worker thread and return its result (see the module docstring).

    `root` must exist (it may be withdrawn). Blocks, running the Tk event loop, until the work
    finishes or the progress window is closed (which raises SystemExit). Until the work reports
    its first stage the window shows `initial_stage` with the bar at 1%, so it is never empty.
    """
    messages = queue.Queue()
    outcome = {}

    def log(text):
        text = str(text)
        if sys.stdout is not None and parse_plan(text) is None:   # no console when started without one
            print(text)
        messages.put(text)

    def runner():
        try:
            outcome["value"] = work(log)
        except BaseException as exc:         # SystemExit too: re-raised in the caller below
            outcome["error"] = exc
        finally:
            outcome["done"] = True

    eta = EtaTracker()
    state = {"stage": initial_stage, "detail": "", "percent": 1, "win": None, "closed": False, "ui_failed": False,
             "stop": False, "plan": [], "step": None}
    t0 = time.time()

    def on_close():
        state["closed"] = True
        root.quit()

    def poll():
        if state["stop"]:        # this call finished; a leftover timer must not end a later loop
            return
        while True:
            try:
                line = messages.get_nowait()
            except queue.Empty:
                break
            plan = parse_plan(line)
            if plan is not None:
                state["plan"], state["step"] = plan, None
                continue
            if line.startswith((" ", "\t")):
                state["detail"] = line.strip()
                pct = parse_progress(line)
                if pct is not None:
                    state["percent"] = pct
                    eta.add(pct, time.time())
            elif line.strip():
                state["stage"], state["detail"], state["percent"] = line.strip(), "", None
                eta.reset()
                state["step"] = step_of(state["plan"], line.strip(), state["step"])
        if outcome.get("done") and messages.empty():
            root.quit()
            return
        elapsed = time.time() - t0
        # The window is a courtesy: if drawing it fails for any reason, carry on without it. An
        # error here must never stop this loop, or the program would hang with nothing on screen.
        if not state["ui_failed"]:
            try:
                if state["win"] is None and elapsed * 1000 >= delay_ms:
                    state["win"] = StartupWindow(root, title, on_close, intro)
                if state["win"] is not None:
                    left = eta.remaining(time.time())
                    state["win"].show(state["stage"], state["detail"], state["percent"], elapsed,
                                      format_eta(left) if left is not None else None, state["step"])
            except Exception as exc:
                state["ui_failed"] = True
                if state["win"] is not None:
                    state["win"].close()
                    state["win"] = None
                if sys.stderr is not None:
                    print(f"(progress window unavailable: {exc!r}; set-up continues)", file=sys.stderr)
        root.after(POLL_MS, poll)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    root.after(20, poll)
    root.mainloop()
    state["stop"] = True
    if state["win"] is not None:
        state["win"].close()
    if state["closed"] and not outcome.get("done"):
        raise SystemExit(STOPPED_MESSAGE)
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")


# --------------------------------------------------------------------------
# Windows: no console window behind the app, and errors that are not lost
# --------------------------------------------------------------------------
def detach_console(log_path, kernel32=None):
    """Windows: drop the console window this process was started from, sending print() output to a log.

    Without this, running `python tierlist.py` leaves a command window open behind the app, and
    closing it kills the app. Returns True if a console was detached. Does nothing (False) on other
    systems, when started without a console already, or when the output is being redirected on
    purpose. `kernel32` is only for tests.
    """
    if kernel32 is None:
        if os.name != "nt":
            return False
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.GetConsoleWindow.restype = ctypes.c_void_p
        except (ImportError, AttributeError, OSError):
            return False
    try:
        has_console = bool(kernel32.GetConsoleWindow())
    except Exception:
        return False
    if not has_console:
        # Started without a console (pythonw): the standard streams may be None, which breaks print().
        ensure_streams(log_path)
        return False
    if sys.stdout is not None and not sys.stdout.isatty():
        return False                      # output goes to a file or pipe on purpose: leave it alone
    sys.stdout = sys.stderr = open_log(log_path)
    kernel32.FreeConsole()
    return True


# --------------------------------------------------------------------------
# Missing packages: ask, then install
# --------------------------------------------------------------------------
_VENV_ADVICE = ("Your system's Python does not allow installing packages into it directly. Make a "
                "virtual environment once, then run the program with it:\n\n"
                "    python3 -m venv .venv\n    .venv/bin/pip install -r requirements.txt\n"
                "    .venv/bin/python tierlist.py\n\n(On Windows: .venv\\Scripts\\python.)")


def ensure_packages(root, required, optional=(), declined=(), on_decline=None, installer=None,
                    restart=None, home=None, system_installer=None):
    """Make sure the packages in `required` (and, if wanted, `optional`) can be imported (ST-4, stage 2).

    Names are import names (see deps.PIP_NAMES). Does nothing unless something is missing. Then one
    dialog lists each missing package as its own tick box, saying what it is for and whether it is needed
    or optional (required ones marked with a red asterisk; all ticked to start with); "Install selected" runs `pip install` for the ticked ones behind
    the usual progress window and checks again, without a restart.

    * Optional packages already declined (`declined`) are not offered again; an optional one left unticked
      (or "Not now") is passed to `on_decline(names)` so the caller can remember it.
    * Returns True when every required package is available, False if a required one was left out (the
      program carries on; whatever needs it explains itself later).
    * If this Python refuses installs (externally-managed), it offers to make a private environment in
      <home>/.venv, installs there, and calls restart(python) to start the program again with it. Without
      `restart` / `home` it raises SetupError with the manual steps instead.
    * A failed install of a required package raises SetupError with what to do instead; a failed install of
      only optional ones is reported on stderr and the program carries on.
    Packaged builds skip all of this.
    """
    need = deps.missing(required)
    extra = [n for n in deps.missing(optional) if n not in declined and n not in need]
    gone = need + extra
    if not gone or getattr(sys, "frozen", False):
        return not need
    cmd = "pip install " + " ".join(deps.PIP_NAMES.get(n, n) for n in gone)
    if not deps.pip_available():
        if not need:
            return True                                   # only optional things missing: not worth an error
        if not _get_pip(root, need, system_installer):
            raise SetupError(f"A required package is missing ({', '.join(need)}) and pip is not available "
                             f"to install it.\n\nInstall pip, then run:\n    {cmd}")
    headline = ("Some packages are needed" if len(gone) > 1 else "A package is needed") if need \
        else ("Optional packages are available" if len(extra) > 1 else "An optional package is available")
    def label(n):                                         # the name itself is the link to its page (UI-30)
        kind = "required" if n in need else "optional"
        size = deps.SIZE.get(n)
        return f" ({kind}, about {size} MB)" if size else f" ({kind})"
    choices = [(n, label(n), deps.PURPOSE.get(n, ""), True, n in need, (n, deps.HOMEPAGE.get(n)))
               for n in gone]
    chosen = ask_choices(
        "Word Tier List", headline,
        "Tick what to install. It uses pip, needs an internet connection and takes a minute or so.",
        choices, yes="Install selected", no="Not now", parent=root)
    chosen = [n for n in gone if chosen and n in chosen]
    left_out = [n for n in extra if n not in chosen]
    if left_out and on_decline:
        on_decline(left_out)
    if not chosen:
        return not need
    what = ", ".join(chosen)
    ok, tail = run_with_progress(
        root, lambda log: (installer or deps.install)(chosen, log), title="Installing packages",
        initial_stage=f"Installing {what}...",
        intro="This only happens once. You can close this window to stop; the program will ask again next time.")
    managed = "externally-managed-environment" in tail
    if not ok and managed and _private_env(root, chosen, need, restart, home, system_installer):
        return True                       # restarted in the private environment (a real restart never returns)
    still = deps.missing(chosen)
    if not ok or still:
        if set(need) & set(still):
            raise SetupError(f"Could not install {what}.\n\n{tail}\n\nTry running this yourself, then start "
                             f"the program again:\n    pip install {' '.join(deps.PIP_NAMES.get(n, n) for n in chosen)}")
        if still and sys.stderr is not None:
            print(f"Could not install {', '.join(still)} (optional); carrying on without it.", file=sys.stderr)
    return not deps.missing(need)


def offer_system_install(root, what, why, installer=None):
    """Something the program needs comes from the system, not from pip (deps.SYSTEM_PACKAGES: pip itself, Python's
    venv module, Python): ask to install it with the system's package manager (asked for: offered, not only told),
    then do it behind the progress window. True once the command worked; False if there is no command we know,
    or the answer was no. `installer(cmd, log)`: tests."""
    cmd = deps.system_install_command(what, window=True)
    if not cmd:
        return False
    name = deps.SYSTEM_NAMES[what]
    if not ask_yes_no("Word Tier List", f"Install {name}?",
                      f"{why}\n\nIt can be installed with:\n    {' '.join(cmd)}\n\nYour system may ask for your "
                      "password.", yes="Install it", no="Not now", parent=root, wrap_chars=56):
        return False
    try:
        return bool(run_with_progress(root, lambda log: (installer or deps.run_system_install)(cmd, log),
                                      title=f"Installing {name}", initial_stage="Installing...",
                                      intro="Your system may ask for your password."))
    except SystemExit:                                    # (the progress window was closed: stopped)
        return False


def _get_pip(root, need, installer=None):
    """pip is missing: Python's own ensurepip first (nothing to ask), then the system's package. True once pip
    works."""
    if run_with_progress(root, lambda log: (log("Setting up pip..."), deps.ensure_pip())[1], title="Setting up pip",
                         initial_stage="Setting up pip..."):
        return True
    return offer_system_install(root, "pip", f"Installing {', '.join(need)} needs pip, Python's package "
                                "installer, which this Python does not have.", installer) and deps.pip_available()


def _private_env(root, names, need, restart, home, installer=None):
    """This Python refuses pip installs: offer a private environment next to the program, install there and
    restart with it (True). Returns False when the user says no to an optional-only install."""
    if restart is None or home is None:
        raise SetupError(_VENV_ADVICE)
    venv = os.path.join(home, ".venv")
    if not ask_yes_no("Word Tier List", "Make a private environment for the program?",
                      f"This Python does not allow installing packages into it directly. The program can make "
                      f"its own environment in\n    {venv}\ninstall {', '.join(names)} there, and start again "
                      "with it. Later starts use it automatically.",
                      yes="Make it", no="Not now", parent=root):
        if need:
            raise SetupError(_VENV_ADVICE)
        return False
    def make():
        return run_with_progress(root, lambda log: deps.make_private_env(home, names, log),
                                 title="Making a private environment", initial_stage="Making it...")
    ok, tail, vpy = make()
    if not ok and not os.path.exists(vpy) and offer_system_install(
            root, "venv", "Making the private environment needs Python's venv module, which this system "
            "keeps in a package of its own.", installer):
        ok, tail, vpy = make()                            # (once more, now that venv is there)
    if not ok:
        raise SetupError(f"Could not set up the private environment.\n\n{tail}")
    restart(vpy)
    return True
