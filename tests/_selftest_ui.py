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
import app as A, browser as B
A.show_message = B.show_message = lambda *a, **k: shown.append(a)   # no modal dialogs in the test
A.show_error = lambda *a, **k: shown.append(a)
app = T.App(root, s, T.Definitions(s))


def pump(n=6, d=0.05):
    for _ in range(n):
        root.update()
        time.sleep(d)


def key(ks):                                       # a press and its release (a tap, not a held key)
    app.on_key(types.SimpleNamespace(keysym=ks, time=None))
    app.on_key_release(types.SimpleNamespace(keysym=ks, time=None))


pump()
# ---------------------------------------------------------------- place mode
assert app.hint_lbl.cget("text") == "Backspace or Ctrl+Z undo   \u00b7   Tab next tab"   # 1-6, Space, U, D are on their buttons
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
# the dialogs (UI-24): the shared StyledDialog, problems shown inline, the default button on Enter
qd = app.edit_queue(); pump(3)
assert qd.alive() and list(qd.buttons) == ["Cancel", "Apply & reshuffle"]
assert qd.buttons["Apply & reshuffle"].cget("bg") == T.PALETTE["select_bg"]
spread = [w for w in qd.body.winfo_children() if w.winfo_class() == "TEntry"][1]
spread.delete(0, "end"); spread.insert(0, "5")
qd.win.event_generate("<Return>"); pump(2)
assert qd.alive() and any("at least 100" in str(w.cget("text")) for w in qd.body.winfo_children() if w.winfo_class() == "TLabel")
qd.win.event_generate("<Escape>"); pump(2); assert not qd.alive()
labels = lambda d: " ".join(str(w.cget("text")) for w in d.body.winfo_children() if w.winfo_class() == "TLabel" and w.winfo_manager())
qd = app.edit_queue(); pump(3)
qd.buttons["Apply & reshuffle"].invoke(); pump(2)                               # nothing changed: says so, stays open
assert qd.alive() and "No settings changed" in labels(qd)
seed_e = [w for w in qd.body.winfo_children() if w.winfo_class() == "TEntry"][0]
seed_e.delete(0, "end"); seed_e.insert(0, "424242"); pump(1)
assert "No settings changed" not in labels(qd)                                  # an edit clears the note
real_reshuffle, gate = s.reshuffle, []
s.reshuffle = lambda **k: (gate.append(1), time.sleep(0.6), real_reshuffle(**k))
v0 = s.version
qd.buttons["Apply & reshuffle"].invoke(); pump(2, 0.05)
assert qd.alive() and app.busy and "Shuffling" in labels(qd)                    # runs in the background ...
assert not qd.buttons["Apply & reshuffle"].enabled and not qd.buttons["Cancel"].enabled
bars = [w for w in qd.body.winfo_children() if w.winfo_class() == "TProgressbar"]
assert bars and bars[0].winfo_manager() and str(bars[0].cget("mode")) == "indeterminate"   # the back-and-forth bar
qd.win.event_generate("<Escape>"); pump(1); assert qd.alive()                    # ... and cannot be cancelled halfway
t_end = time.time() + 30
while qd.alive() and time.time() < t_end:
    pump(2, 0.05)
assert not qd.alive() and not app.busy and s.queue_settings()["seed"] == 424242 and s.version > v0
assert app.toast.cget("text") == "Queue reshuffled"
s.reshuffle = real_reshuffle
ad = app.edit_anchors(); pump(3)
entries = [w for w in ad.body.winfo_children() if w.winfo_class() == "TEntry"]
assert len(entries) == 6 and entries[0].get() == "serendipity"
assert len([w for w in ad.body.winfo_children() if w.winfo_class() == "Canvas"]) == 6     # pills, not square labels
notes = lambda: {int(w.grid_info()["row"]) // 2: str(w.cget("text")) for w in ad.body.winfo_children()
                 if w.winfo_class() == "TLabel" and w.winfo_manager()}
assert notes() == {}                                                            # no notes until there is a problem
entries[1].delete(0, "end"); entries[1].insert(0, "serendipity")
entries[3].delete(0, "end"); entries[3].insert(0, "notaword")
entries[5].delete(0, "end")
ad.buttons["Save anchors"].invoke(); pump(2)
n = notes()
assert ad.alive() and set(n) == {0, 1, 3, 5}, n                                 # each note under its own field
assert "twice" in n[0] and "twice" in n[1] and "word list" in n[3] and "Fill" in n[5]
entries[3].delete(0, "end"); entries[3].insert(0, "bureaucracy"); pump(1)
assert 3 not in notes()                                                         # editing a field clears its note
entries[5].insert(0, "moist")
entries[1].delete(0, "end"); entries[1].insert(0, "luminous")
ad.buttons["Save anchors"].invoke(); pump(2)
assert not ad.alive() and s.get_anchors()[1] == "luminous"
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

