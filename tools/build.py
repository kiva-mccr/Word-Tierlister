"""Build Word Tier List as a program for this computer's system (T-3), with PyInstaller.

    python tools/build.py            build into dist/ (installs PyInstaller first if it is missing)
    python tools/build.py --check    build, then start the new program for a moment to make sure it runs

What comes out (PyInstaller builds only for the system it runs on; T-8 covers the others):
    Linux     dist/word-tierlist            one file
    Windows   dist/word-tierlist.exe        one file, no console window
    macOS     dist/Word Tier List.app       an app bundle (one-file apps are not how macOS does it)

The program keeps its save beside itself (T-1: saves.app_dir), carries only the data it reads (T-2: src/bundle.py)
and its own source (T-7). The work is done by src/standalone.py, which File > Source & Updates uses too (T-6). WordNet stays an optional download, as from source: the build machine's own ~/nltk_data is never
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
sys.path.insert(0, os.path.join(ROOT, "src"))
from standalone import executable  # noqa: E402
import standalone  # noqa: E402


def build(dist=None, log=print):
    """Build the program into `dist` (default dist/ in the project), carrying its source inside (T-7); returns its
    path, or None if the build failed. (File > Source & Updates does the same and puts it next to tierlist.py: T-6.)"""
    return standalone.build(dist or os.path.join(ROOT, "dist"), ROOT, log)


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
