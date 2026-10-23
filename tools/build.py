"""Build Word Tier List as a program for this computer's system (T-3), with PyInstaller.

    python tools/build.py            build into dist/ (installs PyInstaller first if it is missing)
    python tools/build.py --check    build, then start the new program for a moment to make sure it runs
    python tools/build.py --all      Linux and Windows at once, on GitHub (T-8): runs the "Build programs" workflow
                                     (.github/workflows/build.yml) on the pushed source, waits, and fetches
                                     word-tierlist-linux and word-tierlist-windows.exe into dist/

--all needs the code pushed to GitHub and GitHub's command-line tool, logged in (gh auth login); without them
it says what is missing and builds for this computer only. A release (the README's download links) is published
by pushing a tag v<VERSION>: the same workflow then attaches both programs to it.

What comes out (PyInstaller builds only for the system it runs on; T-8 covers the others):
    Linux     dist/word-tierlist            one file
    Windows   dist/word-tierlist.exe        one file, no console window
    macOS     dist/Word Tier List.app       an app bundle (one-file apps are not how macOS does it)

The program keeps its save beside itself (T-1: saves.app_dir), carries only the data it reads (T-2: src/bundle.py)
and its own source (T-7). The work is done by src/standalone.py, which File > Source & Updates uses too (T-6). WordNet stays an optional download, as from source: the build machine's own ~/nltk_data is never
packed in (PyInstaller's nltk hook would do that; tools/hooks/hook-nltk.py replaces it).
"""
import argparse
import json
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


WORKFLOW = "build.yml"


def _run(args, run=subprocess.run):
    """(return code, output) of a command; 127 when it cannot be started."""
    try:
        r = run(args, capture_output=True, text=True, cwd=ROOT)
    except OSError as exc:
        return 127, str(exc)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def remote_ready(run=subprocess.run, which=shutil.which):
    """(branch, commit) to build on GitHub, or (None, why not): gh installed and logged in, the commit pushed."""
    if not which("gh"):
        return None, "GitHub's command-line tool (gh) is not installed: https://cli.github.com"
    if _run(["gh", "auth", "status"], run)[0] != 0:
        return None, "gh is not logged in to GitHub: run `gh auth login` first"
    code, branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], run)
    code2, head = _run(["git", "rev-parse", "HEAD"], run)
    if code or code2 or branch.strip() == "HEAD":
        return None, "this is not a git checkout on a branch, so there is no pushed source to build"
    code, pushed = _run(["git", "rev-parse", "@{u}"], run)
    if code or pushed.strip() != head.strip():
        return None, f"commit and push {branch.strip()} first (git push): the builds use the source on GitHub"
    return (branch.strip(), head.strip()), None


def build_all(dist=None, log=print, run=subprocess.run, which=shutil.which, wait=time.sleep):
    """Run the "Build programs" workflow on GitHub for the pushed branch, wait for it, and fetch its programs into
    `dist`: their paths, or (None, why not)."""
    dist = dist or os.path.join(ROOT, "dist")
    ready, why = remote_ready(run, which)
    if not ready:
        return None, why
    branch, head = ready
    log(f"Starting the Build programs workflow on GitHub for {branch} ({head[:7]})...")
    code, out = _run(["gh", "workflow", "run", WORKFLOW, "--ref", branch], run)
    if code:
        return None, ("GitHub would not start the workflow (it must be on the repository's default branch to be "
                      "started this way):\n" + out.strip())
    run_id = None
    for _ in range(30):                              # (the run shows up a few seconds after it is asked for)
        code, out = _run(["gh", "run", "list", "--workflow", WORKFLOW, "--branch", branch, "--event",
                          "workflow_dispatch", "--limit", "5", "--json", "databaseId,headSha,status"], run)
        found = [r for r in (json.loads(out) if code == 0 and out.strip().startswith("[") else [])
                 if r.get("headSha") == head and r.get("status") != "completed"]
        if found:
            run_id = str(found[0]["databaseId"])
            break
        wait(2)
    if not run_id:
        return None, "the workflow was started but its run did not show up; see the Actions tab on GitHub"
    log(f"Building on Linux and Windows (run {run_id}; about 5 minutes)...")
    code, out = _run(["gh", "run", "watch", run_id, "--exit-status", "--interval", "15"], run)
    if code:
        return None, f"the builds failed; see `gh run view {run_id} --log-failed`:\n" + out.strip()[-1500:]
    got = tempfile.mkdtemp(prefix="wtl-runs-")
    code, out = _run(["gh", "run", "download", run_id, "--dir", got], run)
    if code:
        return None, "the programs could not be fetched:\n" + out.strip()
    os.makedirs(dist, exist_ok=True)
    paths = []
    for base, _dirs, files in os.walk(got):          # (one folder per program: flatten them into dist/)
        for f in files:
            target = os.path.join(dist, f)
            shutil.move(os.path.join(base, f), target)
            if not f.endswith(".exe"):
                os.chmod(target, 0o755)
            paths.append(target)
    shutil.rmtree(got, ignore_errors=True)
    for p in sorted(paths):
        log(f"  {p}")
    return sorted(paths), None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build Word Tier List as a program for this system (PyInstaller).")
    ap.add_argument("--dist", help="where to put it (default: dist/ in the project)")
    ap.add_argument("--check", action="store_true", help="start the new program for a moment to make sure it runs")
    ap.add_argument("--all", action="store_true", help="Linux and Windows at once, on GitHub (needs gh and a push)")
    args = ap.parse_args(argv)
    if args.all:
        paths, why = build_all(args.dist)
        if paths:
            return 0
        print(f"Not built on GitHub: {why}.\nBuilding for this computer only.")
    out = build(args.dist)
    if out is None:
        return 1
    if args.check and not check(out):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