# restyle (UI-23): soft tier rows, the full colour on the selected row, rounded buttons only
assert T.tint("#FF0000", 0) == "#FF0000" and T.tint("#FF0000", 1) == "#FFFFFF" and T.tint("#000000", 0.5) == "#808080"
assert str(bw.tree.tag_configure("t0", "background")).upper() == T.TIER_ROW[0] != T.TIER_COLORS[0]
first = bw.tree.get_children()[0]; tier0 = int(bw.tree.item(first, "tags")[0][1:])
bw.tree.selection_set(first); pump(2)
assert T.TIER_COLORS[tier0] in str(bw.style.map(bw.tstyle, "background"))
def all_kids(w):
    for c in w.winfo_children():
        yield c; yield from all_kids(c)
assert not [c for c in all_kids(bw.win) if c.winfo_class() in ("TButton", "TLabelframe")]
assert bw.top_bar.cget("bg") == T.PALETTE["surface"]
bw.tree.selection_remove(first)

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
# an anchor may move (UI-40): its old tier's anchor passes on, a message says so, undo puts it all back
anchors0 = s.get_anchors()
bw.move(2); pump(2)
assert s.get_word("serendipity")["tier"] == 2 and s.get_anchors()[0] not in (None, "serendipity")
assert app.anchors == s.get_anchors() and app.toast.cget("text").startswith("serendipity moved to B; the S anchor is now")
app.undo(); pump(2)
assert s.get_word("serendipity")["tier"] == 0 and s.get_anchors() == anchors0
bw.reload(keep_view=True); bw.tree.selection_set("serendipity"); pump(1)
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

# ---- empty states (UI-20): a friendly card instead of greyed-out cards
app.mode_var.set("conflict"); app.on_mode_change(); pump(3)
if app.pair is None:
    assert app.pair_empty.winfo_ismapped() and not app.duel.winfo_ismapped() and not app.pair_title.winfo_ismapped()
    assert app.pair_empty.title == "No conflicts"
    n0 = s.stats()["comparisons"]; key("Left"); assert s.stats()["comparisons"] == n0     # its keys are off
app.mode_var.set("refine"); app.on_mode_change(); pump(3)
assert app.duel.winfo_ismapped() and not app.pair_empty.winfo_ismapped()             # back to duels when there are some

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
root.event_generate("<Control-minus>"); root.event_generate("<KeyRelease-minus>"); pump(3); assert app.zoom == 1.2
z_before = app.zoom
app.set_zoom(9); assert z_before < app.zoom <= app.ZOOM_MAX            # as big as fits, at most the maximum
app.set_zoom(0); assert app.zoom == app.ZOOM_MIN                         # limits
root.event_generate("<Control-0>"); pump(3)
assert app.zoom == 1.0 and abs(_font("body").cget("size") - body0) <= 1
app.set_zoom(1.1); zoom_saved = s.get_meta("zoom"); app.set_zoom(1.0)
assert zoom_saved == "1.1"

# ---- Tab / Shift+Tab move between the tabs, skipping hidden ones (UI-47)
app.mode_var.set("place"); app.on_mode_change(); pump(2)
vis = [k for k, _ in T.MODES if k in app.mode_switch.visible]
assert len(vis) >= 3, vis
key("Tab"); pump(2); assert app.mode == vis[1] and app.mode_switch.get() == vis[1]
key("ISO_Left_Tab"); pump(2); assert app.mode == "place"                       # Shift+Tab (X11)
app.on_key(types.SimpleNamespace(keysym="Tab", time=None, state=1))            # Shift+Tab (Windows / macOS)
app.on_key_release(types.SimpleNamespace(keysym="Tab", time=None)); pump(2)
assert app.mode == vis[-1]                                                      # wraps round
key("Tab"); pump(2); assert app.mode == "place"
assert app.on_key(types.SimpleNamespace(keysym="Tab", time=None)) == "break"   # no focus traversal
app.on_key_release(types.SimpleNamespace(keysym="Tab", time=None))
pump(2); app.mode_var.set("place"); app.on_mode_change(); pump(2)
hidden = [k for k, _ in T.MODES if k not in app.mode_switch.visible]
for _ in range(len(T.MODES)):
    key("Tab"); pump(1); assert app.mode not in hidden                          # hidden tabs are skipped
