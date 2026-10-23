import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""T-6: File > Source & Updates... from source: the page says where the program goes and whether one is up to
date; "Make the program" builds behind the progress window (faked here: a real build is _selftest_build.py), then
starts the new program and closes this window; a failed build says why and changes nothing."""
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
print("SOURCES OK")
