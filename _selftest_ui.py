import os, sys, tempfile, time, types
import tkinter as tk
import tierlist as T

OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
tmp = tempfile.mkdtemp()
s = T.Store(os.path.join(tmp, "ui.db"))
words = [f"w{i:05d}" for i in range(9000)] + ["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"]
s.insert_words(words)
s.db.execute("UPDATE words SET pen=1 WHERE rank % 10 = 3")
s.db.commit()
s.set_anchors(["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"])
s.reshuffle(seed=11, spread=3000)
for i in range(6500):
    s.place(f"w{i:05d}", i % 6)

root = tk.Tk()
shown = []
T.messagebox.showinfo = lambda *a, **k: shown.append(a)   # no modal dialogs in the test
T.messagebox.showerror = lambda *a, **k: shown.append(a)
app = T.App(root, s, T.Definitions(s))


def pump(n=6, d=0.05):
    for _ in range(n):
        root.update()
        time.sleep(d)


def key(ks):
    app.on_key(types.SimpleNamespace(keysym=ks))


pump()
# ---------------------------------------------------------------- place mode
first = s.next_unplaced()["word"]
assert app.word_card.word == first, (app.word_card.word, first)
assert "frequency rank" in app.word_card.sub
key("3")
assert s.get_word(first)["tier"] == 2
second = s.next_unplaced()["word"]
assert second != first and app.word_card.word == second
key("space")
assert app.cmp is not None
pump(2)
assert app.ladder.winfo_ismapped() and app.ladder.possible() == [0, 1, 2, 3, 4, 5]   # UI-9: the ladder shows
assert app.ladder.mid == app.cmp["mid"]
key("Up"); pump(2)                                                  # better than the middle anchor
if app.cmp:
    assert app.ladder.possible() == list(range(app.cmp["lo"], app.cmp["hi"] + 1)) and max(app.ladder.possible()) < 2
key("BackSpace"); pump(2)
key("Up"); key("Down")
pump(2)
if app.cmp:
    key("e")
assert s.get_word(second)["tier"] is not None
third = app.cur_word
key("u")
assert s.get_word(third)["skips"] == 1 and app.cur_word != third
key("d")
pump(2)
assert app.show_defs
key("d")
key("BackSpace")                      # undo the skip
assert s.get_word(third)["skips"] == 0
# ---------------------------------------------------------------- pair modes
for mode in ("refine", "boundary", "conflict", "place"):
    app.mode_var.set(mode)
    app.on_mode_change()
    pump(2)
    if mode in ("refine", "boundary"):
        assert app.pair is not None, mode
        key("Left")
        key("Down")
# ---------------------------------------------------------------- queue dialog
assert app.apply_queue_settings("abc", "5000", "exp", "1")
assert app.apply_queue_settings("5", "50", "exp", "1")
assert app.apply_queue_settings("5", "5000", "exp", "99")
assert app.apply_queue_settings("77", "8,000", "gauss", "2") is None
cfg = s.queue_settings()
assert cfg["seed"] == 77 and cfg["spread"] == 8000 and cfg["shape"] == "gauss" and cfg["compound"] == 2
assert app.apply_queue_settings("11", "3000", "exp", "1") is None
before = set(root.winfo_children())
app.edit_queue()
pump(3)
dlgs = [w for w in root.winfo_children() if w not in before and isinstance(w, tk.Toplevel)]
assert dlgs, "queue dialog did not open"
for d in dlgs:
    d.destroy()
app.edit_anchors()
pump(3)
for w in root.winfo_children():
    if isinstance(w, tk.Toplevel):
        w.destroy()
pump(2)

# ---------------------------------------------------------------- browse window
app.open_browser()
pump(8)
bw = app.browsers[0]
placed = s.stats()["placed"]
assert placed > 6000
assert bw.loaded == 3000 and bw.total == placed, (bw.loaded, bw.total)
assert len(bw.tree.get_children()) == 3000
print("browse opens with", bw.loaded, "of", bw.total, "rows; font", bw.fsize, "pt")

# scroll to the end repeatedly: everything beyond 1500 (and beyond the first page) must load
for _ in range(10):
    bw.tree.yview_moveto(1.0)
    pump(4, 0.03)
    if bw.loaded >= bw.total:
        break
assert bw.loaded == bw.total == len(bw.tree.get_children()) == placed, (bw.loaded, bw.total)
print("scrolled to the end:", bw.loaded, "rows loaded")
bw.tree.yview_moveto(0.0)
pump(3)

