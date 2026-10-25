"""Zoom (UI-45, fixed after a report): on a screen too small for the zoomed contents, switching tabs or opening
and closing the definitions never loses the zoom; zoom out always makes things smaller; zoom in that cannot fit
says so; the main window's and Browse's zooms are separate and both survive a restart."""
import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import os, tempfile, time
tmp = tempfile.mkdtemp()
os.environ["HOME"] = os.path.join(tmp, "home"); os.makedirs(os.environ["HOME"])
import tkinter as tk
import tierlist as T
import app as A, browser as B
from fonts import font

db = os.path.join(tmp, "z.db")
s = T.Store(db)
words = [f"w{i:03d}" for i in range(80)]
s.insert_words(words + ["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"])
s.set_anchors(["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"])
for i, w in enumerate(words[:50]):
    s.place(w, i % 6)
A.usable_area = B.usable_area = lambda r: (0, 0, 1311, 691)        # a 1366 x 768 laptop

root = tk.Tk(); app = A.App(root, s, T.Definitions(s))
def pump(n=6, d=0.03):
    for _ in range(n):
        root.update(); time.sleep(d)
def body():
    return font("body").cget("size")
pump(10)
b0 = body()
# asked for: a zoom in that cannot fit is refused untried, from the first time: the window and the text never grow
# and snap back (_cannot_grow); the message shakes "no" (wiggle)
sizes, tried = [], []
real_apply = app._apply_zoom
app._apply_zoom = lambda z: (tried.append(z), real_apply(z))[1]
for _ in range(8):
    before = (app.zoom, root.winfo_height(), body())
    app.zoom_step(1); pump(2)
    if app.toast.cget("text") == app.ZOOM_FULL:
        assert (app.zoom, root.winfo_height(), body()) == before and tried[-1:] != [round(before[0] + 0.1, 1)], before
        break
assert app.toast.cget("text") == app.ZOOM_FULL
import json
from constants import VERSION
saved = json.loads(s.get_meta(app.ZOOM_CAPS))                       # (kept in the save for this screen)
assert saved["version"] == VERSION
assert app._cap_key(app._layout_key()) in saved and A.App._saved_caps(app) == app._zoom_cap
wiggled = app.anim.is_running(f"wiggle{id(app.toast)}")
assert wiggled or app.anim.reduce_motion                            # (the first refusal shakes too)
app._apply_zoom = real_apply
for _ in range(8):
    app.zoom_step(1); pump(2)
top, z_top = body(), app.zoom
assert top > b0 and z_top < 1.8                                     # it grew, but stopped where the screen is full
assert app.toast.cget("text") == "This is as big as fits on this screen"
assert app._zoom_cap.get(app._layout_key()) == round(z_top + app.ZOOM_STEP, 2)       # remembered: not tried again
assert s.get_meta("zoom") == str(z_top)
# switching tabs and back keeps the zoom (it used to shrink a step in a taller tab and never grow back)
for m in ("refine", "boundary", "place"):
    app.mode_var.set(m); app.on_mode_change(); pump(3)
    if m == "place":
        assert body() == top, (body(), top)
# opening the definitions when there is no room: the drawer stays folded while the window is fitted (it used to
# flash open at full height for each size tried)
seen = []
real_cs = app._content_size
app._content_size = lambda: (seen.append(app.def_frame.winfo_height() if app.def_frame.winfo_ismapped() else 0), real_cs())[1]
app.toggle_defs(True); app._content_size = real_cs
assert seen and max(seen) <= 1, seen
app.anim.finish_all(); pump(4); app.toggle_defs(False); app.anim.finish_all(); pump(6)
# the definitions: they may shrink things to fit while open; closing brings the zoom back
app.toggle_defs(True); pump(4); app.anim.finish_all(); pump(4)
assert body() <= top
app.toggle_defs(False); pump(4); app.anim.finish_all(); pump(6)
assert body() == top and app.zoom == z_top, (body(), top)
# zoom out is exactly one step, and never makes anything bigger, even while the definitions are open (what
# shows is the zoom or the biggest size that fits, whichever is smaller)
app.toggle_defs(True); pump(4); app.anim.finish_all(); pump(4)
for _ in range(3):
    shown, z = body(), app.zoom
    app.zoom_step(-1); pump(4)
    assert body() <= shown and app.zoom == round(z - app.ZOOM_STEP, 2), (body(), shown, app.zoom)
