"""Window sizing: pure helpers, then the main window, browser and dialogs on simulated screens."""
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
    app.open_browser(); root.update(); bw = app.browsers[-1]; root.update()
    W = bw.win.winfo_width()
    assert W <= int(sw * 0.96) and bw.win.winfo_height() <= int(sh * 0.90), f"browse bigger than screen {sw}x{sh}"
    for bar in (bw.top_bar, bw.btn_bar):
        assert bar.winfo_reqwidth() <= W, f"browse toolbar clipped {sw}x{sh} sc{sc}: {bar.winfo_reqwidth()} > {W}"
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
root.destroy()
print("sizing OK")
