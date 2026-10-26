import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""The definition pane opens tall enough to show every sense when the screen has room (UI-56), stays within the
screen when it has not, grows but never shrinks from word to word, and is back to its usual height when reopened."""
import os, tempfile
import tkinter as tk
import app as A
import tierlist as T

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


def shows_all(app):
    t = app.def_text
    return t.yview() == (0.0, 1.0)


# a tall screen: a long definition opens the pane in full, a short one after it keeps the height
root, app = make(1150)
base_h = root.winfo_height()
assert int(app.def_text.cget("height")) == app.DEF_LINES
app._render_defs(["word7"]); root.update()
assert int(app.def_text.cget("height")) == app.DEF_LINES      # short: the usual height
app.mem_defs["word8"] = LONG
app._render_defs(["word8"]); root.update()
tall = int(app.def_text.cget("height"))
assert tall > app.DEF_LINES and shows_all(app), (tall, app.def_text.yview())
assert root.winfo_height() > base_h and root.winfo_height() <= 1150, root.winfo_height()
assert root.winfo_y() + root.winfo_height() <= 1150, "grown past the bottom of the screen"
app._render_defs(["word7"]); root.update()
assert int(app.def_text.cget("height")) == tall               # never shrinks word to word (no jumping page)
app.toggle_defs(False); root.update(); app.toggle_defs(True); root.update()
assert int(app.def_text.cget("height")) == app.DEF_LINES      # reopened for a short word: the usual height
# F-2: opened for a long definition, the pane opens in full straight away (the folded pane keeps its text's width,
# so the text can say how tall it needs to be)
app.toggle_defs(False); root.update()
app.mem_defs["word9"] = LONG
app.def_words = ["word9"]
app.toggle_defs(True); root.update()
assert int(app.def_text.cget("height")) > app.DEF_LINES and shows_all(app), app.def_text.cget("height")
# reported after F-2: in a window made bigger (the contents grown, UI-25) the pane slid open at its full height over
# the word card and the tier buttons; it is shortened instead, and the centre keeps all its room
root.destroy()
root, app = make(1150)
app.toggle_defs(False); root.update()
root.geometry("1750x1140+0+0")
for _ in range(10):
    root.update(); root.after(30, root.quit); root.mainloop()
assert app.grow > 1, app.grow
app.mem_defs["word10"] = "\n".join(f"{i}. (noun) sense {i}" for i in range(1, 41))
app.def_words = ["word10"]
app.toggle_defs(True); root.update(); app.anim.finish_all(); root.update()
room = app.def_frame.winfo_rooty() - app.center.winfo_rooty()        # (the centre above the pane)
assert app.place_inner.winfo_reqheight() <= room, (app.place_inner.winfo_reqheight(), room)
assert app.grow > 1 and root.winfo_height() <= 1150
root.destroy()

# a definition arriving while the pane slides open (an online lookup, WordNet): fitted against the half-open pane it
# ended taller than fits, over the word card (seen as a flaky _selftest_sizing); the slide settles first now
root, app = make(560)
app.toggle_defs(False); root.update()
app.anim.reduce_motion = False
app.toggle_defs(True); root.update()                            # (sliding)
app.mem_defs[app.cur_word] = LONG
app._render_defs(); app.anim.finish_all(); root.update(); root.update_idletasks()
room = app.def_frame.winfo_rooty() - app.center.winfo_rooty()
assert app.place_inner.winfo_reqheight() <= room, (app.place_inner.winfo_reqheight(), room)
root.destroy()

# F-29 (asked for): comparing to anchors re-fits only when its question would cover something (the pane then eases
# shorter, App._fit_window), and once it ends, only if the pane was shortened for it
root, app = make(1150)
root.geometry("1700x1120")                                      # (room enough for either view)
for _ in range(10):                                             # (its definitions in and fitted first)
    root.update(); app.anim.finish_all()
fits = []
real_fit = app._fit_window
app._fit_window = lambda *a, **k: (fits.append(1), real_fit(*a, **k))[1]
app._toast_room = lambda: 0
app.start_compare(); root.update()
assert app.cmp and not fits                                     # (room enough: nothing moves)
app.cmp = None; app._render_place_state(); root.update()
assert not fits
app._toast_room = lambda: 2000                                  # (as if the question did not fit)
app.start_compare(); root.update()
assert len(fits) == 1
app._toast_room = lambda: 0
app._lines_before_cmp = app.def_frame.lines() + 2               # (the comparison shortened the pane)
app.cmp = None; app._render_place_state(); root.update()
assert len(fits) == 2                                           # (over: it may be as tall as before again)
root.destroy()

# a short screen: the pane takes what fits, the window stays on the screen and nothing else is clipped
root, app = make(560)
app.mem_defs["word8"] = LONG
app._render_defs(["word8"]); root.update()
h = int(app.def_text.cget("height"))
assert 3 <= h < 16 and root.winfo_height() <= 700, (h, root.winfo_height())
assert not shows_all(app)                                     # (it scrolls for the rest)
assert app.place_inner.winfo_reqheight() <= app.center.winfo_height(), "centre clipped"
root.destroy()
print("definition pane height OK")