app.toggle_defs(False); pump(4); app.anim.finish_all(); pump(4)
assert abs(body() - round(12 * app.zoom)) <= 1                                  # closed: the zoom itself shows
z_main = app.zoom
# reported twice: after a zoom (out, or in a window bigger than normal) the contents grew past the zoom, and past
# what zoom in allows, whenever the definitions closed or the tab changed. The size that counts as "normal" is set
# by opening and by a zoom, and never re-measured smaller.
def cycle():
    sizes = set()
    for step in ("defs", "nodefs", "refine", "place", "defs", "boundary", "place", "nodefs"):
        if step in ("defs", "nodefs"):
            app.toggle_defs(step == "defs")
        else:
            app.mode_var.set(step); app.on_mode_change()
        pump(4); app.anim.finish_all(); pump(6)
        if not app.show_defs and app.mode == "place":
            sizes.add((body(), font("word").cget("size"), app.grow))
    return sizes
for steps in (-2, 1):
    for _ in range(abs(steps)):
        app.zoom_step(1 if steps > 0 else -1); pump(4)
    before = (body(), font("word").cget("size"), app.grow)
    assert cycle() == {before}, (steps, before)
w, h = root.winfo_width(), root.winfo_height()
root.geometry(f"{w + 200}x{h + 60}"); pump(10, 0.03)                           # a bigger window, by hand
app.zoom_step(-1); pump(4)
before = (body(), font("word").cget("size"), app.grow)
assert before[2] == 1.0 and cycle() == {before}, before
root.geometry(f"{w}x{h}"); pump(10, 0.03)
app.set_zoom(1.0); pump(4)
app.toast.hide(); app.anim.finish_all(); pump(2)
app.set_zoom(1.0); pump(2)                                                      # M-6: already 100%, Ctrl 0 again
assert app.zoom == 1.0 and app.toast.cget("text") == "Zoom 100%"                 # ...still says so
# Browse has its own zoom: changing it leaves the main window alone, and the other way round
main_body = body()
app.open_browser(); pump(6); bw = app.browsers[0]
bf = bw.f_body.cget("size")
bw.zoom_by(2); pump(3)
assert bw.f_body.cget("size") == bf + 2 and body() == main_body and s.get_meta("browse_zoom") == "2"
assert bw._toast.cget("text") == "Zoom 117%"                                    # M-6: Browse says its zoom too
bw.zoom_by(0); bw.zoom_by(0); pump(2); assert bw._toast.cget("text") == "Zoom 100%"   # ...also when unchanged
bw.zoom_by(2); pump(3)
app.zoom_step(-1); pump(4)
assert bw.f_body.cget("size") == bf + 2 and body() < main_body
z_main = app.zoom
bw.close(); app.on_close()
# both come back after a restart
s.close()
s = T.Store(db)
root = tk.Tk(); app = A.App(root, s, T.Definitions(s)); pump(10)
assert app.zoom == z_main and abs(body() - round(12 * z_main)) <= 1, (app.zoom, body())
app.open_browser(); pump(6)
assert app.browsers[0].zoom == 2
app.browsers[0].close(); app.on_close()

# UI-57 (asked for): the maximized window keeps a zoom of its own; maximizing or restoring brings back the one kept
# for it (the first maximize, before any is kept there, grows as UI-25 does); a zoom out of a grown window is a step
# down from what shows, not "as big as fits" (reported while testing it). (A real maximize under a window manager:
# checked by hand under openbox; here the state is faked.)
A.usable_area = lambda r: (0, 0, 1900, 1040)
s = T.Store(db); s.set_meta("zoom", "1.0"); s.db.execute("DELETE FROM meta WHERE key='zoom_max'"); s.db.commit()
root = tk.Tk(); app = A.App(root, s, T.Definitions(s)); pump(10)
state = {"max": False}
A.is_maximized = lambda w: state["max"]
def maximize(on, size):
    state["max"] = on; root.geometry(size); pump(4); app._apply_grow(); pump(4)
