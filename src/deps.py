"""Third-party packages the program needs, and installing them (no tkinter here).

Two stages (ST-4): before any window exists, terminal_setup() asks in the terminal to install only what
the window cannot open without (tkinter). Every Python package, required (wordfreq) or optional (nltk),
is then offered in the window by startup.ensure_packages, each as its own choice. Keep PACKAGES in step with
requirements.txt (a test checks it).
"""
import importlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from constants import plan_line

# import name -> what to hand to pip
PACKAGES = {"wordfreq": "wordfreq>=3.0", "nltk": "nltk"}

# needed to build and rank the word list / nice to have; both are offered in the window, separately
REQUIRED = ["wordfreq"]
OPTIONAL = ["nltk"]

# disk space each one takes in MB, shown next to its tick box. Measured with pip for wordfreq 3.1 (57 MB to
# download, 70 installed, mostly frequency data) and nltk 3.10 (3 MB download, 23 installed, plus 11 MB of
# WordNet data on first use), Python 3.12; re-measure when the requirements change.
SIZE = {"wordfreq": 70, "nltk": 35}
# what pip downloads for each, with the packages it pulls in (MB; measured with pip 24 for wordfreq 3.1 and
# nltk 3.10): the installing window measures the download against this to show a percentage and a speed
DOWNLOAD = {"wordfreq": 59, "nltk": 3}

# what each one is for, in the words used in the install question
PURPOSE = {"wordfreq": "word frequency data: needed to build and rank the word list",
           "nltk": "the WordNet dictionary, for offline definitions (the program works without it)",
           "tkinter": "the window toolkit (comes with Python, but some systems ship it separately)"}

# each one's own web page (UI-30): a link on its name in the install dialog, printed in the terminal
HOMEPAGE = {"wordfreq": "https://pypi.org/project/wordfreq/",
            "nltk": "https://www.nltk.org/",
            "tkinter": "https://docs.python.org/3/library/tkinter.html"}


def missing(names):
    """The import names in `names` that cannot be imported right now."""
    return [n for n in names if importlib.util.find_spec(n) is None]


def pip_available():
    """True if `python -m pip` works for this interpreter."""
    try:
        return subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True,
                              timeout=30, **_hidden()).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


_DOWNLOADING = re.compile(r"Downloading (\S+) \(([\d.]+) (kB|MB|GB)\)")
_UNIT = {"kB": 1e3, "MB": 1e6, "GB": 1e9}
_ARCHIVES = (".whl", ".tar.gz", ".zip")
INSTALL_STEPS = ["Downloading", "Installing"]      # the main steps install() reports (plan_line)


def install(names, log=print, python=None, plan=True):
    """pip-install the packages for the import names `names`, streaming pip's output through `log`.

    Returns (ok, tail): whether pip succeeded and its last lines (for an error message). Runs in this
    Python (sys.executable) unless `python` names another (a private environment), so the packages land
    where the program will find them. `plan`: announce the two steps (downloading, installing) to the
    progress window; off when a caller announced a longer plan of its own.

    How fast it downloads is measured, not guessed: pip prints no progress when its output is not a terminal,
    so it gets a temporary folder of its own (TMPDIR) and a watcher thread follows the file being downloaded
    there, adding up the files already done (pip names each one and its size as it starts it). Every half
    second that becomes a detail line, "12.4 of 62 MB at 3.1 MB/s (20%)", whose percentage drives the bar and
    the time-left estimate.
    """
    total = sum(DOWNLOAD.get(n, 1) for n in names) * 1e6
    if plan:
        log(plan_line(INSTALL_STEPS))
    log(f"Downloading {', '.join(names)} (about {total / 1e6:.0f} MB)...")
    tmp = tempfile.mkdtemp(prefix="wordtier-pip-")
    env = dict(os.environ, TMPDIR=tmp, TEMP=tmp, TMP=tmp)
    cmd = [python or sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
           "--no-input", "--progress-bar", "off", *[PACKAGES.get(n, n) for n in names]]
    state = {"done": 0.0, "current": 0.0, "installing": False, "finished": False}
    watcher = threading.Thread(target=_watch_download, args=(tmp, total, state, log), daemon=True)
    lines = []
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                errors="replace", env=env, **_hidden())
        watcher.start()
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            lines.append(line)
            m = _DOWNLOADING.search(line)
            if m and not m.group(1).endswith(".metadata"):
                state["done"] += state["current"]          # the one before it has finished
                state["current"] = float(m.group(2)) * _UNIT[m.group(3)]
            elif line.startswith("Installing collected packages") and not state["installing"]:
                state["installing"] = True
                log("Installing...")
            if not line.lstrip().startswith(("Collecting", "Downloading", "Using cached")):
                log("  " + line[:90])        # a leading space = a detail line in the progress window
        proc.wait()
    except OSError as exc:
        return False, str(exc)
    finally:
        state["finished"] = True
        if watcher.is_alive():
            watcher.join(timeout=2)
        shutil.rmtree(tmp, ignore_errors=True)
    importlib.invalidate_caches()           # so the new packages can be imported without restarting
    return proc.returncode == 0, "\n".join(lines[-12:])


