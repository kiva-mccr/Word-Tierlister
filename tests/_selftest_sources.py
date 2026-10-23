import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""T-6, T-7: File > Source & Updates... From source: the page says where the program goes and whether one is up to
date; "Make the program" builds behind the progress window (faked here: a real build is _selftest_build.py), then
starts the new program and closes this window; a failed build says why and changes nothing. In the built program:
unpacking its source into a folder, and syncing a folder unpacked before (only the program's own files; your edits
kept as .bak), shown before it happens; then the folder opens and tierlist.py can start from it."""
import json, os, tempfile, time
os.environ["HOME"] = tempfile.mkdtemp()
import tkinter as tk
import tierlist as T
import sources
import standalone as S


def project():
    d = tempfile.mkdtemp(prefix="proj-")
    for f in ("tierlist.py", os.path.join("src", "a.py")):
        os.makedirs(os.path.join(d, os.path.dirname(f)), exist_ok=True)
        open(os.path.join(d, f), "w").write("x = 1\n")
    return d


def pump(root, n=6):
    for _ in range(n):
        root.update(); time.sleep(0.02)


def window():
    s = T.Store(os.path.join(tempfile.mkdtemp(), "s.db")); s.insert_words(["alpha", "beta", "gamma"])
    s.set_meta("dealt_asked", "1")
    root = tk.Tk()
    app = T.App(root, s, T.Definitions(s))
    pump(root, 10)
    return root, app


# the menu offers it from source only (T-7 adds the built program's side)
root, app = window()
labels = [it[1] for it in dict(app._menu_items())["File"] if it[0] == "command"]
assert "Source & Updates..." in labels
started, built = [], []
S.start = lambda path, popen=None: started.append(path)
# no program yet: one button that makes it
proj = project()
d = sources.SourceDialog(app, root_dir=proj); pump(root)
assert list(d.buttons) == ["Cancel", "Make the program"] and S.program_path(proj) in d.where.cget("text")
S.make_program = lambda root_dir, log: (built.append(root_dir), log("Building..."), S.program_path(root_dir))[2]
d.buttons["Make the program"].invoke(); pump(root, 2)
assert built == [proj] and started == [S.program_path(proj)]          # built, started, and this window closed
try:
    root.winfo_exists(); closed = False
except tk.TclError:
    closed = True
assert closed or not root.winfo_exists()

# built from exactly this source: start it straight away (or build again)
root, app = window()
open(S.program_path(proj), "w").write("program")
json.dump(dict(S.manifest(proj), made=time.time()), open(os.path.join(proj, S.SIDE_FILE), "w"))
d = sources.SourceDialog(app, root_dir=proj); pump(root)
assert list(d.buttons) == ["Cancel", "Build again", "Start it"] and "Nothing has changed" in d.state.cget("text")
d.buttons["Cancel"].invoke(); pump(root)
assert not d.alive() and root.winfo_exists()
# the source changed since: it says so and builds again
open(os.path.join(proj, "src", "a.py"), "a").write("y = 2\n")
d = sources.SourceDialog(app, root_dir=proj); pump(root)
assert list(d.buttons) == ["Cancel", "Make the program"] and "has changed" in d.state.cget("text")
# a failed build says why; this window stays open
shown = []
sources.show_error = lambda *a, **kw: shown.append((a, kw))
S.make_program = lambda root_dir, log: (log("The build failed:\nno compiler"), None)[1]
d.buttons["Make the program"].invoke(); pump(root, 2)
assert shown and "no compiler" in shown[0][1]["details"] and root.winfo_exists() and len(started) == 1
app.on_close()

# ---- T-7: the built program gives its source back -------------------------------------------------------------
def carried(files):
    """A folder like the one inside a built program: the files and their manifest."""
    d = tempfile.mkdtemp(prefix="carried-")
    for f, text in files.items():
        os.makedirs(os.path.join(d, os.path.dirname(f)), exist_ok=True)
        open(os.path.join(d, f), "w").write(text)
    json.dump(dict(S.manifest(d, list(files)), made=time.time()), open(os.path.join(d, S.MANIFEST), "w"))
    return d


v1 = carried({"tierlist.py": "v1\n", "src/a.py": "a1\n", "src/old.py": "old\n", "tests/run_tests.sh": "t\n"})
target = os.path.join(tempfile.mkdtemp(), "Word Tier List source")
plan = S.plan_unpack(v1, target)                                  # a new folder: everything added
assert plan["add"] == ["src/a.py", "src/old.py", "tests/run_tests.sh", "tierlist.py"] and not plan["update"]
S.unpack(v1, target, plan)
assert open(os.path.join(target, "src", "a.py")).read() == "a1\n" and os.path.exists(os.path.join(target, S.UNPACKED))
assert S.summary(S.plan_unpack(v1, target)) == "Everything there is already the same."
# yours stays: a save, its log, a file you edited; a newer program syncs the rest
open(os.path.join(target, "tierlist.db"), "w").write("my save")
open(os.path.join(target, "tierlist.py"), "w").write("my edit\n")
v2 = carried({"tierlist.py": "v2\n", "src/a.py": "a2\n", "src/new.py": "n\n", "tests/run_tests.sh": "t\n"})
plan = S.plan_unpack(v2, target)
assert plan["update"] == ["src/a.py", "tierlist.py"] and plan["add"] == ["src/new.py"] and plan["remove"] == ["src/old.py"]
assert plan["backup"] == ["tierlist.py"] and plan["same"] == 1, plan       # (only the edited one is backed up)
assert S.summary(plan) == "2 updated, 1 added, 1 removed (1 edited file kept as .bak first)."
S.unpack(v2, target, plan)
assert open(os.path.join(target, "tierlist.py")).read() == "v2\n" and open(os.path.join(target, "tierlist.py.bak")).read() == "my edit\n"
assert not os.path.exists(os.path.join(target, "src", "old.py")) and open(os.path.join(target, "src", "new.py")).read() == "n\n"
assert open(os.path.join(target, "tierlist.db")).read() == "my save" and not os.path.exists(os.path.join(target, "src", "a.py.bak"))
# a folder with the source in it but never unpacked into (a clone): a file that differs is kept as .bak
clone = tempfile.mkdtemp(prefix="clone-"); open(os.path.join(clone, "tierlist.py"), "w").write("clone\n")
assert S.plan_unpack(v2, clone)["backup"] == ["tierlist.py"]
# where it is found and where it goes
import sys as _sys
import shutil
meipass = tempfile.mkdtemp(prefix="meipass-")                    # (PyInstaller's folder in a running program)
shutil.copytree(v1, os.path.join(meipass, S.SOURCE_DIR))
_sys.frozen, _sys._MEIPASS = True, meipass
assert S.bundled_source() == os.path.join(meipass, S.SOURCE_DIR)
del _sys.frozen, _sys._MEIPASS
assert S.bundled_source() is None                                # (from source: nothing carried)
assert S.default_source_folder("/home/me/Programs/word-tierlist") == "/home/me/Programs/Word Tier List source"
assert S.default_source_folder("/Apps/Word Tier List.app/Contents/MacOS/Word Tier List") == "/Apps/Word Tier List source"

# the dialog in the built program: where, what it will do, then unpack, open the folder, offer to start tierlist.py
root, app = window()
target2 = os.path.join(tempfile.mkdtemp(), "Word Tier List source")
S.default_source_folder = lambda program=None: target2
opened, asked, popened = [], [], []
S.open_folder = lambda path, popen=None: opened.append(path)
S.python_for_source = lambda: "/usr/bin/python3"
sources.ask_yes_no = lambda *a, **kw: (asked.append(a), True)[1]
sources.subprocess.Popen = lambda args, **kw: popened.append(args)
d = sources.SourceDialog(app, source=v2, frozen=True); pump(root)
assert list(d.buttons) == ["Change folder...", "Cancel", "Unpack"] and target2 in d.where.cget("text")
assert "every file is added" in d.state.cget("text")
d.buttons["Unpack"].invoke(); pump(root)
assert sorted(os.listdir(os.path.join(target2, "src"))) == ["a.py", "new.py"] and opened == [target2]
assert asked and popened == [["/usr/bin/python3", os.path.join(target2, "tierlist.py")]]
open(os.path.join(target2, "src", "a.py"), "w").write("edited\n")
d = sources.SourceDialog(app, source=v2, frozen=True); pump(root)
assert "1 updated (1 edited file kept as .bak first)" in d.state.cget("text"), d.state.cget("text")
d.close()
# no Python on this computer: it says how to run the source instead of offering to start it
told = []
S.python_for_source = lambda: None
sources.show_message = lambda *a, **kw: told.append(a)
d = sources.SourceDialog(app, source=v2, frozen=True); pump(root)
d.buttons["Unpack"].invoke(); pump(root)
assert told and "install Python" in told[0][2] and len(popened) == 1
# built without its source: nothing to unpack
d = sources.SourceDialog(app, source=None, frozen=True); pump(root)
S.bundled_source = lambda: None
d.close(); d = sources.SourceDialog(app, frozen=True); pump(root)
assert list(d.buttons) == ["Close"]
d.close()

# ---- T-8: "Update to the newest version first", ticked to start with ------------------------------------------------
from constants import VERSION
def settle(d, n=20):
    for _ in range(n):
        if d.checked:
            break
        pump(root, 3)
    assert d.checked
release = {"version": "9.1.0", "tag": "v9.1.0", "source": "zip", "page": ""}
d = sources.SourceDialog(app, source=v2, frozen=True, check=lambda: None); settle(d)       # offline: says so
assert d.update_var.get() and "could not be reached" in d.update_line.cget("text")
d.close()
d = sources.SourceDialog(app, source=v2, frozen=True, check=lambda: dict(release, version=VERSION)); settle(d)
assert "the newest there is" in d.update_line.cget("text"); d.close()
# a newer one, unpacking: Unpack downloads it first and shows what unpacking it changes; the next Unpack does it
v3 = carried({"tierlist.py": "v3\n", "src/a.py": "a3\n", "tests/run_tests.sh": "t\n"})
fetched = []
S.fetch_source = lambda rel, folder, log: (fetched.append(rel["version"]), log("Downloading..."), v3)[2]
target3 = os.path.join(tempfile.mkdtemp(), "Word Tier List source"); S.default_source_folder = lambda program=None: target3
S.unpack(v2, target3)
d = sources.SourceDialog(app, source=v2, frozen=True, check=lambda: release); settle(d)
assert "Version 9.1.0 is out" in d.update_line.cget("text") and '"Unpack" downloads it' in d.update_line.cget("text")
d.buttons["Unpack"].invoke(); pump(root)
assert fetched == ["9.1.0"] and d.alive() and "9.1.0 downloaded" in d.update_line.cget("text")
assert "2 updated" in d.state.cget("text") and "1 removed" in d.state.cget("text"), d.state.cget("text")
d.buttons["Unpack"].invoke(); pump(root)
assert open(os.path.join(target3, "tierlist.py")).read() == "v3\n" and fetched == ["9.1.0"] and not d.alive()
# unticked: the version you have, nothing downloaded
d = sources.SourceDialog(app, source=v2, frozen=True, check=lambda: release); settle(d)
d.update_var.set(False); d._show_update()
assert "unticked, yours is used" in d.update_line.cget("text")
d.buttons["Unpack"].invoke(); pump(root)
assert fetched == ["9.1.0"] and open(os.path.join(target3, "tierlist.py")).read() == "v2\n"
# from source: Make the program builds the newer version (your files untouched); unticked, your source
made = []
S.make_program = lambda root_dir, log, release=None: (made.append(release and release["version"]), None)[1]
sources.show_error = lambda *a, **kw: None
proj2 = project()
d = sources.SourceDialog(app, root_dir=proj2, check=lambda: release); settle(d)
assert '"Make the program" builds the program from it' in d.update_line.cget("text")
d.buttons["Make the program"].invoke(); pump(root, 2)
d = sources.SourceDialog(app, root_dir=proj2, check=lambda: release); settle(d)
d.update_var.set(False); d.buttons["Make the program"].invoke(); pump(root, 2)
assert made == ["9.1.0", None], made
app.on_close()
print("SOURCES OK")
