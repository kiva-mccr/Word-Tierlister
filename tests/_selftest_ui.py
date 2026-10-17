import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
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
assert app.hint_lbl.cget("text") == "Backspace or Ctrl+Z undo"     # 1-6, Space, U, D are on their buttons
first = s.next_unplaced()["word"]
assert app.word_card.word == first, (app.word_card.word, first)
assert "frequency rank" in app.word_card.sub
key("3")
assert s.get_word(first)["tier"] == 2
second = s.next_unplaced()["word"]
assert second != first and app.word_card.word == second
key("space")
assert app.cmp is not None
assert app.hint_lbl.cget("text") == "Esc cancel"                  # only keys no button shows
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

# ---- every tab's content is centred in the page, and the page is the same size in every tab
c = app.center
pages = set()
for m in ("place", "refine", "boundary", "conflict"):
    app.mode_var.set(m); app.on_mode_change(); pump(4)
    inner = app.place_inner if m == "place" else app.pair_inner
    kids = [w for w in inner.winfo_children() if w.winfo_ismapped()]
    l = min(w.winfo_rootx() for w in kids); r = max(w.winfo_rootx() + w.winfo_width() for w in kids)
    t = min(w.winfo_rooty() for w in kids); b = max(w.winfo_rooty() + w.winfo_height() for w in kids)
    assert abs((l + r) / 2 - (c.winfo_rootx() + c.winfo_width() / 2)) <= 2, ("not centred across", m)
    page_top, page_bottom = app.status_band.winfo_rooty(), c.winfo_rooty() + c.winfo_height()
    assert abs((t + b) / 2 - (page_top + page_bottom) / 2) <= 2, ("not centred in the visible page", m)
    pages.add((c.winfo_rooty(), c.winfo_height()))
assert len(pages) == 1, pages                                       # the Tier / Boundary choice lives inside
app.mode_var.set("refine"); app.on_mode_change(); pump(2)
assert app.opt_frame.winfo_ismapped() and app.opt_frame.winfo_rooty() < app.pair_title.winfo_rooty()

# ---- UI-18: every hotkey dips the button it stands for (after doing its job); never a disabled one
app.mode_var.set("place"); app.on_mode_change(); app.cmp = None; app._render_place_state(); pump(2)
flashed = []
def spy(b, name):
    real = b.flash
    b.flash = lambda *a, **k: (flashed.append(name), real(*a, **k))
for i, b in enumerate(app.tier_btns): spy(b, f"tier{i}")
spy(app.compare_btn, "compare"); spy(app.later_btn, "later")
for k, b in app.cmp_btns.items(): spy(b, k)
for k, b in app.duel.buttons.items(): spy(b, "duel_" + k)
w = app.cur_word; key("5"); assert flashed[-1] == "tier4" and s.get_word(w)["tier"] == 4   # placed AND dipped
w = app.cur_word; key("u"); assert flashed[-1] == "later" and s.get_word(w)["skips"] >= 1
key("space"); assert flashed[-1] == "compare" and app.cmp
key("Up"); assert flashed[-1] == "better"
if app.cmp:
    key("BackSpace"); assert flashed[-1] == "back"
key("Escape"); assert app.cmp is None
for m in ("refine",):
    app.mode_var.set(m); app.on_mode_change(); pump(2)
    for k, name in (("Left", "duel_left"), ("l", "duel_right"), ("t", "duel_tie"), ("s", "duel_skip")):
        if app.pair:
            key(k); assert flashed[-1] == name, (k, flashed[-1:])
app.mode_var.set("place"); app.on_mode_change(); pump(2)
app.compare_btn.set_enabled(False); n = len(flashed)
key("space"); pump(1); assert not app.compare_btn._pressed and app.cmp is None    # disabled: its key is off too
app.compare_btn.set_enabled(all(app.anchors))
app.motion_var.set(True); app.toggle_motion()
y0 = app.tier_btns[0].coords("label")[1]; w = app.cur_word; key("1")
assert s.get_word(w)["tier"] == 0 and app.tier_btns[0].coords("label")[1] == y0              # Reduce motion: no dip
app.motion_var.set(False); app.toggle_motion()

# ---- sorting fast: each message is its own pill; the older one speeds out underneath, the newest on top
app.mode_var.set("place"); app.on_mode_change(); pump(2)
root.after(1500, root.quit); root.mainloop()                                   # earlier messages have gone
w1 = app.cur_word; key("2"); w2 = app.cur_word; key("3")
assert len(app.toasts) <= 3                                                    # gone ones are cleaned up
live = [t for t in app.toasts if t.cget("text")]
assert len(live) == 2 and live[-1] is app.toast and app.toast.cget("text").startswith(w2)
assert live[0]._hurried and live[0].cget("text").startswith(w1)
t0 = time.perf_counter()
while live[0].cget("text") and time.perf_counter() - t0 < 2:
    root.update(); time.sleep(0.005)
assert not live[0].cget("text") and live[0] not in app.toasts                  # gone and cleaned up
app.anim.finish_all(); root.after(800, root.quit); root.mainloop(); app.anim.finish_all(); pump(2)

