import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""UI-26: a smoke test that drives every mode and window the way a person would (keys, buttons, dialogs) and fails
on any error raised along the way. With Pillow installed it saves a screenshot of each stage (into SMOKE_SHOTS, or
a temporary folder: the path is printed) for a look by eye."""
import os, tempfile, time, types
os.environ["HOME"] = tempfile.mkdtemp()
import tkinter as tk
import tierlist as T

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None
SHOTS = os.environ.get("SMOKE_SHOTS") or tempfile.mkdtemp(prefix="smoke-")
os.makedirs(SHOTS, exist_ok=True)

WORDS = [f"w{i:04d}" for i in range(400)]
s = T.Store(os.path.join(tempfile.mkdtemp(), "smoke.db"))
s.insert_words(WORDS); s.set_anchors(WORDS[:6])
root = tk.Tk(); root.geometry("1300x850+0+0")
app = T.App(root, s, T.Definitions(s))
errors = []
root.report_callback_exception = lambda *exc: errors.append(exc)         # any error inside a Tk callback
shots = []


def pump(n=8):
    for _ in range(n):
        root.update(); time.sleep(0.02)


def key(ks, char="", state=0):
    app.on_key(types.SimpleNamespace(keysym=ks, char=char, time=None, state=state))
    app.on_key_release(types.SimpleNamespace(keysym=ks, time=None))
    pump(3)


def shot(name, win=None):
    pump(6); app.anim.finish_all(); pump(2)
    assert not errors, (name, errors)
    if ImageGrab is None:
        return
    w = win or root
    w.update_idletasks()
    box = (w.winfo_rootx(), w.winfo_rooty(), w.winfo_rootx() + w.winfo_width(), w.winfo_rooty() + w.winfo_height())
    path = os.path.join(SHOTS, f"{len(shots) + 1:02d}-{name}.png")
    ImageGrab.grab(box).save(path)
    shots.append(path)


pump(15)
shot("place")
# ---- Place new words: the number keys, Don't know, comparing to the anchors, a looked-up word, definitions
for k in "123456" * 4:
    key(k)
key("u")
key("space"); shot("comparing")
for ans in ("Up", "Down", "e"):
    if app.cmp:
        key(ans)
key("slash", "/")
for ch in "w0300":
    key(ch, ch)
shot("typing on the card")
key("Return"); assert app.cur_word == "w0300"
key("2")
key("d"); shot("definitions")
key("d")
# ---- the duel tabs: Refine, Boundary, and a conflict to resolve
for mode, answers in (("refine", ("Left", "Right", "Down", "s")), ("boundary", ("Left", "Right", "Down"))):
    app.mode_var.set(mode); app.on_mode_change(); pump(4)
    shot(mode)
    for a in answers * 2:
        key(a)
a, b, c = [r["word"] for r in s.list_words("", "Tier B", limit=3)[0]]
for x, y in ((a, b), (b, c), (c, a)):
    s.record_comparison(x, y, "a", "within")
app.after_external_change(); app._update_options(); pump(4)
assert s.stats()["conflicts"] > 0
app.mode_var.set("conflict"); app.on_mode_change(); pump(4)
shot("conflicts")
key("Left")
app.mode_var.set("place"); app.on_mode_change(); pump(4)
# ---- zoom, Tab between tabs, undo
key("plus", state=0x4); key("minus", state=0x4); key("0", state=0x4)
key("Tab"); key("ISO_Left_Tab", state=0x1)
for _ in range(3):
    key("BackSpace")
shot("after undo")
# ---- Browse: open, sort by a column both ways, select, close
app.open_browser(); pump(6); bw = app.browsers[0]
for col in ("word", "word", "games", "rating"):
    bw.tree.tk.call(bw.tree.heading(col, "command")); pump(3)
first = bw.tree.get_children()[0]; bw.tree.selection_set(first); pump(3)
shot("browse", bw.win)
bw.close()
# ---- the dialogs: anchors, queue randomness, keyboard shortcuts
for name, opener in (("anchors", app.edit_anchors), ("queue", app.edit_queue), ("shortcuts", app.edit_keys)):
    d = opener(); pump(6)
    dlg = getattr(d, "dlg", d)
    shot(name, dlg.win)
    dlg.close(); pump(2)
# ---- the header menus open and close
for name in app.header.menus:
    app.header.open_menu(name); pump(2)
    app.header.close(); pump(1)
shot("end")
assert not errors, errors
app.on_close()
print(f"SMOKE OK ({len(shots)} screenshots in {SHOTS})" if shots else "SMOKE OK (no Pillow: no screenshots)")