maximize(True, "1880x1020")
assert app.zoom == 1.0 and app.grow > 1                              # nothing kept yet: it grows
shown = round(app.zoom * app.grow, 1)
app.zoom_step(-1); pump(3)
assert app.zoom == round(shown - 0.1, 1) and app.grow == 1 and app.toast.cget("text") != app.ZOOM_FULL
z_max = app.zoom
assert s.get_meta("zoom_max") == str(z_max) and s.get_meta("zoom") == "1.0"      # kept for the maximized window
maximize(False, "1000x700")
assert app.zoom == 1.0                                                # restored: its own zoom again
app.zoom_step(1); pump(3)
z_normal = app.zoom
assert s.get_meta("zoom") == str(z_normal) and s.get_meta("zoom_max") == str(z_max)
maximize(True, "1880x1020")
assert app.zoom == z_max and app.grow == 1                            # shown as it was left, not grown
maximize(False, "1000x700")
assert app.zoom == z_normal
# a dialog open while the window is maximized (reported: its text grew with the zoom inside a window that kept its
# size, and was cut off; restoring put it right): it follows the new size, re-wrapped, fitted and centred again
from widgets import StyledDialog
from sizing import usable_area
maximize(True, "1880x1020")
for _ in range(4):
    app.zoom_step(1); pump(3)
z_big = app.zoom
maximize(False, "1000x700")
assert app.zoom == z_normal < z_big
long = ("It builds Word Tier List into one program for this computer, next to tierlist.py (a minute or two), then "
        "reopens as the program with the same save; Python is no longer needed to run it.")
dlg = StyledDialog(root, "Source & Updates", "Make this a standalone program?", long, animator=app.anim)
dlg.button("Not now", dlg.close); dlg.button("Make it", dlg.close, default=True)
dlg.show(); pump(4)
def fits():
    """Every label and button inside the dialog's window (nothing cut off at the bottom or the side)."""
    dlg.win.update_idletasks()
    w, h = dlg.win.winfo_width(), dlg.win.winfo_height()
    out, stack = [], [dlg.win]
    while stack:
        x = stack.pop(); stack.extend(x.winfo_children())
        if x is not dlg.win and x.winfo_ismapped():
            right = x.winfo_rootx() - dlg.win.winfo_rootx() + x.winfo_reqwidth()
            bottom = x.winfo_rooty() - dlg.win.winfo_rooty() + x.winfo_reqheight()
            if right > w + 1 or bottom > h + 1:
                out.append((x.winfo_class(), right, bottom, w, h))
    return out
assert not fits(), fits()
small = dlg.win.winfo_height()
maximize(True, "1880x1020"); pump(4)
assert app.zoom == z_big
assert not fits(), fits()                                            # (it was cut off here)
grew = dlg.win.winfo_height()
area = usable_area(dlg.win)
assert dlg.win.winfo_height() <= area[3] and dlg.win.winfo_width() <= area[2]     # still on the screen
cx = dlg.win.winfo_rootx() + dlg.win.winfo_width() // 2
assert abs(cx - (root.winfo_rootx() + root.winfo_width() // 2)) <= 2              # centred over the window
maximize(False, "1000x700"); pump(4)
assert not fits() and dlg.win.winfo_height() != grew and abs(dlg.win.winfo_height() - small) <= 2
dlg.close()
# the two zooms stay compatible (reported: the window opened with its contents bigger than when maximized, and
# maximizing shrank them): the usual window never shows more than the maximized one would
shown = lambda: round(app.font_scale * app.zoom * app.grow, 2)
assert not A.is_maximized(root)
app.set_zoom(s.meta_number("zoom_max", 1.0) + 0.2); pump(3)                  # usual zoom above the maximized one:
assert s.meta_number("zoom_max", 1.0) == s.meta_number("zoom", 1.0) == app.zoom      # that rises with it
maximize(True, "1880x1020")
app.set_zoom(round(app.zoom - 0.3, 1)); pump(3)                                # maximized zoom below the usual one:
assert s.meta_number("zoom", 1.0) == s.meta_number("zoom_max", 1.0) == app.zoom      # that comes down with it
big = shown()
maximize(False, "1000x700")
assert shown() <= big + 1e-9
# a big window that is not maximized grows its contents (UI-25), but never past what the maximized one shows
root.geometry("1880x1000"); pump(4); app._apply_grow(); pump(4)
assert not A.is_maximized(root) and shown() <= s.meta_number("zoom_max", 1.0) + 1e-9, (shown(), s.get_meta("zoom_max"))
app.on_close()
# a save whose usual zoom is above the maximized one (as left by earlier versions): it opens at the maximized one
s = T.Store(db); s.set_meta("zoom", "1.5"); s.set_meta("zoom_max", "1.0")
root = tk.Tk(); app = A.App(root, s, T.Definitions(s)); pump(10)
assert app.zoom == 1.0 and s.get_meta("zoom") == "1.0" and shown() <= 1.0
maximize(True, "1880x1020")
assert app.zoom == 1.0 and shown() >= 1.0 - 1e-9                              # maximizing never shrinks it
app.on_close()
print("ZOOM OK")