app.mode_var.set("place"); app.on_mode_change(); pump(2)

# holding Ctrl + is paced like any held key, and once the screen is full a repeat only wiggles the one message
app.set_zoom(1.0); pump(2)
real_mono = time.monotonic
clock = {"t": 9000.0}
time.monotonic = lambda: clock["t"]
calls = []
real_apply = app._apply_zoom
app._apply_zoom = lambda z: (calls.append(z), real_apply(z))
ev = lambda t: types.SimpleNamespace(keysym="plus", time=t)
app._zoom_key(ev(1), 1)                                                         # first press: one step
for i in range(40):                                                            # held: 30 repeats a second
    clock["t"] += 0.033
    app.on_key_release(types.SimpleNamespace(keysym="plus", time=100 + i)); app._zoom_key(ev(100 + i), 1)
assert len(calls) <= 1 + (40 * 33 - 500) // 250 + 1, calls                     # paced, not 40 refits
app._zoom_cap[app._layout_key()] = round(app.zoom * app.grow + app.ZOOM_STEP, 2)   # the next step is known not to fit
n_calls = len(calls)
app.zoom_step(1); first = app.toast
assert first.cget("text") == app.ZOOM_FULL and len(calls) == n_calls          # refused without trying on screen
app.zoom_step(1); app.zoom_step(1)
assert app.toast is first and app.anim.is_running(f"wiggle{id(first)}")       # the same message wiggles
app._zoom_cap.clear()
app._apply_zoom, time.monotonic = real_apply, real_mono
app.on_key_release(types.SimpleNamespace(keysym="plus", time=999))
app.anim.finish_all(); app.set_zoom(1.0); pump(2)

# ---- a bigger window, bigger contents (UI-25): the fonts grow with the window, then shrink back with it
assert app._grow_for(*app._ref_size) == 1.0 and app._grow_for(app._ref_size[0] * 9, app._ref_size[1] * 9) == app.GROW_MAX
assert app._grow_for(app._ref_size[0] * 1.32, app._ref_size[1] * 2) == 1.3                  # the smaller ratio, in steps
assert app._grow_for(app._ref_size[0] / 2, app._ref_size[1]) == 1.0                         # never below normal
body1, word1 = _font("body").cget("size"), _font("word").cget("size")
min0 = root.minsize()
rw, rh = app._ref_size
root.geometry(f"{int(rw * 1.42)}x{int(rh * 1.42)}"); pump(12, 0.03)
assert app.grow == 1.4 and _font("body").cget("size") > body1 and _font("word").cget("size") > word1
assert root.minsize() == min0                                                   # can still be made small again
cw, ch = app._content_size(); assert cw <= root.winfo_width() and ch <= root.winfo_height()   # nothing clipped
app.mode_var.set("refine"); app.on_mode_change(); pump(3)
assert app.grow == 1.4                                                          # switching tabs keeps the size
app.mode_var.set("place"); app.on_mode_change(); pump(3)
root.geometry(f"{int(rw * 1.12)}x{int(rh * 1.12)}"); pump(12, 0.03); assert app.grow == 1.1   # one step down
root.geometry(f"{rw}x{rh}"); pump(12, 0.03)
assert app.grow == 1.0 and _font("body").cget("size") == body1 and _font("word").cget("size") == word1

# ---- a held key repeats like a keyboard: 500 ms before the first repeat, then at most every 250 ms;
#      faster auto-repeats are dropped (holding a tier key used to queue placements that went on after release)
app.mode_var.set("place"); app.on_mode_change(); pump(2)
real_now = time.monotonic
clock = [1000.0]
time.monotonic = lambda: clock[0]
placed0 = s.stats()["placed"]
ev = lambda t=None: types.SimpleNamespace(keysym="2", time=t)
app.on_key(ev(1))                                                     # first press: places at once
assert s.stats()["placed"] == placed0 + 1
for i in range(14):                                                   # Windows-style repeats, every 33 ms
    clock[0] += 0.033; app.on_key(ev())
assert s.stats()["placed"] == placed0 + 1                             # (14 x 33 ms < 500 ms) none of them place
clock[0] += 0.05; app.on_key(ev())                                    # past the 500 ms delay: one repeat
assert s.stats()["placed"] == placed0 + 2
for i in range(7):
    clock[0] += 0.033; app.on_key(ev())                               # within 250 ms: dropped
