import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import inspect, os, tempfile
import tierlist as T

tmp = tempfile.mkdtemp()
s = T.Store(os.path.join(tmp, "t.db"))
assert "progress" not in inspect.signature(T.Store.reshuffle).parameters
assert "first" not in inspect.signature(T.App.edit_anchors).parameters

# stats on a fresh store, then after insert
st = s.stats()
assert st["total"] == 0, st
s.insert_words(["alpha", "beta", "gamma", "delta", "epsilon"])
assert s.stats()["total"] == 5 and s.stats()["placed"] == 0
assert s._total == 5

# pick_within focus branch
assert s.pick_within(focus="alpha") is None            # unplaced
s.place("alpha", 2)
assert s.pick_within(focus="alpha") is None            # tier has <2 words
assert s.pick_within(focus="nope") is None             # unknown word
s.place("beta", 2); s.place("gamma", 2)
for _ in range(10):
    a, b, t = s.pick_within(focus="alpha")
    assert a == "alpha" and b in ("beta", "gamma") and t == 2
r = s.pick_within()
assert r and r[2] == 2 and r[0] != r[1]
s.record_comparison("alpha", "beta", "a", "within")
s.record_comparison("alpha", "gamma", "a", "within")
assert s.pick_within(focus="alpha") is None            # faced everyone in its tier
print("store parts OK")

# UI: no anchors -> _startup opens anchors dialog
import tkinter as tk
root = tk.Tk()
s2 = T.Store(os.path.join(tmp, "u.db"))
s2.insert_words(["one", "two", "three"])
called = []
orig = T.App.edit_anchors
T.App.edit_anchors = lambda self: called.append(1)
app = T.App(root, s2, T.Definitions(s2))
root.update()
root.after(500, root.quit); root.mainloop()
assert called == [1], called
T.App.edit_anchors = orig
root.destroy()

# found in a review: tierlist.md beside tierlist.py is the program's note (R-1), and a Markdown export saved there
# would overwrite it: it goes to tierlist-export.md instead (and git tracks the note, never the export)
import saves, app as A
assert saves.is_code_note(os.path.join(_paths.ROOT, "tierlist.md"))          # (the real note)
folder = tempfile.mkdtemp()
open(os.path.join(folder, "tierlist.py"), "w").write("")
open(os.path.join(folder, "tierlist.md"), "w").write("# My tier list\n\nS: apple\n")
assert not saves.is_code_note(os.path.join(folder, "tierlist.md"))           # (an export of yours: free to replace)
open(os.path.join(folder, "tierlist.md"), "w").write("# `tierlist.py`\n\nThe program's entry point.\n")
assert saves.is_code_note(os.path.join(folder, "tierlist.md"))
assert not saves.is_code_note(os.path.join(folder, "other.md"))
root = tk.Tk(); root.withdraw()
s3 = T.Store(os.path.join(tempfile.mkdtemp(), "e.db")); s3.insert_words(["apple"])
app3 = A.App(root, s3, T.Definitions(s3))
A.use_themed = lambda r: False
A.filedialog.asksaveasfilename = lambda **kw: os.path.join(folder, "tierlist.md")
app3.export(); root.update()
assert open(os.path.join(folder, "tierlist.md")).read().startswith("# `tierlist.py`")         # (the note kept)
assert os.path.exists(os.path.join(folder, "tierlist-export.md"))
assert "tierlist-export.md" in app3.toast.cget("text")
app3.on_close()
print("TIDY OK")
