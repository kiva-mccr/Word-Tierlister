"""Window sizing: pure helpers, then the main window, browser and dialogs on simulated screens."""
import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import os, tempfile
import tkinter as tk
import sizing as Z
import app as A
from fonts import font
import tierlist as T

# ---- pure helpers
SAMPLE = """Screen 0: minimum 320 x 200, current 3000 x 1080, maximum 16384 x 16384
HDMI-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 527mm x 296mm
   1920x1080     60.00*+
DP-1 connected 1080x1920+1920+0 left (normal left inverted right x axis y axis) 527mm x 296mm
HDMI-2 disconnected (normal left inverted right x axis y axis)
"""
mons = Z.parse_xrandr(SAMPLE)
assert mons[0] == (0, 0, 1920, 1080, True) and len(mons) == 2, mons
assert Z.parse_xrandr("") == []
assert Z.fit_size((500, 400), (1000, 700), (1200, 800)) == (1000, 700)       # preferred wins when it fits
assert Z.fit_size((1100, 400), (1000, 700), (1200, 800)) == (1100, 700)      # contents need more
assert Z.fit_size((500, 400), (1000, 900), (800, 600)) == (800, 600)         # capped to the screen
x, y, w, h = 0, 0, 1000, 800
g = Z.center_geometry(400, 300, (x, y, w, h))
assert g == "400x300+300+250", g

root = tk.Tk()
for sc in (1.0, 1.333, 2.0):
    root.tk.call("tk", "scaling", sc)
    assert abs(Z.ui_factor(root) - max(0.75, sc / Z.REFERENCE_SCALING)) < 0.01   # Tk rounds scaling slightly
root.tk.call("tk", "scaling", 0.2); assert Z.ui_factor(root) == 0.75           # clamped low
root.tk.call("tk", "scaling", 20); assert Z.ui_factor(root) == 3.0             # clamped high
root.destroy()

# ---- main window on simulated screens: nothing clipped, never bigger than the screen
tmp = tempfile.mkdtemp()
store = T.Store(os.path.join(tmp, "s.db"))
words = ["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist",
         "pneumonoultramicroscopicsilicovolcanoconiosis"] + [f"word{i}" for i in range(30)]
store.insert_words(words); store.set_anchors(words[:6])
for wd in words[6:20]:
    store.place(wd, 2)

real_area = A.usable_area
cases = [(1920, 1080, 1.0), (1920, 1080, 1.333), (1920, 1080, 2.0), (3840, 2160, 2.0),
         (1366, 768, 1.0), (1366, 768, 1.333), (1366, 768, 1.667), (1280, 720, 1.333), (1024, 600, 1.0)]