# ---- duel result (UI-19): answered at once, the next pair after the short resolve; no double answers
app.mode_var.set("refine"); app.on_mode_change(); pump(2)
if app.pair:
    first = dict(app.pair); n0 = s.stats()["comparisons"]
    for side, btn in (("left", app.left_btn), ("right", app.right_btn)):        # cards wear their tier colour
        assert btn.cget("bg") == T.TIER_COLORS[s.get_word(app.pair[side])["tier"]]
    key("Left")
    assert s.stats()["comparisons"] == n0 + 1 and app.pair is None              # saved straight away
    assert app.toast.cget("text") == f"{first['left']}  >  {first['right']}"    # refine shows its result too
    app.pair_answer("left"); app._on_duel("right")                             # clicks during the resolve
    assert s.stats()["comparisons"] == n0 + 1                                   # ...are ignored
    key("Right")                                                                 # a key finishes it and answers
    assert s.stats()["comparisons"] == n0 + 2                                   # the next pair at once
app.anim.finish_all(); pump(2)

# ---- zoom: View menu and Ctrl + / - / 0 scale the whole main window, remembered in the save
from fonts import font as _font
body0, word0 = _font("body").cget("size"), _font("word").cget("size")
import widgets as _W
assert {"Zoom in", "Zoom out", "Actual size"} <= set(_W.DropMenu.labels(app.header.menus["View"]))
app.set_zoom(1.3); pump(3)
assert app.zoom == 1.3 and s.get_meta("zoom") == "1.3"
assert app.toast.cget("text") == "Zoom 130%" and app.toast._tint[0] == T.PALETTE["info"][0] == "#FFFFFF"   # a white card
assert _font("body").cget("size") > body0 and _font("word").cget("size") > word0
assert root.winfo_width() <= app.root.winfo_screenwidth()                          # never past the screen
root.event_generate("<Control-minus>"); pump(3); assert app.zoom == 1.2
app.set_zoom(9); assert app.zoom == app.ZOOM_MAX; app.set_zoom(0); assert app.zoom == app.ZOOM_MIN   # limits
root.event_generate("<Control-0>"); pump(3)
assert app.zoom == 1.0 and abs(_font("body").cget("size") - body0) <= 1
app.set_zoom(1.1); zoom_saved = s.get_meta("zoom"); app.set_zoom(1.0)
assert zoom_saved == "1.1"

# ---- calm stats (UI-15): one quiet line, "+N today" muted, the pace only on hover
import app as A
line = A.format_stats({"placed": 6506, "total": 9006, "skipped": 3, "conflicts": 0})
assert line == "Placed 6,506 of 9,006 (72.2%)   \u00b7   2,500 left   \u00b7   3 skipped", line
assert "conflict" not in line                                       # only when there are some
assert A.format_stats({"placed": 1, "total": 2, "skipped": 0, "conflicts": 1}).endswith("1 conflict to look at")
assert "/hr" not in app.stats_lbl.cget("text") and "today" not in app.stats_lbl.cget("text")
n0 = int(app.today_lbl.cget("text").split()[0].lstrip("+").replace(",", ""))
app.mode_var.set("place"); app.on_mode_change(); pump(2)
key("4")
assert app.word_card.find_withtag("old")                            # UI-16: the old word is on its way out
app.anim.finish_all(); pump(2)
assert not app.word_card.find_withtag("old")
assert app.today_lbl.cget("text") == f"+{n0 + 1:,} today" and str(app.today_lbl.cget("foreground")) == T.PALETTE["muted"]
key("BackSpace"); pump(2); assert app.today_lbl.cget("text") == f"+{n0:,} today"   # undo takes it back
app.session_count, app.session_start = 0, time.time() - 1800
assert app._pace_text() == "Words and duels done today"            # too early to talk about pace
app.session_count = 60
assert app._pace_text().endswith("about 120 an hour") and app.today_tip.text_fn(None) == app._pace_text()
assert abs(A.local_midnight() - time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))) < 1

# ---- the tier chart (UI-13): in Place new words only, and it follows placements
app.mode_var.set("place"); app.on_mode_change(); pump(2)
assert app.chart.shown
before = list(app.chart.counts); key("2"); app.anim.finish_all(); pump(2)
assert app.chart.counts[1] == before[1] + 1 and sum(app.chart.counts) == sum(before) + 1
for m in ("refine", "boundary", "conflict"):
    app.mode_var.set(m); app.on_mode_change(); pump(2)
    assert not app.chart.shown and app.chart.itemcget("letter0", "state") == "hidden", m
app.mode_var.set("place"); app.on_mode_change(); pump(2); assert app.chart.shown
# UI-17: a placed word's message lands in its tier's bar, which then pulses
pulsed = []
real_pulse = app.chart.pulse
app.chart.pulse = lambda t: pulsed.append(t)
key("3"); app.anim.finish_all(); pump(2)                            # the rise ...
root.after(700, root.quit); root.mainloop()                         # ... the rest ...
app.anim.finish_all(); pump(2)                                       # ... the flight
assert pulsed and pulsed[-1] == 2, pulsed                           # (an earlier message may land first)
app.chart.pulse = real_pulse

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
