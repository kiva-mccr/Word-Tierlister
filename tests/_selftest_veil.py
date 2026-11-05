import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""Windows appear complete (F-48, asked for): the main window stays see-through after opening until nothing has
moved or resized it for a moment, dialogs and the setup window are drawn see-through and shown in one go, and a
fit (maximizing to a big zoom) never tries sizes on screen above the limit found while the window was hidden."""
import os, tempfile, time
tmp = tempfile.mkdtemp()
os.environ["HOME"] = os.path.join(tmp, "home"); os.makedirs(os.environ["HOME"])
os.environ["USERPROFILE"] = os.environ["HOME"]
import tkinter as tk
import tierlist as T
import app as A
import startup, ui_style
from widgets import StyledDialog

s = T.Store(os.path.join(tmp, "v.db"))
words = [f"w{i:03d}" for i in range(40)]
anchors = ["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"]
s.insert_words(words + anchors); s.set_anchors(anchors)
s.set_meta("dealt_asked", "1")


def alpha(w):
    return float(w.attributes("-alpha"))


def pump(win, ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        win.update(); time.sleep(0.01)


def wait_for(win, cond, s=5.0):
    """Run the event loop until cond() holds, for at most `s` seconds (Mac runners are slow: never a fixed wait)."""
    end = time.time() + s
    while not cond() and time.time() < end:
        win.update(); time.sleep(0.01)
    return cond()


class FakeEvent:
    def __init__(self, widget):
        self.widget = widget


root = tk.Tk(); root.withdraw()
T.init_fonts(root); T.apply_ttk_style(root)
app = A.App(root, s, T.Definitions(s))
app._startup = lambda: None
app.open_window()
assert app._veil_since is not None and alpha(root) == 0.0            # still see-through: it may yet be resized
# the window manager resizes it just after it shows (GNOME maximizes a window that nearly fills the screen): while
# that is still going on, it stays see-through (driven by hand, not by the clock: Mac runners are slow)
app._on_root_configure(FakeEvent(root))
assert app._grow_job and app._monitor_job                             # (hurried while see-through: 20 ms each)
app._unveil()
assert app._veil_since is not None and alpha(root) == 0.0, "unveiled while it was still being resized"
assert wait_for(root, lambda: app._veil_since is None and alpha(root) == 1.0), "never unveiled"
assert not app._grow_job and not app._monitor_job
# a Configure after that waits the usual 80 / 300 ms again (only while see-through are they hurried)
app._on_root_configure(FakeEvent(root))
assert app._veil_since is None
wait_for(root, lambda: not app._grow_job and not app._monitor_job)

# just maximized or restored: the re-fit runs at once (an idle job), not after the 80 ms pause (asked for)
real_max = A.is_maximized
try:
    A.is_maximized = lambda w: not app._maximized
    app._on_root_configure(FakeEvent(root))
    assert root.tk.splitlist(root.tk.call("after", "info", app._grow_job))[1] == "idle"
finally:
    A.is_maximized = real_max
root.after_cancel(app._grow_job); app._grow_job = None
app._on_root_configure(FakeEvent(root))                                # (an ordinary resize still waits)
assert root.tk.splitlist(root.tk.call("after", "info", app._grow_job))[1] == "timer"
wait_for(root, lambda: not app._grow_job and not app._monitor_job)

# never see-through for long, even if the window keeps moving
app._veil_since = time.time() - A.App.VEIL_MAX_MS / 1000
app._last_configure = time.time()
root.attributes("-alpha", 0.0)
app._unveil()
assert app._veil_since is None and wait_for(root, lambda: alpha(root) == 1.0)

# a fit never tries a size above the screen's limit (found hidden, _precheck_zoom): maximizing to a zoom kept for it
# that this screen cannot fit showed every size from that zoom down
key = app._layout_key()
app._zoom_cap[key] = 1.2
tried = []
real = A.scale_fonts
A.scale_fonts = lambda z, *a, **k: (tried.append(z), real(z, *a, **k))[1]
try:
    app._apply_zoom(1.8)
finally:
    A.scale_fonts = real
assert tried and max(tried) <= 1.1 + 1e-9, tried
assert round(app.font_scale * app.zoom, 2) <= 1.1
app._apply_zoom(1.0); pump(root, 100)

# a dialog is drawn see-through and turns opaque once drawn
d = StyledDialog(root, "Test", "A heading", "Some words " * 20)
d.button("OK", d.close, default=True)
d.show()
assert alpha(d.win) == 0.0 and d.win.winfo_viewable()
assert wait_for(root, lambda: alpha(d.win) == 1.0)
d.close()

# the setup window shows where it belongs, not first in the corner (it is placed while withdrawn)
maps = []
root.bind_all("<Map>", lambda e: isinstance(e.widget, tk.Toplevel) and maps.append(e.widget.geometry()), add="+")
w = startup.StartupWindow(root, "Setting up", lambda: None)
assert wait_for(root, lambda: maps and alpha(w.win) == 1.0)
assert maps and maps[0].split("+")[1:] == w.win.geometry().split("+")[1:], (maps, w.win.geometry())
w.close()


# unveil gives up waiting for a window that never shows, and never runs the event loop itself (a stand-in window
# with its own timer list: macOS cannot report the alpha of a window it never showed)
class NeverShown:
    def __init__(self):
        self.alpha, self.timers, self.updates = 0.0, [], 0
    def winfo_exists(self): return True
    def winfo_viewable(self): return False
    def update_idletasks(self): self.updates += 1
    def update(self): raise AssertionError("unveil ran the event loop")
    def after(self, ms, fn): self.timers.append(fn)
    def attributes(self, name, value): self.alpha = value


t = NeverShown()
ui_style.unveil(t, wait_ms=50)
for _ in range(20):                       # (each timer runs in turn; 5 looks, 10 ms apart, then the 30 ms one)
    if not t.timers:
        break
    t.timers.pop(0)()
assert t.alpha == 1.0 and t.updates == 1 and not t.timers
app.on_close()
print("veil self-test passed")
