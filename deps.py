"""Third-party packages the program needs, and installing them (no tkinter here).

Two stages (ST-4): before any window exists, terminal_setup() asks in the terminal to install only what
the program cannot start without (tkinter and wordfreq), installs it, then the window opens. Everything
optional (nltk) is offered later, in the window, by startup.ensure_packages. Keep PACKAGES in step with
requirements.txt (a test checks it).
"""
import importlib
import importlib.util
import os
import shutil
import subprocess
import sys

# import name -> what to hand to pip
PACKAGES = {"wordfreq": "wordfreq>=3.0", "nltk": "nltk"}

# needed before the window can do its job (asked in the terminal); the rest are offered in the window
REQUIRED = ["wordfreq"]
OPTIONAL = ["nltk"]

# what each one is for, in the words used in the install question
PURPOSE = {"wordfreq": "word frequency data (needed to rank the words)",
           "nltk": "the WordNet dictionary, for offline definitions (the program works without it)",
           "tkinter": "the window toolkit (comes with Python, but some systems ship it separately)"}


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


def install(names, log=print):
    """pip-install the packages for the import names `names`, streaming pip's output through `log`.

    Returns (ok, tail): whether pip succeeded and its last lines (for an error message). Runs in this
    Python (sys.executable), so the packages land where the program will find them.
    """
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
           "--no-input", "--progress-bar", "off", *[PACKAGES.get(n, n) for n in names]]
    lines = []
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                errors="replace", **_hidden())
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                lines.append(line)
                log("  " + line[:90])        # a leading space = a detail line in the progress window
        proc.wait()
    except OSError as exc:
        return False, str(exc)
    importlib.invalidate_caches()           # so the new packages can be imported without restarting
    return proc.returncode == 0, "\n".join(lines[-12:])


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


def terminal_setup(argv, home, ask=input, out=print, run=subprocess.call, installer=None,
                   has_tk=None, tk_command=None, make_venv=None, restarter=None):
    """Stage 1 of the install (ST-4): in the terminal, before any window, get only what the program cannot
    start without (tkinter and the REQUIRED packages). Optional packages are left for the window.

    Asks once ("Install them now? [Y/n]"), installs (the tkinter system package through the package
    manager, which may ask for your password; the Python packages with pip, output shown as it goes) and
    then returns so the program opens its window. Returns True when everything required is there.

    * If this Python refuses pip installs (externally-managed, typical on Linux), offers to make a private
      environment in <home>/.venv, installs there and restarts the program with it. A later start with the
      system Python that finds .venv restarts into it straight away, without asking again.
    * Answering no: without tkinter the program cannot continue (SystemExit with what to do); without
      wordfreq it carries on and the window explains (same as "Not now" there).
    `argv` is the command line to restart with; the keyword arguments after `out` are for tests.
    """
    installer = installer or install
    has_tk = has_tk or tk_available
    restarter = restarter or restart
    need = missing(REQUIRED)
    no_tk = not has_tk()
    if not need and not no_tk:
        return True
    venv = os.path.join(home, ".venv")
    vpy = venv_python(venv)
    if (os.path.exists(vpy) and not _same_python(vpy) and not os.environ.get(REEXEC_ENV)):
        out(f"Using the program's private Python environment ({venv}).")
        restarter(vpy, argv)
        return True                                  # only reached in tests (restart replaces the process)
    tk_cmd = (tk_command if tk_command is not None else tk_install_command()) if no_tk else None
    out("")
    out("Word Tier List needs a few things before it can open its window:")
    if no_tk:
        how = f" (installed with: {' '.join(tk_cmd)})" if tk_cmd else ""
        out(f"    tkinter: {PURPOSE['tkinter']}{how}")
    for n in need:
        out(f"    {n}: {PURPOSE.get(n, n)}")
    if [n for n in OPTIONAL if n not in need]:
        out("Optional extras are offered later, in the window.")
    if need:
        out(f"The Python packages are installed with: pip install {' '.join(PACKAGES.get(n, n) for n in need)}")
    if no_tk and not tk_cmd:
        out("")
        raise SystemExit("tkinter cannot be installed from here. " + tk_advice())
    if not _ask(ask, out, "Install them now?"):
        if no_tk:
            raise SystemExit("The window cannot open without tkinter. " + tk_advice())
        out("Carrying on without them; the window explains what does not work.")
        return False
    if no_tk:
        out(f"Installing tkinter: {' '.join(tk_cmd)}")
        code = run(tk_cmd)
        if code != 0 or not has_tk():
            raise SystemExit("tkinter could not be installed for this Python "
                             f"({sys.executable}). " + tk_advice())
    if need:
        out("Installing " + ", ".join(need) + " (this needs an internet connection and takes a minute or so)...")
        ok, tail = installer(need, out)
        if not ok and "externally-managed-environment" in tail:
            out("")
            out("This Python does not allow installing packages into it directly.")
            if not _ask(ask, out, f"Make a private environment for the program in {venv} and install there?"):
                raise SystemExit("Nothing was installed. To do it yourself:\n"
                                 f"    {sys.executable} -m venv {venv}\n"
                                 f"    {vpy} -m pip install -r requirements.txt\n"
                                 f"    {vpy} tierlist.py")
            out(f"Making {venv}...")
            if (make_venv or _make_venv)(venv, out) != 0 or not os.path.exists(vpy):
                raise SystemExit("Could not make the private environment. On Debian/Ubuntu it needs:\n"
                                 "    sudo apt install python3-venv")
            code = run([vpy, "-m", "pip", "install", "--disable-pip-version-check",
                        *[PACKAGES.get(n, n) for n in need]])
            if code != 0:
                raise SystemExit("Could not install the packages into the private environment (see above).")
            out("Done. Restarting with the private environment...")
            restarter(vpy, argv)
            return True
        if not ok or missing(need):
            raise SystemExit(f"Could not install {', '.join(need)}.\n\n{tail}\n\nTry running this yourself:\n"
                             f"    {sys.executable} -m pip install {' '.join(PACKAGES.get(n, n) for n in need)}")
    if no_tk:
        out("Done. Opening the window...")
        restarter(sys.executable, argv)              # tkinter was missing when the program started
        return True
    out("Done. Opening the window...")
    return True


def _make_venv(venv, out):
    return subprocess.call([sys.executable, "-m", "venv", venv])


def wants_terminal_setup(no_install):
    """True when stage 1 should run: an interactive terminal, installs allowed, not a packaged build."""
    if no_install or getattr(sys, "frozen", False):
        return False
    try:
        return sys.stdin is not None and sys.stdin.isatty() and sys.stdout is not None and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False
