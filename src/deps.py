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

# what making the program (File > Source & Updates, T-6) needs as well: the builder. Not in requirements.txt (the
# program itself never imports it); offered with the program's own packages before a build (sources.py)
BUILD_PACKAGES = {"PyInstaller": "pyinstaller"}
PIP_NAMES = {**PACKAGES, **BUILD_PACKAGES}      # import name -> what to hand to pip, for anything offered

# disk space each one takes in MB, shown next to its tick box. Measured with pip for wordfreq 3.1 (57 MB to
# download, 70 installed, mostly frequency data) and nltk 3.10 (3 MB download, 23 installed, plus 11 MB of
# WordNet data on first use), Python 3.12; re-measure when the requirements change.
SIZE = {"wordfreq": 70, "nltk": 35, "PyInstaller": 15}   # (PyInstaller 6.22: 2 MB to download, 15 installed)
# what pip downloads for each, with the packages it pulls in (MB; measured with pip 24 for wordfreq 3.1 and
# nltk 3.10): the installing window measures the download against this to show a percentage and a speed
DOWNLOAD = {"wordfreq": 59, "nltk": 3, "PyInstaller": 3}

# what each one is for, in the words used in the install question
PURPOSE = {"wordfreq": "word frequency data: needed to build and rank the word list",
           "nltk": "the WordNet dictionary, for offline definitions (the program works without it)",
           "tkinter": "the window toolkit (comes with Python, but some systems ship it separately)",
           "PyInstaller": "the builder that turns the program into one file: needed to make the program"}

# each one's own web page (UI-30): a link on its name in the install dialog, printed in the terminal
HOMEPAGE = {"wordfreq": "https://pypi.org/project/wordfreq/",
            "nltk": "https://www.nltk.org/",
            "tkinter": "https://docs.python.org/3/library/tkinter.html",
            "PyInstaller": "https://pyinstaller.org/"}


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
           "--no-input", "--progress-bar", "off", *[PIP_NAMES.get(n, n) for n in names]]
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


# What the system's own package manager installs for each piece the program needs from outside Python's packages
# (asked for: anything missing is offered, not only told). None: nothing to install there (it comes with Python).
SYSTEM_PACKAGES = {
    "apt-get": {"tkinter": ["python3-tk"], "pip": ["python3-pip"], "venv": ["python3-venv"],
                "python": ["python3", "python3-tk"]},
    "dnf": {"tkinter": ["python3-tkinter"], "pip": ["python3-pip"], "venv": None,
            "python": ["python3", "python3-tkinter"]},
    "pacman": {"tkinter": ["tk"], "pip": ["python-pip"], "venv": None, "python": ["python", "tk"]},
    "zypper": {"tkinter": ["python3-tk"], "pip": ["python3-pip"], "venv": None, "python": ["python3", "python3-tk"]},
}
_MANAGERS = {"apt-get": ["apt-get", "install", "-y"], "dnf": ["dnf", "install", "-y"],
             "pacman": ["pacman", "-S", "--noconfirm"], "zypper": ["zypper", "--non-interactive", "install"]}
SYSTEM_NAMES = {"tkinter": "tkinter", "pip": "pip, Python's package installer", "venv": "Python's venv module",
                "python": "Python"}


