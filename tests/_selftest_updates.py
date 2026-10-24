import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""T-8: the newest release on GitHub (asked for nothing online here: GitHub's answers are stand-ins), downloading a
release's source ready to unpack or build from, `tools/build.py --all` (the Build programs workflow on GitHub,
through gh; stand-ins again) and the workflow itself (the names the README's download links and the program use)."""
import io, json, os, re, sys, tempfile, zipfile
import standalone as S
from constants import REPO, VERSION
import importlib.util

class R:
    def __init__(self, code=0, out=""):
        self.returncode, self.stdout, self.stderr = code, out, ""


# versions
assert S.version_tuple("v1.2.10") == (1, 2, 10) and S.version_tuple("1.0") == (1, 0)
assert S.newer({"version": "9.0.0"}) and not S.newer({"version": VERSION}) and not S.newer(None)
assert S.newer({"version": "1.10.0"}, "1.9.3")                     # (numbers, not text)
assert S.read_version(_paths.ROOT) == VERSION

# the newest release: GitHub's answer read; offline, an error or no release yet: None
answer = {"tag_name": "v9.1.0", "zipball_url": "https://api.github.com/x/zipball/v9.1.0", "html_url": "page"}
asked = []
def fetch(url, timeout=10):
    asked.append(url); return json.dumps(answer).encode()
offline = os.environ.pop("WORD_TIERLIST_OFFLINE")
try:
    r = S.latest_release(fetch)
    assert r == {"version": "9.1.0", "tag": "v9.1.0", "source": answer["zipball_url"], "page": "page"}, r
    assert asked == [f"https://api.github.com/repos/{REPO}/releases/latest"]
    def broken(url, timeout=10):
        raise OSError("no network")
    assert S.latest_release(broken) is None
    assert S.latest_release(lambda url, timeout=10: b'{"message": "Not Found"}') is None
finally:
    os.environ["WORD_TIERLIST_OFFLINE"] = offline
assert S.latest_release(fetch) is None and len(asked) == 1          # (the tests never go online)

# its source: GitHub's zip (one folder on top) unpacked with a manifest; nothing written outside the folder
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("kiva-Word-Tierlister-abc123/", "")
    z.writestr("kiva-Word-Tierlister-abc123/tierlist.py", "print('v9')\n")
    z.writestr("kiva-Word-Tierlister-abc123/src/constants.py", 'VERSION = "9.1.0"\n')
    z.writestr("kiva-Word-Tierlister-abc123/../evil.py", "x")
zipped = buf.getvalue()
folder = os.path.join(tempfile.mkdtemp(), "release")
got = S.fetch_source(r, folder, log=lambda t: None, fetch=lambda url, timeout=60: zipped)
m = S.read_manifest(got)
assert sorted(m["files"]) == ["src/constants.py", "tierlist.py"] and m["version"] == "9.1.0", m
assert not os.path.exists(os.path.join(os.path.dirname(folder), "evil.py"))
plan = S.plan_unpack(got, os.path.join(tempfile.mkdtemp(), "here"))  # (ready to unpack, as the program's own)
assert plan["add"] == ["src/constants.py", "tierlist.py"]
try:
    S.fetch_source(r, tempfile.mkdtemp(), log=lambda t: None, fetch=lambda url, timeout=60: (_ for _ in ()).throw(OSError("x")))
    raise AssertionError("should have failed")
except OSError as exc:
    assert "could not download version 9.1.0" in str(exc)

# make_program with a release: downloads it first (a step of its own), builds from it, puts it beside tierlist.py
proj = tempfile.mkdtemp()
built, steps = [], []
S.fetch_source = lambda release, folder, log: (os.makedirs(folder), folder)[1]
S.build = lambda dist, root, log: (built.append(root), open(S.output_path(dist), "w").write("p"),
                                   open(os.path.join(dist, S.SIDE_FILE), "w").write("{}"), S.output_path(dist))[3]
S.has_pyinstaller = lambda: True
assert S.make_program(proj, steps.append, release=r) == S.program_path(proj)
assert built[0].endswith("release") and "Downloading version 9.1.0" in steps[0]
assert S.make_program(proj, steps.append) and built[1] == proj           # (unticked: the source you have)
# the temporary folder on another disk than the project (reported: "[Errno 18] Invalid cross-device link"): a rename
# from there fails, so everything is moved by copying
import errno
real_rename, real_replace = os.rename, os.replace
def other_disk(a, b, *args, **kw):
    if str(a).startswith(tempfile.gettempdir()) != str(b).startswith(tempfile.gettempdir()):
        raise OSError(errno.EXDEV, "Invalid cross-device link")
    return real_rename(a, b, *args, **kw)
os.rename = os.replace = other_disk
proj = os.path.join(_paths.ROOT, "tests", "_cross_device_check")
os.makedirs(proj, exist_ok=True)
try:
    assert S.make_program(proj, steps.append) == S.program_path(proj) and os.path.exists(os.path.join(proj, S.SIDE_FILE))
finally:
    os.rename, os.replace = real_rename, real_replace
    import shutil
    shutil.rmtree(proj, ignore_errors=True)

# PyInstaller there but incomplete (reported: "No module named 'PyInstaller.utils'"): the check imports what a build
# uses, and a broken one is reinstalled, not taken as installed; both run from a neutral folder
import importlib
S2 = importlib.reload(S)                                    # (the real functions, not the stand-ins above)
calls = []
def fake_run(args, **kw):
    calls.append((args, kw.get("cwd")))
    code = args[-1] if args[1] == "-c" else None
    ok = {"import PyInstaller": 0, S2.PYINSTALLER_CHECK: 1 if len(calls) < 3 else 0}.get(code, 0)
    return R(ok)
S2.subprocess.run = fake_run
try:
    assert S2.ensure_pyinstaller("python", log=lambda t: None)
finally:
    S2.subprocess.run = importlib.import_module("subprocess").run
pip = [a for a, _ in calls if "pip" in a]
assert pip and "--force-reinstall" in pip[0], calls                  # (repaired, not "installed")
assert all(cwd for _, cwd in calls)

# tools/build.py --all: says what is missing, or runs the workflow, waits and fetches both programs into dist/
spec = importlib.util.spec_from_file_location("build_tool", os.path.join(_paths.ROOT, "tools", "build.py"))
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)