def _watch_download(folder, total, state, log, every=0.5, clock=time.monotonic):
    """install()'s watcher: until pip starts installing, report how much has come down and how fast."""
    history = []                                      # (time, bytes) over the last few seconds, for the speed
    last = None
    while not state["finished"] and not state["installing"]:
        got = state["done"] + min(_largest_archive(folder), state["current"] or float("inf"))
        now = clock()
        history.append((now, got))
        while len(history) > 2 and now - history[0][0] > 5:
            history.pop(0)
        span = history[-1][0] - history[0][0]
        speed = (history[-1][1] - history[0][1]) / span if span > 0.9 else None
        whole = max(total, state["done"] + state["current"])
        line = (f"  {got / 1e6:.1f} of {whole / 1e6:.0f} MB" + (f" at {speed / 1e6:.1f} MB/s" if speed else "")
                + f" ({min(99, int(got * 100 / whole))}%)")
        if got and line != last:
            log(line)
            last = line
        time.sleep(every)


def _largest_archive(folder):
    """Size of the biggest package file under `folder` (the one being downloaded), 0 if none."""
    best = 0
    for top, _dirs, files in os.walk(folder):
        for f in files:
            if f.endswith(_ARCHIVES):
                try:
                    best = max(best, os.path.getsize(os.path.join(top, f)))
                except OSError:
                    pass
    return best


def _hidden():
    """Windows: do not flash a console window for the pip process."""
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


# --------------------------------------------------------------------------
# Stage 1: the terminal, before any window (ST-4)
# --------------------------------------------------------------------------
REEXEC_ENV = "WORD_TIERLIST_RESTARTED"      # set when we restart ourselves, so a restart never loops


def tk_available():
    """True if tkinter (and the _tkinter extension under it) can be imported."""
    try:
        importlib.import_module("tkinter")
        return True
    except ImportError:
        return False


def tk_install_command(platform=None, which=None):
    """The system command that installs tkinter for this Python, as a list, or None if we do not know one.

    Linux: the distribution's package manager (only for the system Python, which is what those packages
    serve). macOS: Homebrew's python-tk for this Python version. Windows: None (tkinter is an option of the
    python.org installer, not something to install afterwards).
    """
    platform = platform or sys.platform
    which = which or shutil.which
    if platform.startswith("linux"):
        sudo = [] if hasattr(os, "geteuid") and os.geteuid() == 0 else ["sudo"]
        for tool, cmd in (("apt-get", ["apt-get", "install", "-y", "python3-tk"]),
                          ("dnf", ["dnf", "install", "-y", "python3-tkinter"]),
                          ("pacman", ["pacman", "-S", "--noconfirm", "tk"]),
                          ("zypper", ["zypper", "--non-interactive", "install", "python3-tk"])):
            if which(tool):
                return sudo + cmd
    elif platform == "darwin" and which("brew"):
        return ["brew", "install", f"python-tk@{sys.version_info[0]}.{sys.version_info[1]}"]
    return None


def tk_advice(platform=None):
    """What to do yourself when tkinter is missing and cannot be installed from here."""
    platform = platform or sys.platform
    if platform.startswith("win"):
        return ("Run the python.org installer again, choose Modify, and tick \"tcl/tk and IDLE\".")
    if platform == "darwin":
        return "Install Python from python.org (it includes tkinter), or with Homebrew:  brew install python-tk"
    return ("Install your system's tkinter package, for example:\n"
            "    Debian/Ubuntu:  sudo apt install python3-tk\n"
            "    Fedora:         sudo dnf install python3-tkinter\n"
            "    Arch:           sudo pacman -S tk")