assert s.stats()["placed"] == placed0 + 2
clock[0] += 0.03; app.on_key(ev()); assert s.stats()["placed"] == placed0 + 3   # 250 ms later: the next one
app.on_key_release(types.SimpleNamespace(keysym="2", time=9))
clock[0] += 0.01; app.on_key(ev(10)); assert s.stats()["placed"] == placed0 + 4  # released and pressed again: at once
# X11-style auto-repeat: a release and a press with the same timestamp (still held)
app.on_key_release(types.SimpleNamespace(keysym="2", time=20)); clock[0] += 0.033; app.on_key(ev(20))
assert s.stats()["placed"] == placed0 + 4                             # recognised as held: dropped
app.on_key_release(types.SimpleNamespace(keysym="2", time=30))
time.monotonic = real_now
app.anim.finish_all(); root.after(900, root.quit); root.mainloop(); app.anim.finish_all(); pump(2)

# ---- calm stats (UI-15): one quiet line, "+N today" muted, the pace only on hover
import app as A
line = A.format_stats({"placed": 6506, "total": 9006, "skipped": 3, "conflicts": 0})
assert line == "Placed 6,506 of 9,006 (72.2%)   \u00b7   3 skipped", line          # no "N left" (UI-34)
assert "conflict" not in line                                       # only when there are some
assert A.format_stats({"placed": 1, "total": 2, "skipped": 0, "conflicts": 1}).endswith("1 conflict to look at")
assert "/hr" not in app.stats_lbl.cget("text") and "today" not in app.stats_lbl.cget("text")
# sorting fast through long and short words: the buttons never move (reported); the key hint stays on one line
app.mode_var.set("place"); app.on_mode_change(); pump(2)
long_short = ["incomprehensibilities", "ox", "electroencephalograph", "cat"]
s.insert_words(long_short)
s.db.executemany("UPDATE words SET qkey=? WHERE word=?", [(-100 + i, w) for i, w in enumerate(long_short)]); s.db.commit()
app.refresh(); pump(2)
spots = set()
for _ in range(4):
    key("2"); root.update()
    for _ in range(3):
        root.update(); time.sleep(0.01)
        spots.add(tuple((b.winfo_rootx(), b.winfo_rooty()) for b in (app.tier_btns[0], app.tier_btns[5], app.compare_btn, app.later_btn)))
app.anim.finish_all(); pump(2)
assert len(spots) == 1, spots
assert int(app.hint_lbl.cget("wraplength") or 0) == 0                            # no fixed wrap width
for _ in range(4):
    app.undo(); pump(1)
# the progress shelf (UI-14) follows placements
placed_before = sum(sp["placed"] for sp in app.progress_bar.data["spines"])
app.mode_var.set("place"); app.on_mode_change(); pump(2)
key("3"); app.anim.finish_all(); pump(2)
assert sum(sp["placed"] for sp in app.progress_bar.data["spines"]) == placed_before + 1
assert app.progress_bar.data == s.shelf()
app.undo(); pump(2); assert sum(sp["placed"] for sp in app.progress_bar.data["spines"]) == placed_before
n0 = int(app.today_lbl.cget("text").split()[0].lstrip("+").replace(",", ""))
app.mode_var.set("place"); app.on_mode_change(); pump(2)
key("4")
assert app.word_card.find_withtag("old")                            # UI-16: the old word is on its way out
app.anim.finish_all(); pump(2)
assert not app.word_card.find_withtag("old")
assert app.today_lbl.cget("text") == f"+{n0 + 1:,} today" and str(app.today_lbl.cget("foreground")) == T.PALETTE["muted"]
key("BackSpace"); pump(2); assert app.today_lbl.cget("text") == f"+{n0:,} today"   # undo takes it back
# the pace counts only active time (UI-33): a pause longer than PACE_GAP_S is a break and adds only that much
real_time = time.time
clock = {"t": 5000.0}
time.time = lambda: clock["t"]
app.session_count, app._active_s, app._last_action = 0, 0.0, clock["t"]
for _ in range(3):
    clock["t"] += 30; app._count_action()
assert app._pace_text() is None                                     # too early to talk about pace: no note
for _ in range(57):
    clock["t"] += 30; app._count_action()                            # 60 actions, 30 s apart: 120 per hour
