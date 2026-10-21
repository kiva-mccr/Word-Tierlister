import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""T-3: tools/build.py makes the program for this system with PyInstaller. Always: the command line for each
system (one file and no console on Linux / Windows, an app bundle on macOS; only tools/bundle.py's data; no
CJK tokenizers; our own nltk hook, so the build machine's WordNet stays out). With PyInstaller installed (it is
never installed by the tests): a real build, then the new program run from a folder of its own."""
import importlib.util, os, sys, tempfile
sys.path.insert(0, os.path.join(_paths.ROOT, "tools"))
import build

dist = os.path.join(tempfile.mkdtemp(), "dist")
for plat, out, onefile in (("linux", "word-tierlist", True), ("win32", "word-tierlist.exe", True),
                           ("darwin", "Word Tier List.app", False)):
    args = build.pyinstaller_args(dist, "/tmp/work", platform=plat)
    assert build.output_path(dist, plat) == os.path.join(dist, out)
    assert ("--onefile" in args) == onefile and ("--onedir" in args) != onefile and "--windowed" in args
    sep = ";" if plat == "win32" else ":"
    added = [args[i + 1] for i, a in enumerate(args) if a == "--add-data"]
    assert any(a.endswith(f"large_en.msgpack.gz{sep}wordfreq/data") for a in added), added
    assert not any("_fr." in a for a in added) and "jieba" in args and "MeCab" in args
    assert args[args.index("--additional-hooks-dir") + 1] == os.path.join(_paths.ROOT, "tools", "hooks")
    assert args[args.index("--paths") + 1] == os.path.join(_paths.ROOT, "src")
assert build.executable("/x/Word Tier List.app", "darwin") == "/x/Word Tier List.app/Contents/MacOS/Word Tier List"
assert build.executable("/x/word-tierlist", "linux") == "/x/word-tierlist"
hook = open(os.path.join(_paths.ROOT, "tools", "hooks", "hook-nltk.py")).read()
assert "datas = []" in hook                                       # (PyInstaller's own packs ~/nltk_data)

if importlib.util.find_spec("PyInstaller") is None:
    print("BUILD OK (PyInstaller is not installed: no real build; pip install pyinstaller to run one)")
else:
    out = build.build(dist, log=lambda *_: None)
    assert out and os.path.getsize(out) > 5e6, out
    assert build.check(out, log=lambda *_: None)                   # opens, stays open, its save beside itself
    print(f"BUILD OK (built and ran {os.path.basename(out)}, {os.path.getsize(out) / 1e6:.0f} MB)")
