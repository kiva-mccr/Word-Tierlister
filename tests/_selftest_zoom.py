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
print("ZOOM OK")