def system_install_command(what, platform=None, which=None, window=False):
    """The system command that installs `what` ("tkinter", "pip", "venv" or "python") for this computer, as a
    list, or None if there is nothing we know to run.

    Linux: the distribution's package manager (only for the system Python, which is what those packages serve),
    as root: through sudo in a terminal, through pkexec (the desktop's own password prompt) from a `window`.
    macOS: Homebrew (python-tk brings Python with it). Windows: winget for Python (for this user, no admin);
    tkinter is an option of the python.org installer, not something to install afterwards."""
    platform = platform or sys.platform
    which = which or shutil.which
    if platform.startswith("linux"):
        root = hasattr(os, "geteuid") and os.geteuid() == 0
        if root:
            elevate = []
        elif window:
            if not which("pkexec"):
                return None                          # (no way to ask for the password without a terminal)
            elevate = ["pkexec"]
        else:
            elevate = ["sudo"]
        for tool, packages in SYSTEM_PACKAGES.items():
            if which(tool):
                names = packages.get(what)
                return elevate + _MANAGERS[tool] + names if names else None
    elif platform == "darwin" and which("brew"):
        version = f"{sys.version_info[0]}.{sys.version_info[1]}"
        return {"tkinter": ["brew", "install", f"python-tk@{version}"], "python": ["brew", "install", "python-tk"],
                "pip": None, "venv": None}.get(what)
    elif platform.startswith("win") and what == "python" and which("winget"):
        return ["winget", "install", "-e", "--id", "Python.Python.3.12", "--scope", "user",
                "--accept-package-agreements", "--accept-source-agreements"]
    return None


def tk_install_command(platform=None, which=None):
    """The system command that installs tkinter for this Python in a terminal (see system_install_command)."""
    return system_install_command("tkinter", platform, which)


def run_system_install(cmd, log=print):
    """Run a system install command (system_install_command), its output through `log`; True if it worked. Runs
    on a worker thread behind the progress window (never touches tkinter)."""
    log("Installing: " + " ".join(cmd))
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                stdin=subprocess.DEVNULL, **_hidden())
    except OSError as exc:
        log(f"  could not run it: {exc}")
        return False
    for line in proc.stdout:
        if line.strip():
            log("  " + line.rstrip()[:200])
    return proc.wait() == 0


def ensure_pip(python=None, run=subprocess.run):
    """Python's own way to put pip back (ensurepip: no password, nothing from the system); True if pip works then.
    Debian's Python leaves it out: then the system package is needed (system_install_command("pip"))."""
    try:
        run([python or sys.executable, "-m", "ensurepip", "--upgrade"], capture_output=True, timeout=300,
            **_hidden())
    except (OSError, subprocess.SubprocessError):
        return False
    return pip_available()


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


# --------------------------------------------------------------------------
# ST-5: give the terminal back (Linux / macOS), and a launcher in the applications menu (Linux)
# --------------------------------------------------------------------------
DETACHED_ENV = "WORD_TIERLIST_DETACHED"     # set in the copy started in its own session (so it never loops)
DETACH_WAIT = 1.5                           # seconds the terminal waits to see the new copy get going


def windowless_python(python=None, exists=os.path.exists):
    """Windows: pythonw.exe, the Python with no console window, beside this python.exe (every python.org install
    and every venv has it), or None."""
    exe = python or sys.executable
    folder, name = os.path.split(exe)
    if name.lower() == "pythonw.exe":
        return exe
    w = os.path.join(folder, "pythonw.exe")
    return w if exists(w) else None


def should_detach(console=False, env=None, streams=None, posix=None, windows=None, pythonw=None):
    """True when the program, started from a terminal (or a console window a double-click opened), should carry
    on without it and let it go (so closing it no longer closes the program): Linux and macOS in a session of
    their own; Windows with pythonw.exe (reported: the console window stayed open behind it; letting go of it
    alone is not enough when the py launcher that opened it waits on). Not with --console, not when output is
    redirected on purpose, not twice, on Linux only with a desktop to draw on (else the window could not open,
    and the message saying so must stay in the terminal), on Windows only with a pythonw.exe. Arguments are for
    tests."""
    env = os.environ if env is None else env
    windows = (os.name == "nt") if windows is None else windows
    posix = (os.name == "posix") if posix is None else posix
    if console or env.get(DETACHED_ENV):
        return False
    if windows:
        if not (pythonw if pythonw is not None else windowless_python()):
            return False
        try:
            return all(s is not None and s.isatty() for s in (streams or (sys.stdin, sys.stdout)))
        except (AttributeError, ValueError):
            return False
    if not posix:
        return False
    if sys.platform != "darwin" and not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        return False
    try:
        return all(s is not None and s.isatty() for s in (streams or (sys.stdin, sys.stdout)))
    except (AttributeError, ValueError):
        return False


