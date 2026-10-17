import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import os, tempfile
import tkinter as tk
from ui_motion import Animator, ease_out_cubic, lerp_color
import tierlist as T

# ---- pure helpers
assert ease_out_cubic(0) == 0 and ease_out_cubic(1) == 1
assert ease_out_cubic(-5) == 0 and ease_out_cubic(5) == 1                 # clamped
xs = [ease_out_cubic(i / 20) for i in range(21)]
assert all(b >= a for a, b in zip(xs, xs[1:])) and xs[10] > 0.8            # monotonic, fast start
assert lerp_color("#000000", "#FFFFFF", 0) == "#000000"
assert lerp_color("#000000", "#FFFFFF", 1) == "#FFFFFF"
assert lerp_color("#FF0000", "#0000FF", 0.5) == "#800080"
assert lerp_color("#FFB3C1", "#FBF7F4", 2) == "#FBF7F4"                    # clamped
assert lerp_color("#FFB3C1", "#FBF7F4", -1) == "#FFB3C1"

root = tk.Tk()
now = [0.0]
A = Animator(root, clock=lambda: now[0])

def pump(ms):
    """Advance the fake clock by `ms` and let Tk run its due 16 ms timers."""
    now[0] += ms / 1000.0
    root.update()

def real_wait(ms):
    root.after(ms, root.quit); root.mainloop()

# ---- frames: starts at 0, rises, ends exactly at 1.0, on_done once
frames, done = [], []
A.run("a", 100, frames.append, lambda: done.append(1))
assert frames == [0.0] and A.busy and not done
for _ in range(10):
    now[0] += 0.02; real_wait(18)
assert done == [1] and not A.busy
assert frames[-1] == 1.0 and frames.count(1.0) == 1
assert all(b >= a for a, b in zip(frames, frames[1:])) and len(frames) >= 3, frames

# ---- same key: the old animation is finished first
f1, d1, f2 = [], [], []
A.run("k", 200, f1.append, lambda: d1.append(1))
A.run("k", 200, f2.append)
assert f1[-1] == 1.0 and d1 == [1] and f2 == [0.0]
A.finish("k"); assert f2[-1] == 1.0 and not A.busy

# ---- different keys run side by side; finish_all ends both; finish on idle is a no-op
fa, fb = [], []
A.run("x", 200, fa.append); A.run("y", 200, fb.append)
assert A.busy
A.finish_all()
assert fa[-1] == 1.0 and fb[-1] == 1.0 and not A.busy
A.finish("nothing"); A.finish_all()

# ---- no timers left behind (a finished animation must not keep ticking)
before = len(root.tk.call("after", "info"))
A.run("z", 100, lambda p: None); A.finish_all()
assert len(root.tk.call("after", "info")) == before

# ---- reduce motion: no frames, end state immediately
A.reduce_motion = True
rf, rd = [], []
A.run("r", 250, rf.append, lambda: rd.append(1))
assert rf == [1.0] and rd == [1] and not A.busy
A.reduce_motion = False
zf = []
A.run("zero", 0, zf.append); assert zf == [1.0] and not A.busy               # ms=0 also jumps

# ---- a failing frame does not leave a timer looping (Tk reports the error; the animation is dropped)
errors = []
root.report_callback_exception = lambda *exc: errors.append(exc[1])
def boom(p):
    if p > 0: raise RuntimeError("frame failed")
A.run("boom", 100, boom)
now[0] += 0.05
real_wait(40)
assert errors and isinstance(errors[0], RuntimeError), errors
assert not A.busy and len(root.tk.call("after", "info")) == before

# ---- cancel_all stops without end states
cf = []
A.run("c", 200, cf.append); A.cancel_all()
assert cf == [0.0] and not A.busy
root.destroy()

# ---- App wiring: saved switch, View menu entry, key press finishes animations, close is clean
tmp = tempfile.mkdtemp()
s = T.Store(os.path.join(tmp, "m.db"))
s.insert_words(["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist", "w1", "w2"])
s.set_anchors(["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"])
root = tk.Tk()
app = T.App(root, s, T.Definitions(s)); root.update()
assert app.reduce_motion is False and app.anim.reduce_motion is False
from widgets import DropMenu
labels = DropMenu.labels(app.header.menus["View"])                       # the header's View menu (UI-10)
assert "Reduce motion" in labels, labels
got = []
app.anim.run("w", 200, got.append)
class E: keysym = "x"
app.on_key(E())
assert got[-1] == 1.0 and not app.anim.busy                                # key press finished it
app.motion_var.set(True); app.toggle_motion()
assert app.reduce_motion and app.anim.reduce_motion and s.get_meta("reduce_motion") == "1"
root.destroy()
# the choice is remembered on the next open
root = tk.Tk(); app2 = T.App(root, s, T.Definitions(s)); root.update()
assert app2.reduce_motion is True and app2.motion_var.get() is True and app2.anim.reduce_motion is True
app2.anim.run("p", 200, got.append); app2.on_close() if False else app2.anim.cancel_all()
root.destroy()
print("MOTION OK")
