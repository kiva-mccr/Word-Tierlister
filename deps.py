"""Third-party packages the program needs, and installing them (no tkinter here).

The window part (asking first, showing progress) is startup.ensure_packages. Keep PACKAGES in step with
requirements.txt (a test checks it).
"""
import importlib.util
import os
import subprocess
import sys

# import name -> what to hand to pip
PACKAGES = {"wordfreq": "wordfreq>=3.0", "nltk": "nltk"}

# what each one is for, in the words used in the install question
PURPOSE = {"wordfreq": "word frequency data (needed to rank the words)",
           "nltk": "the WordNet dictionary, for offline definitions (the program works without it)"}


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