def detach_terminal(argv, out=print, popen=subprocess.Popen, wait=DETACH_WAIT, clock=time.monotonic,
                    sleep=time.sleep, windows=None, pythonw=None):
    """Start the program again on its own, not tied to this terminal, and return the exit code for this one:
    Linux / macOS in a session of its own (setsid), Windows with pythonw.exe (no console window), detached; this
    copy then ends, so the console window a double-click opened closes and a terminal gets its prompt back. It
    waits a moment: if the new copy fails straight away (it could not open its window), what it said is shown
    here, so a failure is never silent. The new copy writes its messages to tierlist.log next to the save. The
    keyword arguments are for tests."""
    early = tempfile.TemporaryFile()             # what it says while getting going (shown only if it fails)
    env = dict(os.environ, **{DETACHED_ENV: "1"})
    windows = (os.name == "nt") if windows is None else windows
    if windows:
        flags = getattr(subprocess, "DETACHED_PROCESS", 0x8) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
        child = popen([pythonw or windowless_python(), *argv], stdin=subprocess.DEVNULL, stdout=early, stderr=early,
                      creationflags=flags, close_fds=True, env=env)
    else:
        child = popen([sys.executable, *argv], stdin=subprocess.DEVNULL, stdout=early, stderr=early,
                      start_new_session=True, env=env)
    end = clock() + wait
    while clock() < end:
        code = child.poll()
        if code is not None:
            if code:
                early.seek(0)
                said = early.read().decode("utf-8", "replace").strip()
                out(said or f"The program stopped straight away (exit code {code}).")
            return code
        sleep(0.05)
    out("Word Tier List is open in its own window: you can close this terminal. "
        "(Messages go to tierlist.log next to your save; --console keeps them here.)")
    return 0


ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "icon-256.png")   # (IC-1)


def kept_icon(home=None):
    """The program's icon copied where it stays (~/.local/share/icons/word-tierlist.png: a built program's own copy
    is in a folder that is gone once it closes), for a launcher or a file's custom icon; its path, or None."""
    if not os.path.exists(ICON):
        return None
    home = home or os.path.expanduser("~")
    data = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    icon = os.path.join(data, "icons", "word-tierlist.png")
    try:
        os.makedirs(os.path.dirname(icon), exist_ok=True)
        shutil.copyfile(ICON, icon)
    except OSError:
        return None
    return icon


def desktop_entry(python, script, name="Word Tier List", icon="accessories-dictionary"):
    """The text of a Linux .desktop launcher that starts the program with no terminal (`script` None: a built
    program, started by itself); `icon`: a picture's path, or the name of one the desktop has."""
    q = lambda p: '"' + p.replace("\\", "\\\\").replace('"', '\\"') + '"'
    run = f"{q(python)} {q(script)}" if script else q(python)
    return "\n".join([
        "[Desktop Entry]", "Type=Application", f"Name={name}",
        "Comment=Tier-list every English word, at your own pace",
        f"Exec={run}", f"Path={os.path.dirname(script or python)}", "Terminal=false",
        f"Icon={icon}", "Categories=Education;Game;", "StartupNotify=true", ""])


def add_to_menu(python, script, home=None):
    """Write (or update) the launcher in ~/.local/share/applications, with the program's icon copied to
    ~/.local/share/icons (a built program's own copy is gone once it closes). Returns (path, "added" or "updated")."""
    home = home or os.path.expanduser("~")
    data = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    folder = os.path.join(data, "applications")
    os.makedirs(folder, exist_ok=True)
    icon = kept_icon(home) or "accessories-dictionary"
    path = os.path.join(folder, "word-tierlist.desktop")
    was = os.path.exists(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(desktop_entry(python, script, icon=icon))
    os.chmod(path, 0o755)
    return path, "updated" if was else "added"
