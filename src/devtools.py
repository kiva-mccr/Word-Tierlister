"""Developer tools from the window (DT-1..DT-7): what the bubbles at a dialog's top right start while Settings >
Developer tools is on. How words are dealt has one split bubble, Review words | Tune & reroll; Source & Updates has
Log and Crash test (and Nightly, which is sources.py's own).

- Review words: the review of rude meanings (OB-9, App.open_review); with no review file yet, the first review words
  are made first (tools/measure_rudeness.py sample).
- Tune & reroll: the tuner's window (tools/tune_rudeness.py, OB-10), then new review words (measure_rudeness.py
  next) once it closes after tuning to the end. Every AUTO_TUNE new answers it starts by itself, hidden (DT-6).
- A running tool's ring (DT-3) reads progress(); its red cross (DT-7) calls stop().

The tools run from the source folder (root) as programs of their own, each in a process group of its own, so stopping
one stops what it started. A worker thread reads their output into a Job; the window waits on it with background.Task
and Repeat (a worker thread never touches Tk).
"""
import os
import re
import signal
import subprocess
import sys
import threading

from tkinter import filedialog

import standalone
from background import Repeat, Task
from constants import LOG_FILE, REVIEW_FILE, review_answers_path
from errors import ask_yes_no, show_message
from filepicker import browse, use_themed
from review import read_answers
from saves import is_frozen

# a tool started by a developer bubble gets a process group of its own, so stopping it stops what it started too
OWN_GROUP = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}


def stop_tree(proc, run=subprocess.run):
    """Stop a tool a developer bubble started, and the processes it started (the tuner's workers); never waits
    (whoever watches it sees it end)."""
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            threading.Thread(target=run, args=(["taskkill", "/F", "/T", "/PID", str(proc.pid)],),
                             kwargs={"capture_output": True, "timeout": 30}, daemon=True).start()
        else:
            os.killpg(proc.pid, signal.SIGTERM)
    except (OSError, AttributeError, TypeError):
        try:
            proc.terminate()
        except OSError:
            pass


class Job:
    """A tool running in the background, shared by the window and the worker thread that reads it. Each field is
    written by one side only: the worker sets proc, step, note, frac, over, tuned, hidden and done; the window
    sets stop, said and run."""

    def __init__(self, proc=None, then=None, path=None, partial=(), note=None):
        self.proc = proc          # the running process (the tuner's, or the command now running)
        self.step = None          # which of the commands runs now (run_tools)
        self.note = note          # its last line, for the bubble's hover note
        self.stop = False         # asked to stop (the bubble's red cross)
        self.done = None          # (exit code, last line) once the commands have run (run_tools)
        self.then = then          # after the review words: "open" (the review opens on them) or "reroll"
        self.path = path          # the review file being made
        self.partial = list(partial)    # what each command leaves half written when it is stopped
        self.frac = 0.0           # the tuner: how far through its rounds
        self.over = False         # the tuner: done (tuned to the end, or closed)
        self.tuned = False        # the tuner: tuned to the end (the reroll follows once it closes)
        self.hidden = False       # the tuner: its window is hidden (its close box while tuning)
        self.said = False         # the tuner: its "done" toast was shown
        self.run = None           # the reroll's runner (tests)

    def running(self):
        return self.proc is not None and self.proc.poll() is None


def run_tools(cmds, cwd, on_line=None, job=None):
    """Run each command in turn (a worker thread: no Tk here): (the exit code, the last line it printed), stopping
    at the first that fails. `on_line(step, steps, line)`: each line as it is printed (the bubble's hover note).
    `job`: the running one is kept there (proc, step), and none starts once it says stop."""
    code, last = 0, ""
    job = job if job is not None else Job()
    for i, cmd in enumerate(cmds):
        if job.stop:
            return 1, "stopped"
        p = subprocess.Popen(cmd, cwd=cwd, env=standalone.clean_env(), stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, bufsize=1, **OWN_GROUP)
        job.proc, job.step = p, i
        if job.stop:                      # (stopped while it was starting)
            stop_tree(p)
        last = ""
        for line in p.stdout:
            if line.strip():
                last = line.strip()
                if on_line:
                    on_line(i + 1, len(cmds), last)
        code = p.wait()
        if code:
            break
    return code, last