def venv_python(venv_dir):
    """The python inside a virtual environment folder (it may not exist yet)."""
    if os.name == "nt":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def _same_python(path):
    try:
        return os.path.samefile(path, sys.executable)
    except OSError:
        return False


def restart(python, argv):
    """Start the program again with `python` (after tkinter or a private environment was set up).

    POSIX replaces this process, so the terminal simply carries on with the new one. Windows has no real
    exec, so it runs the new process and exits with its code.
    """
    os.environ[REEXEC_ENV] = "1"
    sys.stdout.flush()
    cmd = [python, *argv]
    if os.name == "nt":
        sys.exit(subprocess.call(cmd))
    os.execv(python, cmd)


def _ask(ask, out, question):
    """Ask a yes/no question in the terminal; Enter means yes. No terminal input (EOF) counts as no."""
    while True:
        try:
            answer = ask(f"{question} [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            out("")
            return False
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        out("Please answer y or n.")


def use_private_env(argv, home, has_tk=None, restarter=None):
    """If something is missing here but the program's private environment (<home>/.venv, made by the
    window's install step) exists, restart in it straight away: that is where the packages went. Never
    loops (REEXEC_ENV). Returns True when it restarted (only seen in tests; a real restart does not return)."""
    has_tk = has_tk or tk_available
    vpy = venv_python(os.path.join(home, ".venv"))
    if os.environ.get(REEXEC_ENV) or not os.path.exists(vpy) or _same_python(vpy):
        return False
    if has_tk() and not missing(REQUIRED):
        return False
    (restarter or restart)(vpy, argv)
    return True


def terminal_setup(argv, ask=input, out=print, run=subprocess.call, has_tk=None, tk_command=None,
                   restarter=None):
    """Stage 1 of the install (ST-4): in the terminal, before any window, get only what the window itself
    needs, which is tkinter. Every Python package (wordfreq, nltk) is asked about later, in the window.

    Asks once ("Install it now? [Y/n]", Enter = yes), installs it with the system package manager (sudo may
    ask for your password) and restarts the program so the window can open. Returns True when tkinter is
    there. Raises SystemExit with what to do when it is missing and cannot or may not be installed.
    The keyword arguments after `argv` are for tests."""
    has_tk = has_tk or tk_available
    if has_tk():
        return True
    tk_cmd = tk_command if tk_command is not None else tk_install_command()
    out("")
    out(f"Word Tier List needs tkinter, {PURPOSE['tkinter']}, to open its window.")
    out(f"More about it: {HOMEPAGE['tkinter']}")
    if not tk_cmd:
        raise SystemExit("tkinter cannot be installed from here. " + tk_advice())
    out(f"It can be installed with: {' '.join(tk_cmd)}")
    out("Everything else the program uses is asked about in the window.")
    if not _ask(ask, out, "Install it now?"):
        raise SystemExit("The window cannot open without tkinter. " + tk_advice())
    out(f"Installing tkinter: {' '.join(tk_cmd)}")
    if run(tk_cmd) != 0 or not has_tk():
        raise SystemExit("tkinter could not be installed for this Python "
                         f"({sys.executable}). " + tk_advice())
    out("Done. Opening the window...")
    (restarter or restart)(sys.executable, argv)     # tkinter was missing when the program started
    return True


def make_private_env(home, names, log=print):
    """Make <home>/.venv and pip-install `names` into it, streaming output through `log`. For a Python that
    refuses installs (externally-managed). Returns (ok, tail, python of the environment)."""
    venv = os.path.join(home, ".venv")
    vpy = venv_python(venv)
    log(plan_line(["Making a private environment"] + INSTALL_STEPS))
    log(f"Making a private environment in {venv}...")
    if _make_venv(venv, log) != 0 or not os.path.exists(vpy):
        return False, ("Could not make the private environment. On Debian/Ubuntu it needs:\n"
                       "    sudo apt install python3-venv"), vpy
    ok, tail = install(names, log, python=vpy, plan=False)
    return ok, tail, vpy


def _make_venv(venv, log):
    return subprocess.call([sys.executable, "-m", "venv", venv], **_hidden())


def wants_terminal_setup(no_install):
    """True when stage 1 should run: an interactive terminal, installs allowed, not a packaged build."""
    if no_install or getattr(sys, "frozen", False):
        return False
    try:
        return sys.stdin is not None and sys.stdin.isatty() and sys.stdout is not None and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False