assert app._pace_text() == "about +120/hr", app._pace_text()
clock["t"] += 3 * 3600; app._count_action()                          # back after 3 hours away
assert abs(app._active_s - (60 * 30 + app.PACE_GAP_S)) < 1e-6
assert app._pace_text() == f"about +{round(61 / ((60 * 30 + app.PACE_GAP_S) / 3600)):,}/hr"
assert app.today_tip.text_fn(None) == app._pace_text()
time.time = real_time
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
# switching tabs while a placement's animations still run: the tier chart must not show under the next tab's view
app.mode_var.set("place"); app.on_mode_change(); pump(2)
key("4"); app.mode_var.set("boundary"); app.on_mode_change(); app.anim.finish_all(); pump(3)
assert all(app.chart.itemcget(i, "state") == "hidden" for i in app.chart.find_withtag("all"))
# a held key's next repeat waits from when the last action finished (a slow save must still get to draw)
app.mode_var.set("refine"); app.on_mode_change(); pump(2)
real_mono = time.monotonic
clock = {"t": 1000.0}
time.monotonic = lambda: clock["t"]
def hold(dt):                                                 # an X11 auto-repeat: release + press, same timestamp
    clock["t"] += dt
    app.on_key_release(types.SimpleNamespace(keysym="Left", time=77)); app.on_key(types.SimpleNamespace(keysym="Left", time=77))
n0 = s.stats()["comparisons"]
app.on_key(types.SimpleNamespace(keysym="Left", time=1)); app.anim.finish_all()   # the first press acts
hold(0.6); app.anim.finish_all(); n1 = s.stats()["comparisons"]                       # past the delay: acts
assert n1 == n0 + 2
real_act = app._action_done
app._action_done = lambda e: (clock.__setitem__("t", clock["t"] + 0.4), real_act(e))   # each action takes 400 ms
hold(0.3); app.anim.finish_all(); n2 = s.stats()["comparisons"]; assert n2 == n1 + 1   # 300 ms since the last: acts
hold(0.1); app.anim.finish_all(); assert s.stats()["comparisons"] == n2               # only 100 ms since it finished
app._action_done = real_act; time.monotonic = real_mono
app.on_key_release(types.SimpleNamespace(keysym="Left", time=99)); pump(2)
# UI-31: each tab shows its own view in the chart's spot, on top of the others, which keep their space
sizes = set()
for m in ("place", "refine", "boundary", "conflict"):
    app.mode_var.set(m); app.on_mode_change(); pump(2)
    assert all(v.shown == (k == m) for k, v in app.tab_views.items()), m        # Boundary: none (archived)
    if m in app.tab_views:
        view = app.tab_views[m]
        assert str(root.tk.splitlist(root.tk.call("winfo", "children", str(view.master)))[-1]) == str(view)   # raised
    sizes.add((app.status_band.winfo_height(), app.center.winfo_rooty()))
assert len(sizes) == 1, sizes                                                   # the page never moves
app.mode_var.set("refine"); app.on_mode_change(); pump(2)
assert app.settled_chart.shares == s.settled_shares(app.SETTLED_DUELS)
app.mode_var.set("boundary"); app.on_mode_change(); pump(2)
if app.pair:                                                                    # swaps are still counted in the save
    n0 = s.swap_counts()
    side = "left" if s.get_word(app.pair["left"])["tier"] > s.get_word(app.pair["right"])["tier"] else "right"
    app._on_duel(side); app.anim.finish_all(); pump(3)                          # the lower-tier word wins: a swap
    assert sum(s.swap_counts()) == sum(n0) + 1
    app.undo(); pump(2); assert s.swap_counts() == n0
app.mode_var.set("conflict"); app.on_mode_change(); pump(2)
assert app.conflict_card.count == s.stats()["conflicts"]
app.mode_var.set("place"); app.on_mode_change(); pump(2)
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

# ---- tabs only when they have work (UI-46)
W = T.App.modes_with_work
assert W({"tiers": {}, "conflicts": 0}) == {"place"}
assert W({"tiers": {0: 1, 2: 1}, "conflicts": 0}) == {"place"}                     # no pair, no neighbours
assert W({"tiers": {0: 2}, "conflicts": 0}) == {"place", "refine"}
assert W({"tiers": {1: 1, 2: 1}, "conflicts": 3}) == {"place", "boundary", "conflict"}
app.anim.finish_all()
assert app.mode_switch.visible == W(s.stats())
app.mode_var.set("conflict"); app.on_mode_change(); pump(2)                      # opened by code: it shows while open
assert "conflict" in app.mode_switch.visible
if not s.stats()["conflicts"]:
    app.mode_var.set("place"); app.on_mode_change(); pump(2); app.anim.finish_all()
    assert "conflict" not in app.mode_switch.visible                             # and goes once you leave it
app.on_close()
print("UI OK")