def follow_tuner(proc, job):
    """Read the tuner's printed rounds into `job` (a worker thread: no Tk here): over once it says it is done
    (its window may stay open for Keep; what it prints later is still read, so its pipe never fills) or closes."""
    try:
        for line in proc.stdout:
            m = re.match(r"Round (\d+) of up to (\d+)", line.strip())
            if m and not job.over:
                job.frac = int(m.group(1)) / max(1, int(m.group(2)))
                job.note = f"Round {m.group(1)} of up to {m.group(2)}"
            elif line.startswith("Done"):
                job.over = job.tuned = True       # (tuned to the end: the reroll follows once it closes)
            elif line.startswith("Hidden"):       # (its close box while tuning: only hidden; show_tuner brings it back)
                job.hidden = True
    except (OSError, ValueError):
        pass
    job.over = True


class DevTools:
    """The developer tools of one main window (App.devtools). `tuner`: the tuner's Job while its process runs;
    `tool`: the review words' Job while they are being made."""

    AUTO_TUNE = 50                        # new answers between two automatic Tune & rerolls (DT-6, asked for)

    def __init__(self, app):
        self.app = app
        self.root = standalone.ROOT       # (the source folder whose tools/ the bubbles run; tests point it elsewhere)
        self.tuner = None
        self.tool = None

    def _flash(self, *a, **kw):
        self.app.flash(*a, **kw)

    # ---- the review file and the review ------------------------------------------------------------------------
    def review_file(self):
        """The review file to use: the last one opened, else REVIEW_FILE next to the save (it may not exist)."""
        store = self.app.store
        last = store.get_meta("review_file")
        if last and os.path.exists(last):
            return last
        return os.path.join(os.path.dirname(os.path.abspath(store.path)), REVIEW_FILE)

    def pick_review_file(self, parent, ask=None):
        """The review file, or None: when there is none at review_file(), ask for one (it is made by
        tools/measure_rudeness.py sample). `ask(start) -> path or None`: how to ask (tests)."""
        path = self.review_file()
        if os.path.exists(path):
            return path
        start = os.path.dirname(path)
        if ask is None:
            if use_themed(self.app.root):
                ask = lambda d: browse(parent, "Open a review file", d, mode="file", exts=(".jsonl",),
                                       animator=self.app.anim, note="No rude_review.jsonl next to the save: pick one "
                                       "made by tools/measure_rudeness.py sample.")
            else:
                ask = lambda d: filedialog.askopenfilename(parent=parent, initialdir=d, title="Open a review file",
                                                           filetypes=[("Review files", "*.jsonl"), ("All", "*")])
        path = ask(start)
        if not path:
            return None
        self.app.store.set_meta("review_file", os.path.abspath(path))
        return path

    def review_rude(self, dlg=None, ask=None):
        """Close the dialog (it holds the input), then open the review (App.open_review), asking for the file first
        when there is none next to the save."""
        path = self.pick_review_file(dlg.win if dlg else self.app.root, ask)
        if not path:
            return None
        if dlg is not None:
            dlg.close()
        return self.app.open_review(path)

    def _tool(self, name, parent):
        """tools/<name> in the source folder, or None after saying the bubble works only from the source (a built
        program carries no tools to run)."""
        path = os.path.join(self.root, "tools", name)
        if not is_frozen() and os.path.exists(path):
            return path
        show_message("Developer tools", "Only from the source", f"tools/{name} runs from the source folder: start "
                     "Word Tierlister with python tierlist.py (File > Source & Updates can unpack the source).",
                     parent=parent)
        return None

    def _entries(self):
        return os.path.join(self.root, "rudeness_entries.jsonl")

    # ---- the Review words bubble's ring and stop button -------------------------------------------------------
    def progress(self, name):
        """How a developer tool that keeps running is doing, for its bubble's ring: None (not running) or
        (fraction or None, the hover note, the split bubble's right half or None). "review": the Review words
        bubble: Tune & reroll's two steps (the tuner's rounds, then Make review words: no fraction, it cannot tell
        how far), or the first review words being made."""
        tuner = self.tuner
        if tuner is not None and tuner.running():
            if tuner.over:                        # (done: waiting for Keep or Discard in its window)
                return 1.0, "Step 1 of 2: tuned; Keep or Discard in the tuner's window", "Keep or Discard · step 1 of 2"
            note = tuner.note or "The tuner is reading Wiktionary's entries"
            if tuner.hidden:
                note += "  ·  click Tune & reroll to bring its window back"
            return tuner.frac or 0.0, "Step 1 of 2: " + note, "Tuning · step 1 of 2"
        job = self.tool
        if job is None:
            return None
        note = job.note or "Making review words"
        if job.then == "reroll":
            return None, "Step 2 of 2: " + note, "New words · step 2 of 2"
        return None, note, None

    def stop_note(self):
        """The Review words bubble's hover note over its ring (the stop button): what stopping does now."""
        if self.tuner is not None and self.tuner.running():
            return "Stop: the tuner closes and its numbers are thrown away; no new review words are made"
        if self.tool is not None and self.tool.then == "open":
            return "Stop: no review words are made"
        return "Stop: the review words stay as they were"

    def stop(self):
        """The Review words bubble's stop button (asked for): stop the tuner, or the review words being made (its
        half-written file is removed once it has ended: _watch_tool). Returns what it stopped: "tuner", "tools" or
        None."""
        tuner = self.tuner
        if tuner is not None and tuner.running():
            tuner.stop = True
            stop_tree(tuner.proc)
            return "tuner"
        job = self.tool
        if job is not None and job.done is None:
            job.stop = True
            stop_tree(job.proc)
            return "tools"
        return None

    @staticmethod
    def _drop_partial(job):
        """Remove what the stopped command left half written (a review file, Wiktionary's entries)."""
        if job.step is None or job.step >= len(job.partial):
            return
        try:
            os.remove(job.partial[job.step])
        except OSError:
            pass

    def show_tuner(self, bring=True):
        """Bring the tuner's window back (asked for: closed while it tunes, a click on its bubble opens it again; once
        done, the next click shows the open window rather than starting another). True if a tuner was there."""
        job = self.tuner
        if job is None or not job.running():
            return False
        if not bring:                             # (only: is one running?)
            return True
        try:
            job.proc.stdin.write("show\n")
            job.proc.stdin.flush()
        except (OSError, ValueError, AttributeError):
            return False
        job.hidden = False
        return True

    # ---- Review words | Tune & reroll ------------------------------------------------------------------------------
    def review_words(self, dlg=None, ask=None, run=None):
        """The Review words bubble's left half (asked for: one bubble for the review words): the review
        (review_rude); with no review file yet, the first review words are made (make_review_words) and the review
        opens on them. Returns what it started (the review, the commands) or None."""
        if self.tool is not None and self.tool.then == "open":
            self._flash("Still making the first review words", kind="info")
            return None
        if os.path.exists(self.review_file()):
            return self.review_rude(dlg)
        return self.make_review_words(dlg, ask, run, then="open")

    def _tune_base(self, n):
        """The answers there were when Tune & reroll last started (meta tune_base); the first time, `n`."""
        store = self.app.store
        try:
            return int(store.get_meta("tune_base"))
        except (TypeError, ValueError):
            store.set_meta("tune_base", str(n))
            return n

    def next_auto_tune(self, n):
        """At how many answered words the next automatic Tune & reroll starts (the review's strip), with `n` now."""
        return self._tune_base(n) + self.AUTO_TUNE

    def review_answered(self, n, start=None, run=None):
        """The review saved an answer, `n` words answered (DT-6): every AUTO_TUNE new ones, Tune & reroll starts by
        itself, its tuner hidden until it is done (--start-hidden); never while one runs, nor without the tools or
        the entries (no questions asked: it waits for the next answer). Returns the tuner's command, or None."""
        if n < self.next_auto_tune(n) or self.tool is not None or self.show_tuner(bring=False):
            return None
        if is_frozen() or not os.path.exists(self._entries()):
            return None
        return self.tune_reroll(None, start=start, run=run, hidden=True)

    def tune_reroll(self, dlg=None, ask=None, start=None, run=None, hidden=False):
        """The Review words bubble's right half, Tune & reroll (asked for: the tools run in sequence): the tuner
        (tune_rules); once it has tuned to the end and its window is closed (Keep or Discard), new review words
        (make_review_words, then="reroll"). While it runs, a click brings the tuner's window back (or says the new
        words are still being made). `run`: for the reroll (tests). Returns the tuner's command, or None."""
        if self.tool is not None:
            self._flash("Still making review words", kind="info")
            return None
        if self.show_tuner():                     # (one tuner at a time: the open one is brought forward)
            if dlg is not None:
                dlg.close()
            return None
        cmd = self.tune_rules(dlg, ask, start, hidden=hidden)
        if cmd:
            answered = read_answers(review_answers_path(self.review_file()))
            self.app.store.set_meta("tune_base", str(len(answered)))    # (by hand too: the next 50 count from here)
        if cmd and self.tuner is not None:
            self.tuner.run = run
            job = self.tuner
            if self._watch_tuner(job):
                Repeat(self.app.root, 300, lambda: self._watch_tuner(job))
        return cmd

    def _watch_tuner(self, job):
        """Tune & reroll's steps (polled: the tuner is read on a worker thread): a toast when the tuner is done,
        then, once its process has ended after tuning to the end, the reroll; a tuner closed mid-way ends it. True
        while it runs (asked again: a Repeat)."""
        if job.tuned and not job.said:
            job.said = True
            self._flash("The tuner is done: Keep or Discard its numbers in its window", kind="ok", ms=6000)
        if job.running():
            return True
        if self.tuner is job:
            self.tuner = None
        if job.stop:
            self._flash("Stopped: the tuner's numbers were thrown away", kind="info", ms=5000)
        elif job.tuned:
            self.make_review_words(None, run=job.run, then="reroll")
        elif job.proc.poll():
            self._flash("The tuner stopped before it was done", kind="warn", ms=6000)
        return False

    def make_review_words(self, dlg=None, ask=None, run=None, then=None):
        """Make review words (OB-11): tools/measure_rudeness.py in the background, the review file next to the save
        (review_file): `sample` (1,500 words) when there is none yet, else `next` (the answered words kept, the rest
        replaced by 300 picked from the answers' misses; an open review opens again on them). The Wiktionary entries
        it reads (rudeness_entries.jsonl in the source folder) are fetched first when missing, after asking
        (`ask(): yes?`, tests). A toast says when it starts and what it made. `run(commands) -> (exit code, its last
        line)` runs them, on a worker thread (tests: at once). `then`: "open" (the review opens on them) or "reroll"
        (the end of Tune & reroll: its toast). Returns the commands, or None."""
        parent = dlg.win if dlg else self.app.root
        tool = self._tool("measure_rudeness.py", parent)
        if tool is None:
            return None
        if self.tool is not None:
            self._flash("Still making review words", kind="info")
            return None
        path = self.review_file()
        cmds, partial = [], []
        entries = self._entries()
        if not os.path.exists(entries):
            if not (ask or (lambda: ask_yes_no(
                    "Make review words", "Read Wiktionary's entries first?",
                    "The words are picked from every English entry of Wiktionary: about 3 GB to read once, kept as "
                    "rudeness_entries.jsonl (about 300 MB) in the source folder. It can take half an hour.",
                    yes="Read them", parent=parent)))():
                return None
            cmds.append([sys.executable, tool, "fetch"])
            partial.append(entries)
        first = not os.path.exists(path)
        cmds.append([sys.executable, tool, "sample", "--out", path] if first else
                    [sys.executable, tool, "next", "--review", path])
        partial.append(path if first else path + ".part")     # (next writes a .part, then swaps it in)
        self.app.store.set_meta("review_file", os.path.abspath(path))
        self._flash(f"Making {'1,500' if first else '300 new'} review words: a few minutes", kind="info", ms=5000)
        job = self.tool = Job(then=then, path=path, partial=partial)

        def line(step, steps, text):
            job.note = (f"Step {step} of {steps}: " if steps > 1 else "") + text

        def done(result):
            job.done = result
            self._watch_tool(job)

        def failed(exc):                  # (a command that could not even start: said like one that failed)
            done((1, str(exc) or type(exc).__name__))
        Task(self.app.root, (lambda: run(cmds, self.root)) if run else (lambda: run_tools(cmds, self.root, line, job)),
             done=done, failed=failed, ms=500, thread=run is None)
        return cmds

    def _watch_tool(self, job):
        """The toast once the tools have run (`job.done`, handed over by make_review_words' Task)."""
        if job.done is None:
            return
        self.tool = None
        code, last = job.done
        app = self.app
        if job.stop:
            self._drop_partial(job)
            self._flash("Stopped: the review words are as they were" if job.then != "open" else
                       "Stopped: no review words were made", kind="info", ms=5000)
        elif code == 0:
            if app.review is not None and app.review.alive() and app.review_path == job.path:
                app.review.close()                # (the file was refreshed under it: open it again on the new words,
                app.open_review(job.path)         # its answers saved already)
            elif job.then == "open" and os.path.exists(job.path):
                app.open_review(job.path)
            done = last or "review words made"
            self._flash(f"Tune & reroll is done: {done}" if job.then == "reroll" else done, kind="ok", ms=6000)
        else:
            self._flash(f"{'Tune & reroll' if job.then == 'reroll' else 'Making review words'} failed: {last}",
                       kind="warn", ms=8000)

    def tune_rules(self, dlg=None, ask=None, start=None, hidden=False):
        """Tune the rules (OB-10; Tune & reroll's first step): tools/tune_rudeness.py's window, a program of its own,
        on the review file and its answers (asked for when there is none next to the save). It needs the Wiktionary
        entries (making the first review words reads them) and some answers. `start(command)`: how to start it
        (tests). Returns the command, or None."""
        parent = dlg.win if dlg else self.app.root
        tool = self._tool("tune_rudeness.py", parent)
        path = tool and self.pick_review_file(parent, ask)
        if not path:
            return None
        entries = self._entries()
        if not os.path.exists(review_answers_path(path)):
            show_message("Tune the rules", "Nothing answered yet", "Review some rude meanings first: the rules are "
                         "tuned against your answers.", parent=parent)
            return None
        if not os.path.exists(entries):
            show_message("Tune the rules", "Wiktionary's entries are missing", "Review words reads them when it makes "
                         "the first review words (about 3 GB, once): the tuner scores every word they hold.",
                         parent=parent)
            return None
        cmd = [sys.executable, tool, "--review", path, "--entries", entries, "--from-program"] + \
            (["--start-hidden"] if hidden else [])
        proc = (start or (lambda c: subprocess.Popen(c, cwd=self.root, env=standalone.clean_env(),
                                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                                                     bufsize=1, **OWN_GROUP)))(cmd)
        if getattr(proc, "stdout", None) is not None:      # (its rounds fill the bubble's ring: follow_tuner)
            self.tuner = Job(proc=proc)
            threading.Thread(target=follow_tuner, args=(proc, self.tuner), daemon=True).start()
        if dlg is not None:
            dlg.close()
        self._flash(f"{self.AUTO_TUNE} new answers: tuning the rules in the background (its window shows when done)"
                   if hidden else "The tuner is opening: it reads Wiktionary's entries first (about a minute)",
                   kind="info", ms=5000)
        return cmd

    # ---- Source & Updates: Log, Crash test -------------------------------------------------------------------------
    def open_log(self):
        """The "Log" bubble: tierlist.log next to the save, in the system's text viewer."""
        path = os.path.join(os.path.dirname(os.path.abspath(self.app.store.path)), LOG_FILE)
        try:
            if not os.path.exists(path):
                raise OSError(f"there is no {LOG_FILE} yet")
            standalone.open_folder(path)          # (xdg-open / open / startfile open a file with its own program)
        except OSError as exc:
            self._flash(f"Could not open the log: {exc}", kind="warn")
        return path

    def crash_test(self, dlg=None, delay=300):
        """The "Crash test" bubble (was --crash-test): close the dialog, then fail on purpose, to see the error
        dialog and the log entry; the program keeps running."""
        if dlg is not None:
            dlg.close()
        self.app.root.after(delay, lambda: 1 / 0)
