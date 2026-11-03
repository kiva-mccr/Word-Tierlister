import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""The definitions pane fills the room the page leaves (Z-1, asked for: always as much pane as fits; nothing on the
page resizes the window or its text): a long or short definition, opening and closing it, comparing to anchors and
switching tabs never change the window's size or the text size; the pane eases to the room left and scrolls the rest,
and nothing it holds covers the page."""
import os, tempfile
import tkinter as tk
import app as A
import tierlist as T
from fonts import font

LONG = "\n".join(f"{i}. (noun) sense number {i} of a word with very many meanings indeed" for i in range(1, 17))
SHORT = "1. (noun) a short one"


def make(screen_h):
    store = T.Store(os.path.join(tempfile.mkdtemp(), "s.db"))
    words = [f"word{i}" for i in range(12)]
    store.insert_words(words)
    store.set_anchors(words[:6])
    A.usable_area = lambda r: (0, 0, 1800, screen_h)
    root = tk.Tk()
    ap = A.App(root, store, T.Definitions(store))
    ap.anim.reduce_motion = True
    ap.mem_defs.update({w: SHORT for w in words})
    root.update()
    ap.toggle_defs(True); root.update()
    return root, ap


def settle(root, app, n=6):
    for _ in range(n):
        root.update(); app.anim.finish_all()
    root.update_idletasks()


def shows_all(app):
    return app.def_text.yview() == (0.0, 1.0)


def state(root, app):
    """What must never change from the page's own doings: the window's size and the text size."""
    return root.winfo_width(), root.winfo_height(), font("word").cget("size"), font("body").cget("size")


def page_clear(app):
    """The view on screen is not covered by the pane (the room for a message kept under it)."""
    inner = app.place_inner if app.mode == "place" else app.pair_inner
    room = app.def_frame.winfo_rooty() - app.center.winfo_rooty()
    return inner.winfo_reqheight() <= room, (inner.winfo_reqheight(), room)


# a tall screen: the pane fills the room; long and short definitions change nothing but what it shows
root, app = make(1150)
settle(root, app)
before, lines = state(root, app), app.def_frame.lines()
assert lines == app._pane_lines() and lines > app.DEF_LINES_MIN, (lines, app._pane_lines())
assert app.def_frame.winfo_rooty() + app.def_frame.winfo_height() <= app.center.winfo_rooty() + root.winfo_height()
app.mem_defs["word8"] = LONG
app._render_defs(["word8"]); settle(root, app)
assert state(root, app) == before and app.def_frame.lines() == lines
app._render_defs(["word7"]); settle(root, app)
assert state(root, app) == before and app.def_frame.lines() == lines and shows_all(app)
ok, why = page_clear(app); assert ok, why
# opening and closing it never resizes the window or the text (its room counts while it is shut)
app.toggle_defs(False); settle(root, app)
assert state(root, app) == before and not app.def_frame.winfo_manager()
app.toggle_defs(True); settle(root, app)
assert state(root, app) == before and app.def_frame.lines() == lines
# comparing to anchors: the pane eases shorter for the taller view, and back as tall when it ends; nothing else moves
app.start_compare(); settle(root, app)
assert app.cmp and state(root, app) == before
cmp_lines = app.def_frame.lines()
assert app.DEF_LINES_MIN <= cmp_lines < lines, (cmp_lines, lines)
ok, why = page_clear(app); assert ok, why
app.cmp = None; app._render_place_state(); settle(root, app)
assert state(root, app) == before and app.def_frame.lines() == lines
# every tab: the same window and text size, the pane filling what each leaves
for mode in ("refine", "conflict", "place"):
    app.mode_var.set(mode); app.on_mode_change(); settle(root, app)
    assert state(root, app) == before, (mode, state(root, app), before)
    assert app.def_frame.lines() == app._pane_lines(), mode
    ok, why = page_clear(app); assert ok, (mode, why)
root.destroy()

# the pane eases there (a comparison): several heights shown on the way, never a jump
root, app = make(1150)
root.geometry("1500x1000+0+0")                                  # (room for more than its shortest: a Mac's screen
for _ in range(10):                                             # held the window it opened with at its minimum;
    root.update(); root.after(40, root.quit); root.mainloop()   # the contents re-grow 80 ms after a resize)
settle(root, app)
lines = app.def_frame.lines()
app.anim.reduce_motion = False
heights, tick = [], [app.anim.clock()]
real_clock, app.anim.clock, app.anim._real = app.anim.clock, (lambda: tick[0]), False   # (the animator's clock in
app.start_compare()                                             # steps: a slow Mac's runner drew one frame of it)
for _ in range(30):
    root.after(20, root.quit); root.mainloop()                  # (each frame's timer)
    heights.append(app.def_frame.winfo_reqheight()); tick[0] += 0.01
app.anim.clock, app.anim._real = real_clock, True
app.anim.finish_all(); root.update()
assert app.def_frame.lines() < lines, (lines, app.def_frame.lines(), root.winfo_height())
assert len(set(heights)) > 3 and all(b <= a for a, b in zip(heights, heights[1:])), heights
root.destroy()

# a window made bigger (the contents grown, UI-25): the pane opens into the room kept for it, over nothing
root, app = make(1150)
app.toggle_defs(False); root.update()
root.geometry("1750x1140+0+0")
for _ in range(10):
    root.update(); root.after(30, root.quit); root.mainloop()
assert app.grow > 1, app.grow
grown = state(root, app)
app.mem_defs["word10"] = "\n".join(f"{i}. (noun) sense {i}" for i in range(1, 41))
app.def_words = ["word10"]
app.toggle_defs(True); settle(root, app)
ok, why = page_clear(app); assert ok, why
assert state(root, app) == grown and app.grow > 1
app.start_compare(); settle(root, app)
ok, why = page_clear(app); assert ok, why
assert state(root, app) == grown                               # (the comparison fits the grown window too)
root.destroy()

# a definition arriving while the pane slides open (an online lookup, WordNet) changes nothing over the page
root, app = make(560)
app.toggle_defs(False); root.update()
app.anim.reduce_motion = False
app.toggle_defs(True); root.update()                            # (sliding)
app.mem_defs[app.cur_word] = LONG
app._render_defs(); settle(root, app)
ok, why = page_clear(app); assert ok, why
root.destroy()

# a short screen: the pane keeps at least its shortest, scrolls the rest, the window stays on the screen
root, app = make(560)
app.mem_defs["word8"] = LONG
app._render_defs(["word8"]); settle(root, app)
h = app.def_frame.lines()
assert app.DEF_LINES_MIN <= h < 16 and root.winfo_height() <= 560, (h, root.winfo_height())
assert not shows_all(app)                                     # (it scrolls for the rest)
ok, why = page_clear(app); assert ok, why
app.start_compare(); settle(root, app)
assert app.def_frame.lines() >= app.DEF_LINES_MIN and root.winfo_height() <= 560
ok, why = page_clear(app); assert ok, why
root.destroy()
print("definition pane height OK")