def fake_gh(logged_in=True, pushed=True, runs_ok=True):
    calls = []
    def run(args, **kw):
        calls.append(args)
        if args[:3] == ["gh", "auth", "status"]:
            return R(0 if logged_in else 1)
        if args[:2] == ["git", "rev-parse"]:
            return R(0, {"--abbrev-ref": "main\n", "HEAD": "abc123\n"}.get(args[2], "abc123\n" if pushed else "old\n"))
        if args[:3] == ["gh", "run", "list"]:
            return R(0, json.dumps([{"databaseId": 7, "headSha": "abc123", "status": "queued"}]))
        if args[:3] == ["gh", "run", "watch"]:
            return R(0 if runs_ok else 1, "X build failed")
        if args[:3] == ["gh", "run", "download"]:
            d = args[args.index("--dir") + 1]
            for name in S.RELEASE_ASSETS.values():
                os.makedirs(os.path.join(d, name)); open(os.path.join(d, name, name), "w").write("prog")
        return R(0)
    return run, calls


assert B.build_all(which=lambda n: None)[1].startswith("GitHub's command-line tool (gh) is not installed")
run, _ = fake_gh(logged_in=False)
assert "gh auth login" in B.build_all(run=run, which=lambda n: "/bin/gh")[1]
run, _ = fake_gh(pushed=False)
assert "push main first" in B.build_all(run=run, which=lambda n: "/bin/gh")[1]
run, calls = fake_gh(runs_ok=False)
assert "the builds failed" in B.build_all(run=run, which=lambda n: "/bin/gh", wait=lambda s: None, log=lambda t: None)[1]
dist = tempfile.mkdtemp()
run, calls = fake_gh()
paths, why = B.build_all(dist, run=run, which=lambda n: "/bin/gh", wait=lambda s: None, log=lambda t: None)
assert why is None and sorted(os.listdir(dist)) == sorted(S.RELEASE_ASSETS.values()), (why, os.listdir(dist))
assert ["gh", "workflow", "run", "build.yml", "--ref", "main"] in calls
assert os.access(os.path.join(dist, S.RELEASE_ASSETS["linux"]), os.X_OK)

# the workflow: on a button and on a v-tag; builds Linux and Windows under the names the release and README use
text = open(os.path.join(_paths.ROOT, ".github", "workflows", B.WORKFLOW), encoding="utf-8").read()
assert "workflow_dispatch" in text and 'tags: ["v*"]' in text and "gh release create" in text
for platform, asset in S.RELEASE_ASSETS.items():
    assert f"asset: {asset}" in text and f"built: dist/{S.output_name(platform)}" in text, asset
    assert f"releases/latest/download/{asset}" in open(os.path.join(_paths.ROOT, "README.md"), encoding="utf-8").read()
assert re.search(r"tools/build\.py --check", text) and "constants.VERSION" in text and "needs: build" in text
# T-10: the other form, Python, the builder and the file manager start without a built program's leftovers (its
# Tcl / Tk folders inside its temporary folder, gone once it closes: "Tk data/library directory ... could not be
# collected", reported), with the computer's own library path back
mei = "/tmp/_MEI00003d16rZjImv"
env = {"TCL_LIBRARY": mei + "/_tcl_data", "TK_LIBRARY": mei + "/_tk_data", "_PYI_ARCHIVE_FILE": "/x/prog",
       "LD_LIBRARY_PATH": mei, "LD_LIBRARY_PATH_ORIG": "/opt/lib", "HOME": "/home/me", "PATH": "/usr/bin"}
got = S.clean_env(env, frozen=True)
assert got == {"LD_LIBRARY_PATH": "/opt/lib", "HOME": "/home/me", "PATH": "/usr/bin",
               "PYINSTALLER_RESET_ENVIRONMENT": "1"}, got
got = S.clean_env({k: v for k, v in env.items() if k != "LD_LIBRARY_PATH_ORIG"}, frozen=True)
assert "LD_LIBRARY_PATH" not in got                                           # (it had none of its own)
src = S.clean_env({"TCL_LIBRARY": mei + "/_tcl_data", "TK_LIBRARY": tempfile.gettempdir(), "HOME": "/h"}, frozen=False)
assert src == {"TK_LIBRARY": tempfile.gettempdir(), "HOME": "/h"}, src     # (from source: only the dead paths go)
seen = []
S.start("/x/word-tierlist", popen=lambda args, **kw: seen.append(kw.get("env")))
S.open_folder(tempfile.gettempdir(), popen=lambda args, **kw: seen.append(kw.get("env"))) if not sys.platform.startswith("win") else None
S.start_source("/x/src", "/usr/bin/python3", popen=lambda args, **kw: seen.append(kw.get("env")))
assert seen and all(e is not None and not any(k.startswith("_PYI_") for k in e) for e in seen)
print("UPDATES OK")
