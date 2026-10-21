"""Build Word Tier List as a program for this computer's system (T-3), with PyInstaller.

    python tools/build.py            build into dist/ (installs PyInstaller first if it is missing)
    python tools/build.py --check    build, then start the new program for a moment to make sure it runs

What comes out (PyInstaller builds only for the system it runs on; T-8 covers the others):
    Linux     dist/word-tierlist            one file
    Windows   dist/word-tierlist.exe        one file, no console window
    macOS     dist/Word Tier List.app       an app bundle (one-file apps are not how macOS does it)

The program keeps its save beside itself (T-1: saves.app_dir) and carries only the data it reads (T-2:
tools/bundle.py). WordNet stays an optional download, as from source: the build machine's own ~/nltk_data is never
packed in (PyInstaller's nltk hook would do that; tools/hooks/hook-nltk.py replaces it).
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import bundle  # noqa: E402

NAME = "word-tierlist"
MAC_NAME = "Word Tier List"


def output_path(dist, platform=None):
    """Where the built program ends up for `platform` (sys.platform)."""
    platform = platform or sys.platform
    if platform.startswith("win"):
        return os.path.join(dist, NAME + ".exe")
    if platform == "darwin":
        return os.path.join(dist, MAC_NAME + ".app")
    return os.path.join(dist, NAME)


def pyinstaller_args(dist, work, platform=None):
    """The PyInstaller command line (after "python -m PyInstaller") for this system."""
    platform = platform or sys.platform
    sep = ";" if platform.startswith("win") else ":"
    mac = platform == "darwin"
    args = [os.path.join(ROOT, "tierlist.py"), "--noconfirm", "--clean",
            "--name", MAC_NAME if mac else NAME,
            "--distpath", dist, "--workpath", work, "--specpath", work,
            "--paths", os.path.join(ROOT, "src"),                        # (tierlist.py adds src/ itself at run time)
            "--additional-hooks-dir", os.path.join(TOOLS, "hooks"),
            "--windowed",                                               # no console window (ST-1, ST-2)
            "--onedir" if mac else "--onefile"]
    for src, dest in bundle.datas():
        args += ["--add-data", f"{src}{sep}{dest}"]
    for mod in bundle.EXCLUDE:
        args += ["--exclude-module", mod]
    return args


def ensure_pyinstaller(python=sys.executable, log=print):
    """Install PyInstaller if this Python lacks it (pip; with --break-system-packages on a Python that refuses
    plain pip installs, such as Debian's). Returns True when it is there."""
    def have():
        return subprocess.run([python, "-c", "import PyInstaller"], capture_output=True).returncode == 0
    if have():
        return True
    log("Installing PyInstaller (one time)...")
    for extra in ([], ["--break-system-packages"]):
        r = subprocess.run([python, "-m", "pip", "install", "--disable-pip-version-check", "pyinstaller", *extra],
                           capture_output=True, text=True)
        if r.returncode == 0 and have():
            return True
        if "externally-managed" not in (r.stderr + r.stdout):
            break
    log("Could not install PyInstaller:\n" + (r.stderr or r.stdout)[-1500:])
    return False


def build(dist=None, log=print):
    """Build the program; returns its path, or None if the build failed."""
    dist = dist or os.path.join(ROOT, "dist")
    if not ensure_pyinstaller(log=log):
        return None
    work = tempfile.mkdtemp(prefix="wtl-build-")
    try:
        log(f"Building {os.path.basename(output_path(dist))} for this system (a minute or two)...")
        r = subprocess.run([sys.executable, "-m", "PyInstaller", *pyinstaller_args(dist, work)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            log("The build failed:\n" + r.stderr[-3000:])
            return None
    finally:
        shutil.rmtree(work, ignore_errors=True)
    out = output_path(dist)
    size = os.path.getsize(out) if os.path.isfile(out) else sum(
        os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs)
    log(f"Built {out} ({size / 1e6:.0f} MB).")
    return out


def executable(out, platform=None):
    """The file to run inside what build() made (the .app's own executable on macOS)."""
    if (platform or sys.platform) == "darwin":
        return os.path.join(out, "Contents", "MacOS", MAC_NAME)
    return out


def check(out, seconds=12, log=print):
    """Start the built program from a folder of its own, with a short word list and no internet, and see that it
    opens and stays open, and keeps its save beside itself (T-1). Returns True if it did."""
    home = tempfile.mkdtemp(prefix="wtl-check-")
    folder = os.path.join(home, "Programs")
    os.makedirs(folder)
    target = os.path.join(folder, os.path.basename(out))
    (shutil.copytree if os.path.isdir(out) else shutil.copy2)(out, target)
    words = os.path.join(home, "words.txt")
    with open(words, "w", encoding="utf-8") as f:
        f.write("\n".join(["alpha", "beta", "gamma", "delta", "epsilon", "zeta"]) + "\n")
    env = dict(os.environ, HOME=home, USERPROFILE=home, WORD_TIERLIST_OFFLINE="1")
    p = subprocess.Popen([executable(target), "--wordlist", words, "--no-install", "--console"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    save = os.path.join(os.path.dirname(executable(target)) if not target.endswith(".app") else folder, "tierlist.db")
    end = time.time() + seconds
    while time.time() < end and p.poll() is None and not os.path.exists(save):
        time.sleep(0.5)
    time.sleep(3)                                          # (the window opens after the save is made)
    alive = p.poll() is None
    p.terminate()
    try:
        outtext, errtext = p.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()
        outtext, errtext = p.communicate()
    ok = alive and os.path.exists(save) and "Traceback" not in errtext
    log("The new program " + ("runs, and keeps its save beside itself." if ok else
                              f"did not run as it should:\n{outtext[-1500:]}\n{errtext[-1500:]}"))
    shutil.rmtree(home, ignore_errors=True)
    return ok


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build Word Tier List as a program for this system (PyInstaller).")
    ap.add_argument("--dist", help="where to put it (default: dist/ in the project)")
    ap.add_argument("--check", action="store_true", help="start the new program for a moment to make sure it runs")
    args = ap.parse_args(argv)
    out = build(args.dist)
    if out is None:
        return 1
    if args.check and not check(out):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
