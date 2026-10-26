import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""T-1: where a built program keeps its save. From source: tierlist.py's folder; built: the folder the program sits
in (on macOS the one holding the .app), never the temporary folder a one-file build unpacks itself into; a
read-only one falls back to the per-user data folder. A built program restarts itself without a script name."""
import os, subprocess, sys, tempfile
import saves as S

ROOT = _paths.ROOT
# from source: tierlist.py's folder, as always
assert S.app_dir(frozen=False) == ROOT and os.path.exists(os.path.join(S.SOURCE_DIR, "tierlist.py"))
assert S.restart_args(["--db", "x.db"], frozen=False) == [os.path.join(ROOT, "tierlist.py"), "--db", "x.db"]
# built: the program's folder ...
tmp = tempfile.mkdtemp()
prog = os.path.join(tmp, "Programs", "word-tierlist")
os.makedirs(os.path.dirname(prog)); open(prog, "w").close()
assert S.app_dir(frozen=True, executable=prog) == os.path.dirname(prog)
assert S.restart_args(["--db", "x.db"], frozen=True) == ["--db", "x.db"]          # (the executable is the program)
# ... on macOS the folder holding the .app, not inside the bundle
mac = os.path.join(tmp, "Apps", "Word Tier List.app", "Contents", "MacOS", "word-tierlist")
os.makedirs(os.path.dirname(mac)); open(mac, "w").close()
assert S.program_dir(mac) == os.path.join(tmp, "Apps")
# ... and when that folder is read-only (Program Files), the per-user data folder, made if needed
home = os.path.join(tmp, "home")
for plat, env, want in (("win32", {"APPDATA": os.path.join(home, "AppData", "Roaming")},
                         os.path.join(home, "AppData", "Roaming", "Word Tier List")),
                        ("darwin", {}, os.path.join(home, "Library", "Application Support", "Word Tier List")),
                        ("linux", {}, os.path.join(home, ".local", "share", "word-tierlist")),
                        ("linux", {"XDG_DATA_HOME": os.path.join(home, "xdg")}, os.path.join(home, "xdg", "word-tierlist"))):
    got = S.app_dir(frozen=True, executable=prog, writable=lambda f: False, platform=plat, env=env, home=home)
    assert got == want and os.path.isdir(got), (plat, got)
assert S._writable(tmp) and not S._writable(os.path.join(tmp, "missing"))

# a stand-in built program, in its own process: sys.frozen set and sys.executable somewhere else, as PyInstaller
# does (its modules unpacked to a temporary folder): the save is made next to the program
code = f"""
import sys; sys.path[:0] = [{os.path.join(ROOT, 'src')!r}, {ROOT!r}]
sys.frozen = True; sys.executable = {prog!r}
import os; os.environ["HOME"] = {home!r}; os.environ["USERPROFILE"] = {home!r}
import saves
path, best, others = saves.choose_save(saves.app_dir())
print(saves.app_dir()); print(path)
"""
out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
assert out.returncode == 0, out.stderr
where, save = out.stdout.split()
assert where == os.path.dirname(prog) and save == os.path.join(os.path.dirname(prog), "tierlist.db"), out.stdout
print("APPDIR OK")
