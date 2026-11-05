"""Zoom (UI-45, fixed after a report): on a screen too small for the zoomed contents, switching tabs, comparing or
opening and closing the definitions never changes the text or the window (Z-1); zoom out always makes things smaller; zoom in that cannot fit
says so; the main window's and Browse's zooms are separate and both survive a restart."""
import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import os, tempfile, time
tmp = tempfile.mkdtemp()
os.environ["HOME"] = os.path.join(tmp, "home"); os.makedirs(os.environ["HOME"])
os.environ["USERPROFILE"] = os.environ["HOME"]           # (Windows reads home from USERPROFILE)
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
A.usable_area = B.usable_area = lambda r: (0, 0, 1500, 960)        # a screen with room for a zoom step or two
# (Z-1: a 1366 x 768 laptop, every view and the pane counted, has no room for 100% now; UI-73 had left it no more)

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
started, real_run = [], app.anim.run                                # (a slow Mac's pump let a short shake end: count its start)
app.anim.run = lambda key, *a, **k: (started.append(key), real_run(key, *a, **k))[1]
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
assert "%dx%d" % app._layout_key() in saved and A.App._saved_caps(app) == app._zoom_cap
wiggled = f"wiggle{id(app.toast)}" in started
app.anim.run = real_run
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
# Z-1: opening the definitions never changes the text or the window (the room for its shortest is kept) and
# closing them neither; nor does a comparison to anchors
size = (root.winfo_width(), root.winfo_height())
app.toggle_defs(True); pump(4); app.anim.finish_all(); pump(4)
assert body() == top and (root.winfo_width(), root.winfo_height()) == size
app.start_compare(); pump(4); app.anim.finish_all(); pump(4)
assert body() == top and (root.winfo_width(), root.winfo_height()) == size and app.cmp
app.cmp = None; app._render_place_state(); pump(4)
app.toggle_defs(False); pump(4); app.anim.finish_all(); pump(6)
assert body() == top and app.zoom == z_top and (root.winfo_width(), root.winfo_height()) == size
# zoom out is exactly one step, and never makes anything bigger, even while the definitions are open (what
# shows is the zoom or the biggest size that fits, whichever is smaller)
app.toggle_defs(True); pump(4); app.anim.finish_all(); pump(4)
for _ in range(3):
    shown, z = body(), app.zoom
    app.zoom_step(-1); pump(4)
    assert body() <= shown and app.zoom == round(z - app.ZOOM_STEP, 2), (body(), shown, z, app.zoom)
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

# F-52 (asked for, replacing UI-57's zoom of its own for the maximized window): maximizing or restoring keeps the text
# the size it shows; the page only gets more room (the re-fit at a new text size took ~0.2 s and jarred). (A real
# maximize under a window manager: recorded under openbox; here the state is faked.)
A.usable_area = lambda r: (0, 0, 1900, 1040)
s = T.Store(db); s.set_meta("zoom", "1.0"); s.db.execute("DELETE FROM meta WHERE key IN ('zoom_max', 'monitor_zooms')")
s.db.commit()
root = tk.Tk(); app = A.App(root, s, T.Definitions(s)); pump(10)
state = {"max": False}
A.is_maximized = lambda w: state["max"]
shown = lambda: round(app.font_scale * app.zoom * app.grow, 2)
def maximize(on, size):
    state["max"] = on; root.geometry(size); pump(4); app._apply_grow(); pump(4)