for sw, sh, sc in cases:
    root = tk.Tk(); root.tk.call("tk", "scaling", sc)
    store = T.Store(os.path.join(tempfile.mkdtemp(), "s.db"))        # fresh save per case
    store.insert_words(words); store.set_anchors(words[:6])
    for wd in words[6:20]:
        store.place(wd, 2)
    A.usable_area = lambda r, sw=sw, sh=sh: (0, 0, int(sw * 0.96), int(sh * 0.90))
    app = A.App(root, store, T.Definitions(store)); root.update()
    steps = [("place", False), ("refine", False), ("refine", True), ("place", True)]
    for mode, defs in steps:
        app.mode_var.set(mode); app.on_mode_change(); app.toggle_defs(defs); root.update(); root.update_idletasks()
        W, H = root.winfo_width(), root.winfo_height()
        label = f"{sw}x{sh} sc{sc} {mode} defs={defs} win {W}x{H}"
        assert W <= int(sw * 0.96) and H <= int(sh * 0.90), "bigger than screen: " + label
        inner = app.place_inner if mode == "place" else app.pair_inner
        assert inner.winfo_reqheight() <= app.center.winfo_height(), "centre clipped (h): " + label
        assert inner.winfo_reqwidth() <= app.center.winfo_width(), "centre clipped (w): " + label + \
            f" inner {inner.winfo_reqwidth()} center {app.center.winfo_width()} pair {app.pair if mode != 'place' else None}" \
            f" btn {app.left_btn.winfo_reqwidth()}/{app.right_btn.winfo_reqwidth()} wrap {app.left_btn.cget('wraplength')} pairfont {font('pair').cget('size')}"
        rows = [w for w in root.pack_slaves() if w is not app.center]
        assert max(w.winfo_reqwidth() for w in rows) <= W, "row too wide: " + label
    # Browse window: toolbars and columns must fit its width, on this screen too
    import browser as B
    B.usable_area = A.usable_area
    app.anim.reduce_motion = True                  # (sizes, not motion: no opening ease)
    app.open_browser(); root.update(); bw = app.browsers[-1]; root.update()
    W = bw.win.winfo_width()
    assert W <= int(sw * 0.96) and bw.win.winfo_height() <= int(sh * 0.90), f"browse bigger than screen {sw}x{sh}"
    for bar in (bw.top_bar, bw.btn_bar):
        assert bar.winfo_reqwidth() <= W, f"browse toolbar clipped {sw}x{sh} sc{sc}: {bar.winfo_reqwidth()} > {W}"
    # the word count at its longest ("N of M (more on scroll)") still fits: it is part of the minimum size
    bw.count_lbl.config(text=bw._longest_count()); root.update()
    assert bw.top_bar.winfo_reqwidth() <= max(W, int(bw.win.minsize()[0])), f"browse count clipped {sw}x{sh} sc{sc}"
    bw.total = 1234567; bw._update_count(); root.update()                 # more digits: the minimum grows
    assert int(bw.win.minsize()[0]) >= min(bw._needed_size()[0], int(sw * 0.96)), "minsize ignores the count"
    cols = sum(int(bw.tree.column(c, "width")) for c in ("tier", "word", "rating", "games", "freq"))
    assert cols <= bw.tree.winfo_width() + 2, f"browse columns clipped {sw}x{sh} sc{sc}"
    for col, text in (("rating", "Rating"), ("freq", "Freq #")):
        assert int(bw.tree.column(col, "width")) >= bw.f_bold.measure(text), "heading clipped"
    # Selecting a row outlines it (four edges placed over the row) instead of tinting it
    kids = bw.tree.get_children(); bw.tree.selection_set(kids[1]); root.update()
    assert all(e.winfo_manager() == "place" for e in bw._outline), "selection outline missing"
    bw.tree.selection_remove(kids[1]); bw._draw_outline(); root.update()
    assert not any(e.winfo_manager() for e in bw._outline), "outline should hide with no selection"
    # Start-up window: wide enough for its text, on screen
    import startup as S
    S.usable_area = A.usable_area
    sw_win = S.StartupWindow(root, "Setting up", lambda: None); root.update()
    assert sw_win.win.winfo_reqwidth() <= int(sw * 0.96), "startup window wider than screen"
    sw_win.win.destroy()
    root.destroy()
A.usable_area = real_area

# ---- dialogs stay on screen
root = tk.Tk()
dlg = tk.Toplevel(root); tk.Label(dlg, text="x" * 40).pack(padx=300, pady=200)
Z.place_dialog(dlg, root); dlg.update_idletasks()
ax, ay, aw, ah = Z.usable_area(root)
assert ax <= dlg.winfo_x() and dlg.winfo_x() + dlg.winfo_width() <= ax + aw + 2
# ---- several monitors: a pop-up stays on the monitor it opens from (reported on Windows: a drop-down on a
#      second monitor opened at the far side of the main one, because Tk's screen size is the main monitor's)
two = [(0, 0, 1920, 1080, True), (1920, 0, 2560, 1440, False)]
saved = Z._xrandr_cache.get("monitors")
Z._xrandr_cache["monitors"] = two
assert Z.monitor_at(root, 2500, 300) == (1920, 0, 2560, 1440) and Z.monitor_at(root, 100, 100) == (0, 0, 1920, 1080)
assert Z.monitor_at(root, 5000, 300) == (1920, 0, 2560, 1440)                  # off every monitor: the nearest
assert Z.clamp_to_monitor(root, 2400, 300, 200, 100) == (2400, 300)            # fits: left where it is
assert Z.clamp_to_monitor(root, 4400, 1400, 200, 100) == (4280, 1340)          # kept on the second monitor
assert Z.clamp_to_monitor(root, 1850, 300, 200, 100, at=(1850, 300)) == (1720, 300)   # opened from the first
Z._xrandr_cache["monitors"] = []
assert Z.monitor_at(root, 10, 10)[:2] == (0, 0)                                # unknown: Tk's one screen
if saved is None:
    Z._xrandr_cache.pop("monitors")
