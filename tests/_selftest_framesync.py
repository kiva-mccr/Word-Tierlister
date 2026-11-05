import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""F-53 (asked for): a maximize or restore never shows the old picture in the window's top-left corner. On X11 the
page's X window has centre gravity, goes back to the window's corner once Tk has the new size, and answers frame
sync requests once drawn (framesync); the page's contents start where the old picture was left and ease in a
straight line to their place (App._slide_from_here). Elsewhere framesync does nothing."""
import os, shutil, subprocess, sys, tempfile, time
tmp = tempfile.mkdtemp()
os.environ["HOME"] = os.path.join(tmp, "home"); os.makedirs(os.environ["HOME"])
os.environ["USERPROFILE"] = os.environ["HOME"]
import tkinter as tk
import tierlist as T
import app as A
import framesync


def wait_for(win, cond, s=5.0):
    end = time.time() + s
    while not cond() and time.time() < end:
        win.update(); time.sleep(0.01)
    return cond()


# --- framesync on its own -------------------------------------------------------------------------------------------
r = tk.Tk()
x11 = r.tk.call("tk", "windowingsystem") == "x11"
real_platform = sys.platform
sys.platform = "win32"
try:
    assert framesync.enable(r) is None                         # (anywhere but X11: nothing at all)
finally:
    sys.platform = real_platform
if x11:
    r.geometry("400x300+50+50")
    fs = framesync.enable(r)
    assert fs, "frame sync not set up on X11"
    assert "_NET_WM_SYNC_REQUEST" in r.wm_protocol()
    if shutil.which("xprop"):
        props = subprocess.run(["xprop", "-id", r.wm_frame()], capture_output=True, text=True).stdout
        assert "_NET_WM_SYNC_REQUEST_COUNTER(CARDINAL)" in props and "_NET_WM_SYNC_REQUEST" in props, props
    fs.set_background("#FBF7F4")
    r.bind("<Configure>", lambda e: e.widget is r and fs.after_resize())
    r.update()
    # a request is answered once the new size is drawn: the counter at the last value + STEP
    fs._requested()
    r.geometry("500x380")
    assert wait_for(r, lambda: fs.value == framesync.STEP and not fs.asked), fs.value
    # ...and also when no new size follows it
    fs._requested()
    assert wait_for(r, lambda: fs.value == 2 * framesync.STEP and not fs.asked), fs.value
    # the X server moves the page by half a change (centre gravity); once Tk has the new size it is back in the corner
    if shutil.which("xwininfo"):
        r.geometry("700x520"); r.update()
        assert wait_for(r, lambda: r.winfo_width() == 700)
        info = subprocess.run(["xwininfo", "-id", str(r.winfo_id())], capture_output=True, text=True).stdout
        rel = [line.split(":")[1].strip() for line in info.splitlines() if "Relative upper-left" in line]
        assert rel == ["0", "0"], info
r.destroy()

# --- the slide ------------------------------------------------------------------------------------------------------
s = T.Store(os.path.join(tmp, "f.db"))
words = [f"w{i:03d}" for i in range(40)]
anchors = ["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"]
s.insert_words(words + anchors); s.set_anchors(anchors)
s.set_meta("dealt_asked", "1")
root = tk.Tk(); root.withdraw()
T.init_fonts(root); T.apply_ttk_style(root)
app = A.App(root, s, T.Definitions(s))
app._startup = lambda: None
app.open_window()
assert wait_for(root, lambda: app._veil_since is None)
assert bool(app.framesync) == x11
inner = app.place_inner
root.update()
w, h = root.winfo_width(), root.winfo_height()
x_was, y_was = inner.winfo_x(), inner.winfo_y()
app.anim._real = False                       # (the clock held: the first frames checked without a slow runner's leaps)
clock = [0.0]
app.anim.clock = lambda: clock[0]
# just maximized, 200 x 100 bigger: the contents start where the old picture was left (centre gravity: moved by half
# the change on X11), then ease in a straight line to the middle
app._last_size, app._size_now, app._maximized = (w, h), (w + 200, h + 100), True
app._slide_from_here()
app._size_now = None
dx, dy = (100, 50) if x11 else (0, 0)
info = inner.place_info()
assert (info["relx"], info["anchor"], int(info["x"]), int(info["y"])) == ("0", "nw", x_was + dx, y_was + dy), info
assert app._normal_size == (w, h)
root.geometry(f"{w + 200}x{h + 100}")
assert wait_for(root, lambda: "slide" in app.anim._running), "the slide never started"
x0, y0 = x_was + dx, y_was + dy
tx, ty = (inner.master.winfo_width() - inner.winfo_reqwidth()) // 2, app._centred_top(inner)
seen = []
for k in range(1, 12):                                   # (a straight line: every point on the line between the ends)
    clock[0] = k * app.SLIDE_MS / 10000
    root.update()
    info = inner.place_info()
    if info["anchor"] != "nw":
        break
    seen.append((int(info["x"]), int(info["y"])))
assert seen, "no frames"
for x, y in seen:
    if tx != x0 and ty != y0:
        assert abs((x - x0) / (tx - x0) - (y - y0) / (ty - y0)) < 0.05, (seen, x0, y0, tx, ty)
# a resize while it slides leaves it alone (_recenter)
before = inner.place_info()["y"]
app._recenter()
assert inner.place_info()["y"] == before
clock[0] = 10.0
assert wait_for(root, lambda: app._sliding is None), "the slide never ended"
info = inner.place_info()
assert (info["relx"], info["anchor"], int(info["x"])) == ("0.5", "n", 0), info     # (centred again, as usual)
# restored: back to the size before maximizing, the same way
app._last_size, app._maximized = (w + 200, h + 100), False
x_was = inner.winfo_x()
app._slide_from_here()
assert int(inner.place_info()["x"]) == x_was - dx, inner.place_info()
root.geometry(f"{w}x{h}")
clock[0] = 20.0
assert wait_for(root, lambda: "slide" in app.anim._running)
clock[0] = 40.0
assert wait_for(root, lambda: app._sliding is None)
assert inner.place_info()["anchor"] == "n"
root.destroy()
print("framesync self-test passed")
