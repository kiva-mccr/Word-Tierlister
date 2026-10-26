import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""T-3, T-6: src/standalone.py makes the program for this system with PyInstaller (tools/build.py and File > Source
& Updates use it). Always: the command line for each system (one file and no console on Linux / Windows, an app
bundle on macOS; only src/bundle.py's data; no CJK tokenizers; our own nltk hook, so the build machine's WordNet
stays out; the source carried inside); the source list, its manifest and whether a program is up to date. With
PyInstaller installed (it is never installed by the tests): a real build, its source inside it (taken back out,
unpacked and its core self-test run from there: T-7), then the new program run from a folder of its own."""
import importlib.util, json, os, sys, tempfile
sys.path.insert(0, os.path.join(_paths.ROOT, "tools"))
import build
import standalone as S

dist = os.path.join(tempfile.mkdtemp(), "dist")
for plat, out, onefile in (("linux", "word-tierlist", True), ("win32", "word-tierlist.exe", True),
                           ("darwin", "Word Tier List.app", False)):
    args = S.pyinstaller_args(dist, "/tmp/work", platform=plat, source="/tmp/work/source")
    assert S.output_path(dist, plat) == os.path.join(dist, out)
    assert S.program_path(_paths.ROOT, plat) == os.path.join(_paths.ROOT, out)     # (next to tierlist.py: T-6)
    assert ("--onefile" in args) == onefile and ("--onedir" in args) != onefile and "--windowed" in args
    sep = ";" if plat == "win32" else ":"
    added = [args[i + 1] for i, a in enumerate(args) if a == "--add-data"]
    assert any(a.endswith(f"large_en.msgpack.gz{sep}wordfreq/data") for a in added), added
    assert not any("_fr." in a for a in added) and "jieba" in args and "MeCab" in args
    assert f"/tmp/work/source{sep}source" in added                 # the source inside it (T-7 gives it back)
    assert args[args.index("--additional-hooks-dir") + 1] == os.path.join(_paths.ROOT, "tools", "hooks")
    assert args[args.index("--paths") + 1] == os.path.join(_paths.ROOT, "src")
    for mod in ("matplotlib", "PIL", "numpy"):                     # never packed, even when on the computer
        assert args[args.index(mod) - 1] == "--exclude-module", mod
# ... and the program works without them: importing it and its packages, ranking, WordNet when installed (a broken
# matplotlib on the build machine stopped a build: "No module named 'PIL'")
import bundle, subprocess
probe = f"""
import importlib.abc, sys
class Blocked(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in {set(bundle.UNUSED)!r}:
            raise ImportError("not packed: " + name)
sys.meta_path.insert(0, Blocked())
sys.path[:0] = [{os.path.join(_paths.ROOT, "src")!r}, {_paths.ROOT!r}]
import tierlist, wordfreq, rudeness, definitions
assert wordfreq.zipf_frequency("dog", "en") > 4
rudeness.wordnet()                                  # (None without nltk or its data; never an import error)
"""
r = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True)
assert r.returncode == 0, r.stderr[-2000:]
# a build much bigger than usual says what is in it (reported: 99 MB where 22 is usual), from PyInstaller's tables
work = tempfile.mkdtemp()
big, small = os.path.join(work, "big.so"), os.path.join(work, "small.py")
open(big, "wb").write(b"x" * 3_000_000); open(small, "wb").write(b"x" * 1_000_000)
open(os.path.join(work, "PKG-00.toc"), "w").write(repr(("p.pkg", {}, [("PYZ-00.pyz", big, "PYZ"),
                                                                       ("torch/lib/big.so", big, "BINARY")])))
open(os.path.join(work, "PYZ-00.toc"), "w").write(repr(("p.pyz", [("numpy.core", small, "PYMODULE"),
                                                                  ("numpy.linalg", small, "PYMODULE")])))
assert S.biggest_parts(work) == [("torch", 3.0), ("numpy", 2.0)] and S.biggest_parts(tempfile.mkdtemp()) == []
assert S.executable("/x/Word Tier List.app", "darwin") == "/x/Word Tier List.app/Contents/MacOS/Word Tier List"
assert S.executable("/x/word-tierlist", "linux") == "/x/word-tierlist"

# the source: what the zip ships and the program carries; a manifest tells whether anything changed since a build
files = S.source_files(_paths.ROOT)
assert "tierlist.py" in files and os.path.join("src", "standalone.py") in files and "requirements.txt" in files
assert not any(f.endswith((".db", ".log", ".pyc")) or f.startswith(".git" + os.sep) for f in files)
proj = tempfile.mkdtemp(prefix="proj-")                         # a small project of its own
for f in ("tierlist.py", os.path.join("src", "a.py"), "tierlist.db", "tierlist.txt", "README.md"):
    os.makedirs(os.path.join(proj, os.path.dirname(f)), exist_ok=True)
    open(os.path.join(proj, f), "w").write("x = 1\n")
assert S.source_files(proj) == ["README.md", "tierlist.py", os.path.join("src", "a.py")]   # (no save, no export)
m = S.manifest(proj)
assert set(m["files"]) == {"README.md", "tierlist.py", "src/a.py"}
assert not S.up_to_date(proj)                                   # no program yet
open(S.program_path(proj), "w").write("program")
json.dump(dict(m, made=0), open(os.path.join(proj, S.SIDE_FILE), "w"))
assert S.up_to_date(proj)                                       # built from the source as it is
open(os.path.join(proj, "src", "a.py"), "a").write("y = 2\n")
assert not S.up_to_date(proj)                                   # a file changed
open(os.path.join(proj, "src", "a.py"), "w").write("x = 1\n"); assert S.up_to_date(proj)
open(os.path.join(proj, "src", "b.py"), "w").write("z = 3\n"); assert not S.up_to_date(proj)   # one added
os.remove(os.path.join(proj, "src", "b.py")); os.remove(os.path.join(proj, "README.md"))
assert not S.up_to_date(proj)                                   # one removed
started = []
S.start(S.program_path(proj), popen=lambda args, **kw: started.append((args, kw)))
assert started[0][0] == [S.program_path(proj)] and started[0][1]["start_new_session"]   # (on its own)
hook = open(os.path.join(_paths.ROOT, "tools", "hooks", "hook-nltk.py")).read()
assert "datas = []" in hook                                       # (PyInstaller's own packs ~/nltk_data)

# the check never waits for ever: a program that leaves a process of its own running (as the Windows one-file
# program does) once kept it waiting on its output; its output goes to files and the whole tree is stopped
calls = []
class Started:
    pid = 42
    def terminate(self): calls.append("terminate")
    def wait(self, timeout=None): calls.append(("wait", timeout))
build.stop_tree(Started(), run=lambda args, **kw: calls.append(args), windows=True)
assert calls[0] == ["taskkill", "/F", "/T", "/PID", "42"] and calls[1] == ("wait", 10)
if sys.platform.startswith("linux"):
    import time
    fake = os.path.join(tempfile.mkdtemp(), "word-tierlist")
    with open(fake, "w") as f:
        f.write(f"#!{sys.executable}\nimport os, subprocess, sys, time\n"
                "open(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'tierlist.db'), 'w').close()\n"
                f"subprocess.Popen([{sys.executable!r}, '-c', 'import time; time.sleep(60)'])\n"
                "time.sleep(60)\n")
    os.chmod(fake, 0o755)
    began = time.time()
    assert build.check(fake, seconds=2, log=lambda *_: None)
    assert time.time() - began < 30

if importlib.util.find_spec("PyInstaller") is None:
    print("BUILD OK (PyInstaller is not installed: no real build; pip install pyinstaller to run one)")
else:
    out = build.build(dist, log=lambda *_: None)
    assert out and os.path.getsize(out) > 5e6, out
    from PyInstaller.archive.readers import CArchiveReader         # the source and its manifest are inside it
    inside = set(CArchiveReader(out).toc)
    assert "source/manifest.json" in inside and "source/tierlist.py" in inside and "source/src/app.py" in inside
    assert {f"icons/icon-{n}.png" for n in (16, 32, 256)} <= inside      # (IC-1: the window icon, where ui_style looks)
    assert {"typefaces/YoungSerif-Regular.ttf", "typefaces/AtkinsonHyperlegible-Bold.ttf"} <= inside   # (UI-73)
    built = json.load(open(os.path.join(dist, S.SIDE_FILE)))
    assert built["files"] == S.manifest(_paths.ROOT)["files"]      # (what File > Source & Updates compares)
    # T-7: the source comes back out of the program whole, unpacks, and runs on its own
    reader = CArchiveReader(out)
    carried = tempfile.mkdtemp(prefix="carried-")
    for name in (n for n in reader.toc if n.startswith(S.SOURCE_DIR + "/")):
        dest = os.path.join(carried, name[len(S.SOURCE_DIR) + 1:])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "wb").write(reader.extract(name))
    assert S.manifest(carried, list(built["files"]))["files"] == built["files"]     # every file, every byte
    unpacked = os.path.join(tempfile.mkdtemp(), "Word Tier List source")
    S.unpack(carried, unpacked)
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(unpacked, "tests", "_selftest.py")], capture_output=True, text=True,
                       timeout=600)
    assert r.returncode == 0 and "CORE OK" in r.stdout, r.stderr[-2000:]
    assert build.check(out, log=lambda *_: None)                   # opens, stays open, its save beside itself
    print(f"BUILD OK (built and ran {os.path.basename(out)}, {os.path.getsize(out) / 1e6:.0f} MB)")