else:
    Z._xrandr_cache["monitors"] = saved
assert Z._windows_monitors() == [] or os.name == "nt"                          # (only answers on Windows)
root.destroy()

# ---- Windows display scaling: asked for once, newest way first, older ways as fallbacks
class Fn:
    def __init__(self, result, calls, name): self.result, self.calls, self.name = result, calls, name
    def __call__(self, *a): self.calls.append((self.name, a)); return self.result
def fake_windll(ctx, shcore, legacy):
    calls = []
    def part(**fns):
        return type("P", (), {k: Fn(v, calls, k) for k, v in fns.items()})()
    w = type("W", (), {})()
    w.user32 = part(SetProcessDpiAwarenessContext=ctx, SetProcessDPIAware=legacy)
    w.shcore = part(SetProcessDpiAwareness=shcore)
    return w, calls
w, calls = fake_windll(1, 0, 1)
assert Z.set_dpi_awareness(w) and calls == [("SetProcessDpiAwarenessContext", (-4,))]   # per monitor, v2
w, calls = fake_windll(0, 0, 1)
assert Z.set_dpi_awareness(w) and [c[0] for c in calls] == ["SetProcessDpiAwarenessContext", "SetProcessDpiAwareness"]
w, calls = fake_windll(0, 5, 1)
assert Z.set_dpi_awareness(w) and calls[-1][0] == "SetProcessDPIAware"
assert Z.set_dpi_awareness() is (os.name == "nt") or os.name == "nt"           # elsewhere: nothing to do
# two monitors: a window uses the monitor it is on, and a dialog opens on its parent's, wherever the pointer is
# (it used to be the pointer's monitor: a dialog was pushed onto the other one, the main window fitted to its size)
root = tk.Tk()
from fonts import init_fonts
init_fonts(root)
saved = dict(Z._xrandr_cache)
Z._xrandr_cache["monitors"] = [(0, 0, 1000, 700, True), (1000, 0, 900, 600, False)]
second = tk.Toplevel(root); second.geometry("300x200+1200+100"); second.update()
assert Z.monitor_box(second) == (1000, 0, 900, 600), Z.monitor_box(second)
from widgets import StyledDialog
dlg = StyledDialog(second, "Two monitors", "A question", "On the second monitor, over its window.")
dlg.button("OK", dlg.close, default=True)
Z.place_dialog(dlg.win, second); dlg.win.deiconify(); dlg.win.update()
assert dlg.win.winfo_x() >= 1000, dlg.win.winfo_x()
# a dialog that grows stays on its monitor (refit: keep_on_screen)
dlg.win.geometry("+1500+500"); dlg.win.update()
tk.Label(dlg.body, text="more\n" * 12).pack(); dlg.refit(); dlg.win.update()
assert dlg.win.winfo_y() + dlg.win.winfo_height() <= 600 + 2, (dlg.win.winfo_y(), dlg.win.winfo_height())
dlg.close(); second.destroy(); root.destroy()
Z._xrandr_cache.clear(); Z._xrandr_cache.update(saved)
print("sizing OK")