# scaling with the window
rh = lambda: int(bw.style.lookup(bw.tstyle, "rowheight") or 0)
f0, r0 = bw.fsize, rh()
bw.win.geometry("1800x1100+20+20")
pump(10, 0.05)
f1, r1 = bw.fsize, rh()
bw.win.geometry("700x520+20+20")
pump(10, 0.05)
f2, r2 = bw.fsize, rh()
print(f"font/rowheight: small {f2}/{r2}, base {f0}/{r0}, large {f1}/{r1}")
assert f1 > f0 > f2 and r1 > r0 > r2
bw.win.geometry(f"{bw.base_w}x{bw.base_h}+20+20")
pump(10, 0.05)
assert bw.fsize == f0
bw.zoom_by(3); assert bw.fsize == f0 + 3 and rh() > r0
bw._wheel_zoom(types.SimpleNamespace(delta=120)); assert bw.fsize == f0 + 4
bw._wheel_zoom(types.SimpleNamespace(delta=-120)); bw.zoom_by(0)
# zooming in may have grown the window to keep everything visible: put it back at the base size
bw.win.geometry(f"{bw.base_w}x{bw.base_h}+20+20"); pump(10, 0.05)
assert bw.fsize == f0 and s.get_meta("browse_zoom") == "0"
assert bw.f_body.cget("size") == f0 and bw.def_text.cget("font")

# filters, search, sort
bw.filter_var.set("Unplaced"); bw.reload(); pump(2)
assert bw.total == s.count_words() - placed
assert bw.tree.get_children()[0] == s.next_unplaced()["word"]     # browse default order == queue order
bw.sort_var.set("A-Z"); bw.reload(); pump(2)
kids = bw.tree.get_children()[:50]
assert list(kids) == sorted(kids)
bw.sort_var.set("Frequency"); bw.reload(); pump(2)
fr = [int(bw.tree.set(k, "freq").replace(",", "")) for k in bw.tree.get_children()[:50]]
assert fr == sorted(fr)
bw.sort_var.set("Default")
bw.filter_var.set("All placed"); bw.search_var.set("serend"); bw.reload(); pump(2)
assert "serendipity" in bw.tree.get_children()
bw.tree.selection_set("serendipity"); pump(2)
assert "serendipity" in bw.def_text.get("1.0", "end")
bw.move(2)                                                         # anchors are protected
assert shown and s.get_word("serendipity")["tier"] == 0
bw.search_var.set("w00010"); bw.reload(); pump(2)
bw.tree.selection_set("w00010"); pump(2)
bw.move(0)
assert s.get_word("w00010")["tier"] == 0
v = s.version
key("1")                                                           # main-window action while browser open
pump(2)
bw._maybe_refresh()
assert bw._seen_version == s.version >= v
bw.search_var.set(""); bw.reload(); pump(2)

# screenshots (best effort)
try:
    from PIL import ImageGrab
    for name, geo in (("browse_base", "980x760+10+10"), ("browse_large", "1800x1100+10+10")):
        bw.win.geometry(geo); bw.win.lift(); pump(12, 0.05)
        bw.tree.selection_set(bw.tree.get_children()[3]); pump(3)
        x, y, w, h = bw.win.winfo_rootx(), bw.win.winfo_rooty(), bw.win.winfo_width(), bw.win.winfo_height()
        ImageGrab.grab(bbox=(x, y, x + w, y + h), xdisplay=os.environ.get("DISPLAY")).save(f"{OUT}/{name}.png")
    print("screenshots saved to", OUT)
except Exception as exc:
    print("no screenshots:", exc)

bw.close()

# ---- header (UI-10): no system menu bar; menus open from the header and the keyboard; the mode switch
assert not root.cget("menu")
assert list(app.header.buttons) == ["File", "Edit", "View", "Settings"]
app._open_menu_key("View"); pump(2)
assert app.header.open_name == "View" and "Reduce motion" in T.DropMenu.labels(app.header.menus["View"]) if hasattr(T, "DropMenu") else app.header.open_name == "View"
key("1"); assert app.header.open_name == "View"                      # keys do nothing while a menu is open...
key("Escape"); pump(2); assert app.header.open_name is None          # ...except Escape, which closes it
app._on_mode_switch("boundary"); pump(2)
assert app.mode == "boundary" and s.get_meta("mode") == "boundary" and app.mode_switch.get() == "boundary"
app.mode_var.set("place"); app.on_mode_change(); pump(2)
assert app.mode_switch.get() == "place"                              # the switch follows code changes too
app.on_close()
print("UI OK")