# a bigger window by hand still grows its contents (UI-25); maximizing it keeps that size, restoring too
root.geometry("1880x1020"); pump(4); app._apply_grow(); pump(4)
assert app.grow > 1, (app.grow, app._ref_size, app._window_size(), app._maximized, state)
before = (shown(), body())
maximize(True, "1880x1020"); assert (shown(), body()) == before
maximize(False, "1880x1020"); assert (shown(), body()) == before
root.geometry("1000x700"); pump(4); app._apply_grow(); pump(4)
assert app.grow == 1
before = (shown(), body())
maximize(True, "1880x1020")
assert (shown(), body()) == before and app.zoom == 1.0              # the same text, more room
app.zoom_step(-1); pump(3)                                           # a zoom while maximized is the one zoom
assert app.zoom == 0.9 and s.get_meta("zoom") == "0.9" and s.get_meta("zoom_max") is None
before = (shown(), body())
maximize(False, "1000x700")
assert (shown(), body()) == before                                   # restored: still the same text
# a dialog open while the zoom changes (reported: its text grew inside a window that kept its size, and was cut
# off): it follows the new size, re-wrapped, fitted and centred again
from widgets import StyledDialog
from sizing import usable_area
long = ("It builds Word Tierlister into one program for this computer, next to tierlist.py (a minute or two), then "
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
for _ in range(3):
    app.zoom_step(1); pump(3)
assert not fits(), fits()                                            # (it was cut off here)
grew = dlg.win.winfo_height()
assert grew > small
area = usable_area(dlg.win)
assert dlg.win.winfo_height() <= area[3] and dlg.win.winfo_width() <= area[2]     # still on the screen
frame = dlg.win.winfo_rootx() - dlg.win.winfo_x()                   # (Windows: placed by its frame, ~8 px border)
def centred():                                                      # (or kept on the screen it overhangs)
    a = usable_area(dlg.win)
    edge = dlg.win.winfo_rootx() + dlg.win.winfo_width() >= a[0] + a[2] - 1 - frame or dlg.win.winfo_rootx() <= a[0] + 1 + frame
    return edge or abs(dlg.win.winfo_rootx() + dlg.win.winfo_width() // 2 -
                       (root.winfo_rootx() + root.winfo_width() // 2)) <= 2 + frame
def settle(cond, secs=5):
    end = time.time() + secs
    while not cond() and time.time() < end:
        root.update(); time.sleep(0.01)
    return cond()
assert settle(centred), (dlg.win.winfo_rootx(), dlg.win.winfo_width(), root.winfo_rootx(), root.winfo_width())
# the parent moving just after (macOS puts a window back on the screen after a re-fit): it follows
dlg.rescale(); root.update(); root.geometry("+120+90")
assert settle(centred), (dlg.win.winfo_rootx(), dlg.win.winfo_width(), root.winfo_rootx(), root.winfo_width())
for _ in range(3):
    app.zoom_step(-1); pump(3)
assert not fits() and abs(dlg.win.winfo_height() - small) <= 2
dlg.close()
app.on_close()

# Z-1 (asked for): each monitor keeps its own zooms; the window that stops on another monitor shows that one's at once
# (a monitor never zoomed starts from the last zoom chosen), and is resized only if it is bigger than that monitor
screens = {"left": (0, 0, 1920, 1080), "right": (1920, 0, 1280, 800)}
where = {"m": "left"}
A.monitor_box = lambda r: screens[where["m"]]
A.usable_area = lambda r: (screens[where["m"]][0], 0, screens[where["m"]][2], screens[where["m"]][3] - 40)
state["max"] = False
s = T.Store(db); s.set_meta("monitor_zooms", "{}"); s.set_meta("zoom", "1.0")
root = tk.Tk(); app = A.App(root, s, T.Definitions(s)); pump(10)
app.set_zoom(1.2); pump(3)
assert app.zoom == 1.2
size_left = (root.winfo_width(), root.winfo_height())
where["m"] = "right"; app._check_monitor(); pump(4)                  # (as when the window stops moving there)
assert app.zoom == 1.2 and root.winfo_height() <= 760               # never zoomed there: the last zoom, fitted
app.set_zoom(0.8); pump(3)
assert app.zoom == 0.8
where["m"] = "left"; app._check_monitor(); pump(4)
assert app.zoom == 1.2 and app._monitor == "0,0,1920x1080"          # back: the left one's own zoom
app._check_monitor(); pump(2); assert app.zoom == 1.2                # (the same monitor: nothing changes)
assert (root.winfo_width(), root.winfo_height()) == size_left       # (it fitted there: never resized)
where["m"] = "right"; app._check_monitor(); pump(4)
assert app.zoom == 0.8
kept = json.loads(s.get_meta("monitor_zooms"))
assert kept["0,0,1920x1080"]["zoom"] == 1.2 and kept["1920,0,1280x800"]["zoom"] == 0.8, kept
app.on_close()
s = T.Store(db); root = tk.Tk(); app = A.App(root, s, T.Definitions(s)); pump(6)
assert app.zoom == 0.8                                               # (after a restart: the monitor it opens on)
app.on_close()
where["m"] = "left"
s = T.Store(db); root = tk.Tk(); app = A.App(root, s, T.Definitions(s)); pump(6)
assert app.zoom == 1.2
app.on_close()
print("ZOOM OK")
