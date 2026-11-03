import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""Switching tabs with the definitions pane open (reported: a vertical stutter, and from Refine within tier to
Boundary check the duel buttons seemed to flash): the pane's height is worked out, never tried on screen, every tab
shares one text size (Z-1), the duel cards fade over to the new pair, and the pane sliding open when a tab is switched
to ends at the height that fits."""
import os, tempfile, types
import tkinter as tk
import app as A
from definitions import Definitions
from store import Store
from theme import PALETTE

LONG = "\n".join(f"{i}. (noun) meaning {i} of a word, a fairly long line of text that goes on and on to wrap"
                 for i in range(1, 13))


def make(mode, screen=(1500, 800)):
    store = Store(os.path.join(tempfile.mkdtemp(), "s.db"))
    words = [f"word{i}" for i in range(60)]
    store.insert_words(words)
    store.set_anchors(words[:6])
    for i, w in enumerate(words[:48]):
        store.place(w, i % 6)
    store.set_meta("show_defs", "1")
    store.set_meta("mode", mode)
    A.usable_area = lambda r: (0, 0, screen[0], screen[1])
    root = tk.Tk()
    ap = A.App(root, store, Definitions(store))
    ap.mem_defs.update({w: LONG for w in words})
    root.update()
    ap._render_defs(); settle(ap)
    return root, ap


def settle(app):
    for _ in range(4):
        app.root.update()
        app.anim.finish_all()
    app.root.update()


# 1. the pane's lines are worked out from one measurement: what it predicts fills the window, less than a line spare
root, app = make("refine")
d = app.def_frame
for lines in (4, 9, 15):
    d.set_lines(lines); settle(app)
    fit = app._pane_lines()
    d.set_lines(fit); settle(app)
    spare = root.winfo_height() - sum(w.winfo_reqheight() for w in root.pack_slaves() if w is not app.center) - \
        app.pair_inner.winfo_reqheight() - app._room_below()
    assert 0 <= spare < d.line_height(), (lines, fit, spare)
for mode in ("boundary", "refine"):
    app._on_mode_switch(mode)
    settle(app)

# 2. switching between duel tabs: every pass of the fit that Tk draws shows the pane at one height and the duel cards
# in place (the fit used to draw each line count it tried: the page jumped and the cards blinked out)
seen = []
orig = root.update_idletasks


def watched():
    orig()
    seen.append((d.winfo_height(), d._inner.winfo_height(), app.duel.winfo_ismapped(), app.center.winfo_height()))


root.update_idletasks = watched
for mode in ("boundary", "refine", "boundary"):
    seen.clear()
    pane = (d.winfo_height(), d._inner.winfo_height())
    app._on_mode_switch(mode)
    assert seen, "the fit measured nothing"
    assert {s[:2] for s in seen} == {pane}, (mode, pane, sorted(set(seen)))
    assert all(s[2] for s in seen), "the duel cards went missing during the switch"
    settle(app)
root.update_idletasks = orig

# 3. every tab fits at one text size and one window size (Z-1; the duel tabs each had their own once, and the Place
# tab another)
sizes = set()
for mode in ("refine", "boundary", "conflict", "refine", "place", "boundary"):
    app._on_mode_switch(mode)
    settle(app)
    sizes.add((app._applied_scale, root.winfo_width(), root.winfo_height()))
    assert d.winfo_height() == d.natural_height(), (mode, d.winfo_height(), d.natural_height())
    assert root.winfo_height() <= 800
assert len(sizes) == 1, sizes
app.on_close()

# 4. a pane sliding open when a tab is switched to (a longer definition) ends at the height that fits: measured
# half-way open, it "fitted" with every line and ended past the bottom of the window
root, app = make("place", screen=(1500, 700))
d = app.def_frame
app.anim.reduce_motion = False
app._on_mode_switch("refine")
for _ in range(3):
    root.update()
settle(app)
assert d.winfo_height() == d.natural_height(), (d.winfo_height(), d.natural_height())
assert app.pair_inner.winfo_reqheight() <= d.winfo_rooty() - app.center.winfo_rooty()
assert d.winfo_rooty() + d.winfo_height() <= root.winfo_rooty() + root.winfo_height()

# 5. from one duel tab to another the cards fade into the page and the new pair fades in; a key press finishes it
left = app.duel.left
app._on_mode_switch("boundary")
assert app.anim.is_running(app.duel.anim_key)
old = left.cget("text")
for _ in range(200):                               # (until it is out of sight)
    root.update()
    if left.cget("text") != old or not app.anim.is_running(app.duel.anim_key):
        break
new = app.pair["left"]
app.anim.finish(app.duel.anim_key)
assert left.cget("text") == new and left._look == left._target(), (left.cget("text"), new, left._look)
app._on_mode_switch("refine")
assert app.anim.is_running(app.duel.anim_key)
app.on_key(types.SimpleNamespace(keysym="F12", time=None))          # (any key)
assert not app.anim.is_running(app.duel.anim_key)   # (finished, not hurried: the next pair waits on it)
settle(app)
# not from the Place tab (the whole page changes there), and never with Reduce motion
app._on_mode_switch("place"); settle(app)
app._on_mode_switch("refine")
assert not app.anim.is_running(app.duel.anim_key)
settle(app)
app.anim.reduce_motion = True
app._on_mode_switch("boundary")
assert not app.anim.is_running(app.duel.anim_key) and left.cget("text") == app.pair["left"]
app.on_close()

# 6. DuelCards on its own: half-way through the fade the old pair is faded towards the page; then the new one shows
r = tk.Tk()
from ui_motion import Animator
from widgets import DuelCards
anim = Animator(r)
duel = DuelCards(r, lambda side: None, animator=anim)
duel.pack(); duel.show("apple", "pear"); r.update()
frames = []
duel._anim.run = lambda key, ms, frame, done=None: frames.append(frame)
duel.show("fig", "plum", colors=("#FFD6A5", "#CAFFBF"), fade=True)
f = frames[0]
f(0.2)
assert duel.left.cget("text") == "apple" and duel.left._look[0] != duel.left._target()[0]
f(DuelCards.FADE_OUT)
assert duel.left.cget("text") == "fig" and duel.left._look[0] == PALETTE["bg"]      # (out of sight as it swaps)
f(1.0)
assert duel.left._look == duel.left._target() and duel.left.cget("bg") == "#FFD6A5"
r.destroy()
print("tab switch: no stutter, one size for every tab, cards fade over: OK")
