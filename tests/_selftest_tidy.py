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
print("TIDY OK")
