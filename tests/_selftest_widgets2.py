"""Widgets from UI-7 on: TierRow (and RoundButton's hover lift), DuelCards (and flat buttons), AnchorLadder,
TabBar, DropMenu and HeaderMenus (UI-10), Toast (UI-11),
DefinitionDrawer (UI-12), WordCard.transition_from (UI-16), LinkButton with words (UI-75)."""
import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import time, types
import tkinter as tk
import tkinter.font as tkfont
from theme import PALETTE, TIER_COLORS
from ui_motion import Animator
from widgets import ChoiceButton, EmptyCard, close_popups, watch_focus, WordCard, AnchorLadder, DropMenu, DuelCards, DefinitionDrawer, HeaderMenus, RoundButton, TabBar, TierRow, Toast

root = tk.Tk()
fnt = tkfont.Font(root=root, family="TkDefaultFont", size=16, weight="bold")

def update(n=3):
    for _ in range(n):
        root.update()

# ---- RoundButton lift=: rises off a shadow on hover, back down on leave and while pressed
clicks = []
b = RoundButton(root, "S", lambda: clicks.append(1), font=fnt, lift=3, hint="1")
b.pack(padx=10, pady=10); update()
plain = RoundButton(root, "S", lambda: None, font=fnt, hint="1"); plain.pack(); update()
import widgets as _W
assert plain._target()[1] == _W.lerp_color(plain._fill, PALETTE["text"], _W.EDGE) and _W.EDGE == 0.07   # (UI-78: softer)
assert b.winfo_reqheight() == plain.winfo_reqheight() + 3                     # room for the lift
y0 = b.coords("label")[1]
assert b.itemcget("shadow", "fill") == PALETTE["bg"]                         # shadow invisible at rest
b.event_generate("<Enter>"); update()
assert b.coords("label")[1] == y0 - 3 and b.itemcget("shadow", "fill") == PALETTE["shadow"]
b.event_generate("<ButtonPress-1>", x=5, y=8); update()
assert b.coords("label")[1] == y0 + 2                                         # pressed: back down, plus the dip
b.event_generate("<ButtonRelease-1>", x=5, y=8); update()
assert clicks == [1] and b.coords("label")[1] == y0 - 3                       # still hovered: lifted again
b.event_generate("<Leave>"); update()
assert b.coords("label")[1] == y0
b.event_generate("<Enter>"); update(); b.set_enabled(False); update()
assert b.coords("label")[1] == y0                                             # disabled: never lifted
b.set_enabled(True)
assert not plain.find_withtag("shadow")                                       # no lift, no shadow item

# ---- TierRow (UI-7)
picked = []
anim = Animator(root)
row = TierRow(root, ["S", "A", "B", "C", "D", "F"], picked.append, font=fnt, animator=anim)
row.pack(); update()
assert len(row.buttons) == 6 and [x.cget("text") for x in row.buttons] == list("SABCDF")
assert [x.cget("hint") for x in row.buttons] == [str(i) for i in range(1, 7)]
assert [x.cget("bg") for x in row.buttons] == TIER_COLORS
xs = [x.winfo_x() for x in row.buttons]
assert xs == sorted(xs), "pills run S..F left to right"
ys = row.buttons[2].coords("label")[1]
row.buttons[2].flash(); update(1)
assert row.buttons[2].coords("label")[1] == ys + 2                             # the key's dip (UI-18 calls it)
root.after(150, root.quit); root.mainloop()
assert row.buttons[2].coords("label")[1] == ys                                 # ...and back up
# a click on a pill picks it
p = row.buttons[5]
p.event_generate("<Enter>"); p.event_generate("<ButtonPress-1>", x=6, y=8); update()
p.event_generate("<ButtonRelease-1>", x=6, y=8); update()
assert picked == [5]
# pill shape: radius clamps to half the height (a true pill)
assert p.smooth_image("shape") is not None

# ---- flat RoundButton (UI-8): no fill or outline at rest, a soft fill on hover
f = RoundButton(root, "Skip pair", lambda: None, font=fnt, flat=True); f.pack(); update()
assert f.itemcget("shape", "fill") == PALETTE["bg"] == f.itemcget("shape", "outline")
assert f.itemcget("label", "fill") == PALETTE["muted"]
f.event_generate("<Enter>"); update()
assert f.itemcget("shape", "fill") == PALETTE["surface2"] and f.itemcget("label", "fill") == PALETTE["text"]
f.set_enabled(False); update(); assert f.itemcget("label", "fill") == PALETTE["disabled"]

# ---- DuelCards (UI-8)
answers = []
small = tkfont.Font(root=root, family="TkDefaultFont", size=11)
duel = DuelCards(root, answers.append, fnt, small, animator=anim)
duel.pack(); duel.show("apple", "pear"); update()
assert duel.left.cget("text") == "apple" and duel.right.cget("text") == "pear"
assert "A" in duel.left.cget("hint") and "L" in duel.right.cget("hint") and "T" in duel.tie.cget("hint")
assert duel.left.cget("bg") == PALETTE["left"] and duel.right.cget("bg") == PALETTE["right"]
assert duel.left.winfo_width() == duel.right.winfo_width()                   # same width, whatever the words
assert duel.left.winfo_x() < duel.right.winfo_x()
assert duel.tie.winfo_rooty() > duel.left.winfo_rooty() + duel.left.winfo_height() - 5   # Tie / Skip under the cards
duel.left.event_generate("<Enter>"); update(); anim.finish_all()
assert duel.left.itemcget("shape", "outline") == PALETTE["accent"] and float(duel.left.itemcget("shape", "width")) == 3
duel.left.event_generate("<Leave>"); update()
assert set(duel.buttons) == {"left", "right", "tie", "skip"}
duel.set_enabled(False); assert not any(b.enabled for b in duel.buttons.values())
duel.show("a", "b"); assert all(b.enabled for b in duel.buttons.values())    # show() re-enables
b = duel.tie; b.event_generate("<Enter>"); b.event_generate("<ButtonPress-1>", x=6, y=6); update()
b.event_generate("<ButtonRelease-1>", x=6, y=6); update(); assert answers[-1] == "tie"

# resolve (UI-19): the winner lifts, the loser dims, then the next pair
nxt = []
duel.show("a", "b"); update(); anim.finish_all()
yw = duel.right.coords("label")[1]
duel.resolve("right", anim, lambda: nxt.append(1)); update(1)
assert not duel.left.enabled and duel.right.enabled and not nxt                 # loser dims at once
anim.finish_all(); update(1)
assert duel.right.coords("label")[1] == yw - DuelCards.LIFT and nxt == [1]      # winner up, then on to the next
duel.show("c", "d", colors=(TIER_COLORS[1], TIER_COLORS[2])); update()
assert duel.left.cget("bg") == TIER_COLORS[1] and duel.right.cget("bg") == TIER_COLORS[2]   # tier colours
assert duel.right.coords("label")[1] == yw and duel.left.enabled                # the next pair starts fresh
anim.reduce_motion = True
duel.resolve("left", anim, lambda: nxt.append(2)); assert nxt == [1, 2]         # Reduce motion: straight on
anim.reduce_motion = False

# ---- AnchorLadder (UI-9)
lad = AnchorLadder(root, list("SABCDF"), small, animator=anim); lad.pack(); update()
assert len(lad.find_withtag("pill")) == 6 and lad.itemcget("txt0", "text") == "S"
assert lad.itemcget("pill0", "fill") == TIER_COLORS[0] and not lad.find_withtag("caret")
lad.update_range(0, 5, 2); anim.finish_all()
assert lad.possible() == [0, 1, 2, 3, 4, 5] and lad.find_withtag("caret")
assert lad.itemcget("pill2", "outline") == PALETTE["accent"] and float(lad.itemcget("pill2", "width")) == 3
cx = sum(lad.coords("caret")[0::2]) / 3; px = lad.coords("pill2")[0::2]
assert min(px) < cx < max(px), "caret sits under the asked tier"
lad.update_range(3, 5, 4)                                    # "worse than B": S..B ruled out
assert lad.itemcget("pill0", "fill") == TIER_COLORS[0]       # mid-animation: not faded yet
anim.finish_all()
assert lad.possible() == [3, 4, 5]
assert lad.itemcget("pill0", "fill") != TIER_COLORS[0] and lad.itemcget("pill3", "fill") == TIER_COLORS[3]
assert lad.itemcget("txt0", "fill") == PALETTE["disabled"] and lad.itemcget("txt4", "fill") == PALETTE["text"]
assert float(lad.itemcget("pill2", "width")) == 1            # the ring moved on
anim.reduce_motion = True
lad.update_range(4, 4, 4); assert lad.possible() == [4] and lad.itemcget("pill5", "fill") != TIER_COLORS[5]   # jumps
anim.reduce_motion = False
w0 = lad.winfo_reqwidth(); small.configure(size=20); lad.refresh(); assert lad.winfo_reqwidth() > w0
small.configure(size=11)

# ---- TabBar (UI-10): folder tabs on the page line
changes = []
opts = [("place", "Place new words"), ("refine", "Refine within tier"), ("boundary", "Boundary check")]
seg = TabBar(root, opts, changes.append, small, animator=anim, page_bg=PALETTE["bg"])
seg.pack(fill="x"); root.geometry("900x700"); update(5)
assert seg.get() == "place" and len(seg.find_withtag("label")) == 3
def seg_click(key):
    x = int(seg.tab_x(key))
    seg.event_generate("<Motion>", x=x, y=10); seg.event_generate("<ButtonRelease-1>", x=x, y=10); update()
assert seg.itemcget("label_place", "fill") == PALETTE["text"] and seg.itemcget("label_refine", "fill") == PALETTE["muted"]
# the page line runs the full width, with a gap exactly under the open tab
bl, br = seg.coords("baseline_left"), seg.coords("baseline_right")
tab = seg.coords("tabfill")
assert bl[0] == 0 and br[2] >= seg.winfo_width() - 1 and bl[1] == bl[3] == br[1]
assert abs(bl[2] - min(tab[0::2])) < 1 and abs(br[0] - max(tab[0::2])) < 1
assert min(tab[0::2]) < seg.tab_x("place") < max(tab[0::2])
assert seg.itemcget("tabfill", "fill") == PALETTE["bg"]                          # the open tab is page coloured
assert max(tab[1::2]) > bl[1]                                                    # and reaches over the line
edge = seg.coords("tabedge"); assert max(edge[1::2]) <= bl[1] + 1               # its outline is open at the bottom
t0 = min(tab[0::2])
seg_click("boundary")
assert changes == ["boundary"] and seg.get() == "boundary"
anim.finish_all(); assert min(seg.coords("tabfill")[0::2]) > t0 + 100           # the open tab slid over
assert min(seg.coords("tabfill")[0::2]) < seg.tab_x("boundary") < max(seg.coords("tabfill")[0::2])
seg_click("boundary"); assert changes == ["boundary"]                           # clicking the open one: nothing
seg.event_generate("<Motion>", x=int(seg.tab_x("place")), y=10); update()
assert seg.itemcget("hoverfill", "state") == "normal"                            # hover tint on another tab
seg.set("refine"); anim.finish_all(); assert seg.get() == "refine" and changes == ["boundary"]   # set() is silent
seg.set("nonsense"); assert seg.get() == "refine"
seg.event_generate("<Leave>"); update()
assert seg.itemcget("hoverfill", "state") == "hidden"
assert seg.itemcget("label_refine", "fill") == PALETTE["text"] and seg.itemcget("label_place", "fill") == PALETTE["muted"]
root.geometry("1300x700"); update(5)
assert seg.coords("baseline_right")[2] >= seg.winfo_width() - 1                 # follows the window width
# tabs with nothing to do fold away (UI-46); the open one always stays
seg.set("place"); anim.finish_all()
seg.show_only({"boundary"}); update()
assert anim.is_running(f"tabfold{id(seg)}")                                      # folds, not jumps
anim.finish_all(); assert seg.visible == {"place", "boundary"}
assert seg.itemcget("label_refine", "state") == "hidden" and seg.itemcget("label_boundary", "state") == "normal"
assert seg._index_at(seg.tab_x("refine")) != "refine"                           # a folded tab can't be clicked
assert seg.tab_x("place") < seg.tab_x("boundary")
mid = seg.winfo_width() / 2
assert abs((seg.tab_x("place") + seg.tab_x("boundary")) / 2 - mid) < 2           # the rest stay centred
seg_click("boundary"); anim.finish_all(); assert seg.get() == "boundary" and changes[-1] == "boundary"
assert min(seg.coords("tabfill")[0::2]) < seg.tab_x("boundary") < max(seg.coords("tabfill")[0::2])
seg.show_only(set()); anim.finish_all(); assert seg.visible == {"boundary"}     # the open tab never vanishes
seg.show_only({"place", "refine", "boundary"}, animate=False)
assert seg.itemcget("label_refine", "state") == "normal" and not anim.is_running(f"tabfold{id(seg)}")

# ---- DropMenu and HeaderMenus (UI-10)
ran, chk = [], tk.BooleanVar(value=False)
items = [("command", "Export...", lambda: ran.append("export"), None), ("separator",),
         ("check", "Reduce motion", chk, lambda: ran.append(("motion", chk.get()))),
         ("command", "Undo", lambda: ran.append("undo"), "Ctrl+Z")]
assert DropMenu.labels(items) == ["Export...", "Reduce motion", "Undo"]
dm = DropMenu(root, items, small)
dm.open(50, 60); update()
assert dm.is_open() and dm.win.winfo_viewable() and len(dm._rows) == 3
texts = [[p.cget("text") for p in parts] for _r, parts, _i in dm._rows]
assert texts[2] == ["", "Undo", "Ctrl+Z"] and texts[1][1] == "Reduce motion" and texts[1][0] == ""   # unchecked
dm._step(1); dm._step(1)
assert dm._rows[1][0].cget("bg") == PALETTE["select_bg"] and dm._rows[0][0].cget("bg") == PALETTE["surface"]
dm.invoke(1); update()
assert not dm.is_open() and chk.get() is True and ran == [("motion", True)]
dm.open(50, 60); update()
assert dm._rows[1][1][0].cget("text") == "\u2713"                              # now shows its check mark
dm._rows[0][1][1].event_generate("<ButtonRelease-1>"); update()
assert ran[-1] == "export" and not dm.is_open()
closed = []
dm.open(10 ** 5, 10 ** 5, on_close=lambda: closed.append(1)); update()          # kept on screen
assert dm.win.winfo_rootx() + dm.win.winfo_width() <= dm.win.winfo_screenwidth()
dm.win.event_generate("<Escape>"); update()
assert not dm.is_open() and closed == [1]

hm = HeaderMenus(root, [("File", items), ("Edit", items[3:])], small, animator=anim); hm.pack(side="top"); update()
fb, eb = hm.buttons["File"], hm.buttons["Edit"]
fb.event_generate("<Enter>"); fb.event_generate("<ButtonPress-1>", x=5, y=5); update()
fb.event_generate("<ButtonRelease-1>", x=5, y=5); update()
assert hm.open_name == "File" and hm.drops["File"].is_open()
anim.finish_all(); assert fb.itemcget("shape", "fill") == PALETTE["select_bg"]  # its button looks open
d = hm.drops["File"].win
assert abs(d.winfo_rootx() - fb.winfo_rootx()) <= 1 and d.winfo_rooty() >= fb.winfo_rooty() + fb.winfo_height()
eb.event_generate("<Enter>"); update()                                         # hover switches menus
assert hm.open_name == "Edit" and hm.drops["Edit"].is_open() and not hm.drops["File"].is_open()
anim.finish_all(); assert fb.itemcget("shape", "fill") != PALETTE["select_bg"]
eb.event_generate("<ButtonPress-1>", x=5, y=5); eb.event_generate("<ButtonRelease-1>", x=5, y=5); update()
assert hm.open_name is None                                                    # its own button closes it
hm.open_menu("File"); update()
seg.event_generate("<ButtonPress-1>", x=3, y=3); update()                      # a click elsewhere closes it
assert hm.open_name is None and not hm.drops["File"].is_open()
hm.open_menu("Edit"); update(); hm.drops["Edit"].invoke(0); update()
assert ran[-1] == "undo" and hm.open_name is None
# UI-27: Left / Right move to the neighbouring menu (wrapping); closing hands the keyboard focus back
hm.open_menu("File"); update()
hm.drops["File"].win.event_generate("<Right>"); update(); assert hm.open_name == "Edit"
hm.drops["Edit"].win.event_generate("<Right>"); update(); assert hm.open_name == "File"     # wraps round
hm.drops["File"].win.event_generate("<Left>"); update(); assert hm.open_name == "Edit"
hm.close(); update()
ent = tk.Entry(root); ent.pack(); ent.focus_force(); update()
hm.open_menu("File"); update(); assert str(root.tk.call("focus")).startswith(str(hm.drops["File"].win))
hm.drops["File"].win.event_generate("<Escape>"); update()
assert not hm.drops["File"].is_open() and str(root.tk.call("focus")) == str(ent)       # keys work again
ent.destroy()

# ---- ChoiceButton (UI-43): a drop-down choice made of a button and a DropMenu (no input grab)
cwin = tk.Toplevel(root)
cv = tk.StringVar(value="All tiers"); picked_c = []
cb = ChoiceButton(cwin, cv, ["All tiers", "S", "A"], on_change=lambda: picked_c.append(cv.get()), font=small,
                  animator=anim)
cb.pack(padx=20, pady=20); update()
assert cb.cget("text").startswith("All tiers") and "\u25be" in cb.cget("text")
w_all = cb.winfo_reqwidth()
cv.set("S"); update(); assert cb.cget("text").startswith("S") and cb.winfo_reqwidth() == w_all   # steady width
cb.toggle(); update()
assert cb.menu.is_open() and cb.menu in DropMenu.open_menus
marks = [parts[0].cget("text") for _r, parts, _i in cb.menu._rows]
assert marks == ["", "\u2713", ""]                                                # a check on the current one
cb.menu.invoke(2); update()
assert cv.get() == "A" and picked_c == ["A"] and not cb.menu.is_open() and cb.menu not in DropMenu.open_menus
cb.set_values(["All boundaries", "S | A"]); cv.set("All boundaries"); update()
assert cb.cget("text").startswith("All boundaries")
cb.toggle(); update(); cb.toggle(); update(); assert not cb.menu.is_open()       # clicking again closes it

# ---- UI-43: switching to another program closes every open drop-down; none is "always on top"
cb.toggle(); hm.open_menu("File"); update()
assert hm.open_name == "File" and str(hm.drops["File"].win.attributes("-topmost")) in ("0", "False")
assert len(DropMenu.open_menus) == 2
close_popups(); update()
assert hm.open_name is None and not cb.menu.is_open() and not DropMenu.open_menus
lost = []
check = watch_focus(root, on_lost=lambda: lost.append(1))
hm.open_menu("Edit"); update()
real_tk = root.tk
class FakeTk:                                                                    # what Tcl says has the focus
    def __init__(self, answer): self.answer = answer
    def call(self, *a): return self.answer if a == ("focus",) else real_tk.call(*a)
    def __getattr__(self, name): return getattr(real_tk, name)
root.tk = FakeTk("")                                                             # the program lost focus
check(); root.tk = real_tk; update()
assert hm.open_name is None and lost == [1]
hm.open_menu("Edit"); update()
root.tk = FakeTk(".x.popdown"); check(); root.tk = real_tk                       # focus still inside the program
assert hm.open_name == "Edit"
hm.close(); cwin.destroy()

# ---- Toast (UI-11)
page = tk.Frame(root, width=600, height=300, bg=PALETTE["bg"]); page.pack(); update()
other = tk.Label(page, text="stays put"); other.place(x=10, y=100); update()
oy = other.winfo_y()
toast = Toast(root, small, animator=anim)
assert toast.cget("text") == "" and toast.cget("font") is small
toast.show("apple  ->  S", tint=(TIER_COLORS[0], PALETTE["text"]), ms=200, in_=page); update()
assert toast.cget("text") == "apple  ->  S" and toast.winfo_ismapped() and other.winfo_y() == oy   # floats
assert toast.itemcget("pill", "fill") != TIER_COLORS[0]                         # fading in from the page colour
anim.finish_all(); assert toast.itemcget("pill", "fill") == TIER_COLORS[0] and toast.itemcget("text", "fill") == PALETTE["text"]
cx = toast.winfo_rootx() + toast.winfo_width() / 2; px = page.winfo_rootx() + page.winfo_width() / 2
assert abs(cx - px) <= 2 and 0 < (page.winfo_rooty() + page.winfo_height()) - (toast.winfo_rooty() + toast.winfo_height()) <= 20   # centred, near the bottom
toast.show("pear", ms=5000, in_=page); anim.finish_all()                         # a new message replaces it
assert toast.cget("text") == "pear" and toast.itemcget("pill", "fill") == TIER_COLORS[0]   # (keeps the last tint)
toast.hide(); assert toast.cget("text") == "pear"; anim.finish_all(); update()   # fades out, then it is gone
assert toast.cget("text") == "" and not toast.winfo_ismapped()
toast.show("short", ms=60, in_=page); anim.finish_all()
root.after(120, root.quit); root.mainloop(); anim.finish_all(); update()         # the timer hides it
assert toast.cget("text") == "" and not toast.winfo_ismapped()
toast.show("x " * 200, ms=1000, in_=page, wraplength=300); anim.finish_all(); update()
assert toast.winfo_reqwidth() < 400 and toast.winfo_reqheight() > 40             # long messages wrap
# fling(): rises from the card, rests, then flies to its landing point (its tier's bar) and fades out completely
def toast_xy():
    return toast.winfo_rootx() + toast.winfo_width() / 2 - px, toast.winfo_rooty() - page.winfo_rooty()
landed = []
toast.fling("apple  ->  S", (TIER_COLORS[0], PALETTE["text"]), start_bottom=180, rest_bottom=60, target=(200, -30),
            hold_ms=60, in_=page, on_arrive=lambda: landed.append(1))
update(); x0, y0 = toast_xy()
assert y0 > 100 and abs(x0) <= 2 and toast.itemcget("pill", "fill") != TIER_COLORS[0]    # starts low, faint
anim.finish_all(); update(); x1, y1 = toast_xy()
assert abs(y1 + toast.winfo_height() - 60) <= 1 and abs(x1) <= 2                 # risen to its resting place
anim.finish_all(); assert toast.itemcget("pill", "fill") not in (TIER_COLORS[0], PALETTE["bg"])   # paled a bit
assert toast.cget("text") == "apple  ->  S" and not landed
root.after(100, root.quit); root.mainloop(); update()                          # the rest is over: flying
xs0 = toast_xy(); root.after(60, root.quit); root.mainloop(); update()
xs1 = toast_xy(); assert xs1[0] > xs0[0] + 10 and xs1[1] < xs0[1]               # heading up and to the right
anim.finish_all(); update()
assert landed == [1] and toast.cget("text") == "" and not toast.winfo_ismapped()  # landed, fully faded
assert int(toast.cget("width")) < 40                                            # it shrank into a small drop
# M-2: with clear= (the top of the tallest bar) it goes over the bars and comes down onto its own from above,
# stopping just above the landing point: the drop is opaque, and it used to brush the bars' tops (a pale square)
toast.fling("over", (TIER_COLORS[0], PALETTE["text"]), start_bottom=180, rest_bottom=60, target=(200, -30),
            hold_ms=10, in_=page, clear=-70)
anim.finish_all(); anim.finish_all()
seen, t0 = [], time.perf_counter()
while toast.cget("text") and time.perf_counter() - t0 < 2:
    root.update(); time.sleep(0.004)
    if toast.winfo_ismapped():
        x, y = toast_xy(); seen.append((x, y + toast.winfo_height()))
assert len(seen) > 6
assert all(bottom <= -70 for x, bottom in seen if 100 < x < 195), seen          # over the chart: above every bar
assert abs(seen[-1][0] - 200) <= 2 and -40 < seen[-1][1] <= -31, seen[-1]       # ends resting on its bar
toast.fling("old", (TIER_COLORS[2], PALETTE["text"]), start_bottom=180, rest_bottom=60, target=(200, -30),
            hold_ms=10, in_=page, on_arrive=lambda: landed.append(2))
toast.show("cut short", in_=page); anim.finish_all(); root.after(60, root.quit); root.mainloop(); anim.finish_all()
assert landed == [1]                                                           # a replaced fling never "lands"
toast.hide(); anim.finish_all()

# hurry(): a newer message has started; the old one speeds through its stages and still lands
toast.fling("fast", (TIER_COLORS[1], PALETTE["text"]), start_bottom=180, rest_bottom=60, target=(100, -30),
            hold_ms=5000, in_=page, on_arrive=lambda: landed.append(3))
update(); toast.hurry()
t0 = time.perf_counter()
while toast.cget("text") and time.perf_counter() - t0 < 2:
    root.update(); time.sleep(0.005)
assert landed[-1] == 3 and time.perf_counter() - t0 < 0.6                      # landed well before the 5 s rest
gone = []
t2 = Toast(root, small, animator=anim, on_gone=gone.append)
t2.show("bye", ms=5000, in_=page); update(); t2.hurry()
t0 = time.perf_counter()
while t2.cget("text") and time.perf_counter() - t0 < 2:
    root.update(); time.sleep(0.005)
assert gone == [t2] and time.perf_counter() - t0 < 0.6                         # a plain message fades out fast
t2.hurry()                                                                     # already gone: no-op
t2.destroy()

# under(): over the white card the toast borrows white as its backdrop, back on the page it is cream again
toast.fling("card", (TIER_COLORS[3], PALETTE["text"]), start_bottom=180, rest_bottom=60, target=(50, 0),
            hold_ms=10, in_=page, under=lambda x0, y0, x1, y1: PALETTE["surface"] if y0 > 100 else PALETTE["bg"])
update(); assert toast.cget("bg") == PALETTE["surface"]
anim.finish_all(); update(); assert toast.cget("bg") == PALETTE["bg"]
anim.finish_all(); root.after(40, root.quit); root.mainloop(); anim.finish_all()
# under() is asked with the toast's whole rectangle (reported: a white box beside the card, over the buttons,
# when the backdrop went by height alone), and a long message narrows to a round drop before it reaches the bars
rects = []
def under_rect(x0, y0, x1, y1):
    rects.append((x0, y0, x1, y1)); return PALETTE["surface"] if x1 < 150 else PALETTE["bg"]
toast.fling("a rather long message for a drop", (TIER_COLORS[3], PALETTE["text"]), start_bottom=180, rest_bottom=60,
            target=(200, 0), hold_ms=10, in_=page, under=under_rect)
update(); x0r, y0r, x1r, y1r = rects[-1]
assert abs((x1r - x0r) - int(toast.cget("width"))) <= 1 and abs((y1r - y0r) - int(toast.cget("height"))) <= 1
assert toast.cget("bg") == PALETTE["bg"]                                    # beside the "card": cream, never white
wide = int(toast.cget("width"))
anim.finish_all(); anim.finish_all()                                        # risen and rested: now it flies
sizes, t0 = [], time.perf_counter()
while toast.cget("text") and time.perf_counter() - t0 < 2:
    root.update(); time.sleep(0.004); sizes.append((int(toast.cget("width")), int(toast.cget("height"))))
late = sizes[len(sizes) // 2:]                                              # the second half of the flight
assert len(sizes) > 6 and all(w <= h + 4 < wide / 3 for w, h in late), sizes  # a drop, not a bar, over the chart
# a new message cuts a fling short, and the old one's pending stages do nothing
toast.fling("old", (TIER_COLORS[1], PALETTE["text"]), start_bottom=180, rest_bottom=60, target=(-100, 0), hold_ms=10, in_=page)
toast.show("new", ms=5000, in_=page); anim.finish_all()
root.after(60, root.quit); root.mainloop(); anim.finish_all(); update()
assert toast.cget("text") == "new" and toast.winfo_ismapped() and abs(toast_xy()[0]) <= 2
toast.hide(); anim.finish_all()
anim.reduce_motion = True
toast.fling("still", (TIER_COLORS[2], PALETTE["text"]), start_bottom=180, rest_bottom=60, target=(-100, 0), hold_ms=30, in_=page); update()
assert toast.cget("text") == "still" and abs(toast_xy()[1] + toast.winfo_height() - 60) <= 1         # Reduce motion: straight to rest
root.after(80, root.quit); root.mainloop(); update()
assert toast.cget("text") == ""                                                # then simply gone
toast.show("jump", (PALETTE["ok"][0], PALETTE["ok"][1]), in_=page); assert toast.itemcget("pill", "fill") == PALETTE["ok"][0]
toast.hide(); assert toast.cget("text") == ""                                     # no fade with Reduce motion
anim.reduce_motion = False

# ---- DefinitionDrawer (UI-12)
head = tkfont.Font(root=root, family="TkDefaultFont", size=13, weight="bold")
dwin = tk.Toplevel(root)                                                         # room of its own
dr = DefinitionDrawer(dwin, {"body": small, "head": head}, animator=anim)
defs = {"apple": '1. (noun) a round fruit\n      e.g. "an apple a day"\n2. (verb) to pick apples'}
dr.show_words(["apple", "pear"], defs.get)
txt = dr.text.get("1.0", "end")
assert txt.startswith("apple\n1.  noun  a round fruit\n\u201can apple a day\u201d\n2.  verb  to pick apples")
assert "pear" not in txt and dr.text2.get("1.0", "end").startswith("pear\nLooking up definition...")
assert dr.columns == 2 and dr.text2.winfo_manager() == "grid"                 # (two words: side by side, asked for)
dr.update_idletasks()
assert dr.text.winfo_reqwidth() + dr.text2.winfo_reqwidth() + 1 <= dr.COLUMN_CHARS * small.measure("0") + 28   # (no
                                                                                 # wider than the one column)
dr.set_lines(5); assert dr.lines() == 5 and int(dr.text2.cget("height")) == 5
dr.show_words(["apple", "pear"], defs.get, back=("Back to x", lambda: None))
assert dr.columns == 1 and not dr.text2.winfo_manager()                         # (a lookup: one column again)
dr.set_lines(9)
dr.show_words(["apple", "pear"], defs.get)
def tags_at(word):
    i = dr.text.search(word, "1.0"); return set(dr.text.tag_names(i))
assert "head" in tags_at("apple") and "pos" in tags_at("noun") and "ex" in tags_at("an apple a day")
assert "wait" in dr.text2.tag_names(dr.text2.search("Looking up", "1.0")) and "num" in tags_at("2.")
assert dr.text.tag_cget("pos", "font") and "italic" in str(tkfont.Font(root=root, font=dr.text.tag_cget("pos", "font")).actual("slant"))
assert str(dr.text.cget("state")) == "disabled"
assert not dr.is_open
dr.pack(side="bottom", fill="x"); update()
full = dr.winfo_reqheight()
dr.open(); update()
assert dr.is_open and dr.winfo_height() < full                                  # easing open from nothing
anim.finish_all(); update(); assert abs(dr.winfo_height() - full) <= 2, (dr.winfo_height(), full, dr.winfo_reqheight(), root.winfo_height())
# F-29 (asked for: comparing shrank it in one jump): a fit that shortens it eases it there from where it was
dr.set_lines(9); update(); anim.finish_all(); update()
assert dr.steady
tall = dr.winfo_height()
dr.set_lines(4); update()
dr.ease_from(tall); update()
mid = dr.winfo_height()
assert dr.easing and mid >= tall - 2, (tall, mid)                             # (from where it was: not jumped)
seen = [mid]
for _ in range(30):
    root.update(); time.sleep(0.01); seen.append(dr.winfo_height())
assert seen[-1] < tall and all(b <= a for a, b in zip(seen, seen[1:])) and len(set(seen)) > 3, seen
assert not dr.easing and dr.steady
dr.set_lines(9); update(); anim.finish_all(); update()
# F-23: a window that grows for it only after the slide began (a slow window manager) adds the room on top of the
# height it has: taken as its whole height, the pane's top edge and its text dropped a little
dr.pack_forget(); dr.collapse(); dr.pack(side="bottom", fill="x"); update()
dr.open(); update()
was = dr.winfo_height()
dr.give(30); update()
assert dr.winfo_height() == min(full, was + 30), (was, dr.winfo_height(), full)
dr.give(5000); update(); assert dr.winfo_height() <= full                       # (never past its own height)
anim.finish_all(); update()
closed = []
dr.close(on_closed=lambda: (closed.append(1), dr.pack_forget())); update()
assert not dr.is_open and not closed and dr.winfo_height() > 1                   # still closing
anim.finish_all(); update(); assert closed == [1] and not dr.winfo_manager()
dr.set_open(True); assert dr.is_open
small.configure(size=14); dr.show_words(["apple"], defs.get)                  # italics follow the body size
assert dr.columns == 1 and int(dr.text.cget("width")) == dr.COLUMN_CHARS
assert tkfont.Font(root=root, font=dr.text.tag_cget("pos", "font")).actual("size") == 14
from widgets import refresh_widgets
small.configure(size=16); refresh_widgets(root)                               # a zoom, without filling it again
for tag in ("pos", "ex"):                                                       # (reported: they kept the old size)
    assert tkfont.Font(root=root, font=dr.text.tag_cget(tag, "font")).actual("size") == 16, tag
small.configure(size=14); refresh_widgets(root)
small.configure(size=11)
# F-3: a meaning that only names another word shows that word's first real meaning under it, muted (once per word)
defs.update({"apples": "1. (noun) plural of apple\n2. (noun) Alternative form of apple.",
             "kumquats": "1. (noun) plural of kumquat", "fruits": "1. (noun) plural of fruit"})
defs["fruit"] = "1. (noun) plural of fruits\n2. (noun) The seed-bearing part of a plant."
dr.show_words(["apples"], defs.get)
txt = dr.text.get("1.0", "end")
assert txt.count("apple (noun): a round fruit") == 1, txt
assert "base" in tags_at("apple (noun)") and "base" in tags_at("a round fruit")
dr.show_words(["kumquats"], defs.get)
assert "kumquat: Looking up definition..." in dr.text.get("1.0", "end")       # (filled in when it arrives)
dr.show_words(["fruits"], defs.get)
assert "fruit (noun): The seed-bearing part" in dr.text.get("1.0", "end")    # (its first meaning that is no form)
from definitions import form_target
assert form_target("Alternative form of bull dyke.") == "bull dyke" and form_target("A form of government.") is None
assert form_target("third-person singular simple present indicative of take") == "take"
assert form_target("Alternative letter-case form of Gypsy (\u201ca member\u201d).") == "Gypsy"

# ---- WordCard.transition_from (UI-16): the old word nudges toward its tier and fades, the new one eases in
cwin = tk.Toplevel(root)
wf = tkfont.Font(root=root, family="TkDefaultFont", size=40, weight="bold")
card = WordCard(cwin, wf, small); card.pack(padx=20, pady=20)
card.set("apple", "rank #1"); update()
rest = card.coords("word")
card.set("pear", "rank #2"); card.transition_from("apple", "rank #1", dx=10, dy=12, animator=anim); update(1)
assert card.itemcget("oldword", "text") == "apple" and card.itemcget("word", "text") == "pear"
assert card.coords("word")[1] > rest[1]                                    # new word starts a little low...
assert card.itemcget("word", "fill") != PALETTE["text"]                     # ...and faint
root.after(90, root.quit); root.mainloop()
mid = card.coords("oldword"); assert mid[0] > rest[0] and mid[1] > rest[1]   # old word on its way (right, down)
anim.finish_all(); update(1)                                                # a key press: straight to the end
assert not card.find_withtag("old") and card.coords("word") == card.coords("word")
assert abs(card.coords("word")[1] - card._word_xy[1]) < 0.5 and card.itemcget("word", "fill") == PALETTE["text"]
# a redraw in the middle (window resized) still ends with the word exactly in place
card.set("plum", "rank #3"); card.transition_from("pear", "rank #2", dx=-10, dy=12, animator=anim); update(1)
card.set("plum", "rank #3"); anim.finish_all(); update(1)
assert abs(card.coords("word")[1] - card._word_xy[1]) < 0.5 and not card.find_withtag("old")
# reported: a white flash when placing fast. A redraw mid-transition (the card resizing for the next word) keeps
# the outgoing word, above the card's face, and the two words always have about one word's worth of ink between them
card.set("kiwi", "rank #4"); card.transition_from("plum", "rank #3", dx=10, dy=12, animator=anim); update(1)
card.set("kiwi", "rank #4")                                                 # what a resize does
items = card.find_all()
assert card.find_withtag("oldword") and items.index(card.find_withtag("oldword")[0]) > items.index(card.find_withtag("card")[0])
assert card.itemcget("oldword", "text") == "plum"
for p in (0.0, 0.25, 0.5, 0.75, 1.0):
    card._frame(p)
    ink = sum(1 - sum(int(card.itemcget(t, "fill")[i:i + 2], 16) for i in (1, 3, 5)) / 765 for t in ("oldword", "word"))
    assert ink > 0.6 * (1 - sum(int(PALETTE["text"][i:i + 2], 16) for i in (1, 3, 5)) / 765), p
# the darker word is always on top (a pale one over a dark one cut white gaps through it: reported)
above = lambda a, b: card.find_all().index(card.find_withtag(a)[0]) > card.find_all().index(card.find_withtag(b)[0])
card._frame(0.1); assert above("oldword", "word") and above("oldsub", "sub")
card._frame(0.9); assert above("word", "oldword") and above("sub", "oldsub")
anim.finish_all(); update(1); assert not card.find_withtag("old")
anim.reduce_motion = True                                                   # Reduce motion: no transition at all
card.set("fig", ""); card.transition_from("plum", "rank #3", dx=10, dy=12, animator=anim)
assert not card.find_withtag("old") and card.itemcget("word", "fill") == PALETTE["text"]
anim.reduce_motion = False

# ---- EmptyCard (UI-20)
ew = tk.Toplevel(root)
ec = EmptyCard(ew, head, small); ec.pack(); ec.set("No conflicts", "Your answers all agree. " * 4); update()
assert ec.itemcget("title", "text") == "No conflicts" and ec.itemcget("panel", "fill") == PALETTE["surface2"]
tb, bb = ec.bbox("title"), ec.bbox("body")
assert tb[3] <= bb[1] and bb[2] - bb[0] <= small.measure("n" * 34) + 2               # title above; body wraps
assert ec.winfo_reqwidth() > bb[2] - bb[0] and ec.winfo_reqheight() > bb[3]           # the panel holds both
ew.destroy()

# ---- Toast.wiggle: a little "no" shake of the message on screen, which then stays longer
wt = Toast(root, small, animator=anim); wt.show("No further", ms=400); update()
assert wt.wiggle() and anim.is_running(f"wiggle{id(wt)}")
anim.finish_all(); assert int(wt.place_info()["x"]) == 0
wt._fire(); anim.finish_all(); update(); assert not wt.wiggle()                 # gone: nothing to wiggle
wt.destroy()

# ---- StyledDialog (UI-24): headline, intro, body, rounded buttons; Enter = default, Escape = on_cancel
from fonts import init_fonts
from widgets import StyledDialog
init_fonts(root)
got = []
dlg = StyledDialog(root, "T", "A headline", "Some intro text", animator=anim)
# hidden until show() has centred it: first seen where it ends up (it appeared at the parent's top left, then
# jumped, reported on the keyboard shortcuts dialog)
mapped = []
dlg.win.bind("<Map>", lambda e: e.widget is dlg.win and mapped.append((dlg.win.winfo_rootx(), dlg.win.winfo_rooty())))
tk.Label(dlg.body, text="body").pack()
dlg.win.update_idletasks(); update()
assert dlg.win.state() == "withdrawn" and not mapped
dlg.button("Details", lambda: got.append("details"), side="left")
dlg.button("Cancel", dlg.close)
dlg.button("Go", lambda: got.append("go"), default=True)
dlg.show(); update()
assert mapped and abs(mapped[0][0] - dlg.win.winfo_rootx()) <= 1 and abs(mapped[0][1] - dlg.win.winfo_rooty()) <= 1
assert dlg.win.cget("bg") == PALETTE["bg"] and all(isinstance(b, RoundButton) for b in dlg.buttons.values())
xs = {k: b.winfo_rootx() for k, b in dlg.buttons.items()}
assert xs["Details"] < xs["Cancel"] < xs["Go"]                                 # default rightmost, extras far left
assert dlg.buttons["Go"].cget("bg") == PALETTE["select_bg"] != dlg.buttons["Cancel"].cget("bg")
dlg.win.event_generate("<Return>"); update(); assert got == ["go"]
cancelled = []
dlg.on_cancel = lambda: cancelled.append(1)
dlg.win.event_generate("<Escape>"); update(); assert cancelled == [1] and dlg.alive()
dlg.close(); update(); assert not dlg.alive()

# ---- WordCard's size never depends on the word (reported: the buttons moved / flashed when sorting fast)
wc_font = tkfont.Font(root=root, family="TkDefaultFont", size=40, weight="bold")
wc = WordCard(root, wc_font, small, wraplength=600); wc.pack(); wc.set("ox", "rank #1"); update()
size = (wc.winfo_reqwidth(), wc.winfo_reqheight())
assert size[0] % 2 == 0                                                                   # even: centring never wobbles
for word, sub in (("incomprehensibilities", "rank #2"), ("a", ""), ("well-to-do", "rank #3 - compound word"),
                  ("antidisestablishmentarianism " * 5, "rank #4 - revisiting a word you skipped - compound word")):
    wc.set(word, sub); update()
    assert (wc.winfo_reqwidth(), wc.winfo_reqheight()) == size, word
    cb = wc.bbox("card")
    for tag in ("word", "sub"):
        b = wc.bbox(tag)
        assert not b or (cb[0] <= b[0] and b[2] <= cb[2] and cb[1] <= b[1] and b[3] <= cb[3]), (word, tag, b, cb)
wc.set("ox", "rank #5 - " + "a very long note " * 8); update()
assert wc.itemcget("sub", "text").endswith("\u2026") and wc.bbox("sub")[2] <= wc.bbox("card")[2]   # cut short
assert wc_font.cget("size") == 40                                                         # the shared font untouched
wc.destroy()

# ---- ShapeCard (UI-41): a queue shape's curve; chosen = white with a lilac edge and a "half by" line
from widgets import ShapeCard, short_rank
from constants import queue_weight
picked = []
scw = tk.Toplevel(root)
sc = ShapeCard(scw, "exp", "Exponential", TIER_COLORS[1], on_pick=picked.append, font_=small); sc.pack()
sc.set(spread=20000, chosen=True); update()
assert sc.itemcget("face", "fill") == PALETTE["surface"] and sc.itemcget("face", "outline") == PALETTE["accent"]
assert sc.itemcget("area", "fill") == TIER_COLORS[1] and sc.itemcget("median_text", "text") == "half by #13.9k"
y20 = sc.coords("curve")[1::2]
sc.set(spread=5000); y5 = sc.coords("curve")[1::2]
assert sum(y5) > sum(y20) and len(y5) == len(y20)                    # a smaller spread: the curve drops sooner
assert abs(y5[0] - y20[0]) < 0.01                                   # (both start at the top: rank #1)
sc.set(chosen=False)
assert sc.itemcget("face", "fill") == PALETTE["surface2"] and not sc.find_withtag("median")
sc.set(spread=400000, chosen=True)                                  # median past the axis: pinned to the edge
assert sc.coords("median")[0] <= int(sc.cget("width")) and sc.itemcget("median_text", "anchor") == "ne"
update(); sc.event_generate("<Button-1>", x=5, y=5); update(); assert picked == ["exp"]
assert [short_rank(n) for n in (840, 13863, 100000, 250000, 1_200_000)] == ["840", "13.9k", "100k", "250k", "1.2M"]
assert queue_weight("gauss", 1) > queue_weight("exp", 1) and queue_weight("gauss", 3) < queue_weight("exp", 3)
scw.destroy()

# ---- DuelCards stays centred in a frame wider than the cards (reported: the conflict line widened it)
wide = tk.Toplevel(root); wide.geometry("1400x500+0+0"); wide.columnconfigure(0, weight=1)
dc = DuelCards(wide, lambda side: None, small, small); dc.grid(row=0, column=0, sticky="ew")
dc.show("panel", "thy"); update(4)
mid = dc.winfo_rootx() + dc.winfo_width() / 2
cards = (dc.left.winfo_rootx() + dc.right.winfo_rootx() + dc.right.winfo_width()) / 2
assert dc.winfo_width() > dc.left.winfo_width() * 3 and abs(cards - mid) <= 2, (cards, mid)
wide.destroy()

# ---- Tooltip (UI-33): below what it describes, stays put, rounded lilac card in the shared font
from widgets import Tooltip
area = tk.Canvas(root, width=300, height=40, bg=PALETTE["bg"]); area.pack(); update()
tip = Tooltip(area, lambda e: "left half" if e.x < 150 else "right half", font=small)
shown_states = []
real_place = Tooltip._place
Tooltip._place = lambda self, e: (shown_states.append(self.win.state()), real_place(self, e))
tip.show_at(types.SimpleNamespace(x=40, y=10)); update()
Tooltip._place = real_place
assert shown_states == ["withdrawn"] and tip.win.state() == "normal"            # placed before it is ever shown
tx, ty = tip.win.winfo_rootx(), tip.win.winfo_rooty()
assert tip.text == "left half" and ty >= area.winfo_rooty() + area.winfo_height()   # below it, never over it
tip._on_motion(types.SimpleNamespace(x=200, y=20)); update()
assert tip.text == "right half" and (tip.win.winfo_rootx(), tip.win.winfo_rooty()) == (tx, ty)   # same place
card = tip._canvas.find_withtag("card")[0]
assert tip._canvas.itemcget(card, "fill") == PALETTE["surface2"] and tip._canvas.itemcget(card, "outline") == PALETTE["border"]
assert tip._canvas.smooth_image(card) is not None and tip._canvas.itemcget("text", "font") == str(small)
tip.hide(); assert tip.text == "" and tip.win is None
side = Tooltip(area, lambda e: "beside", font=small, side="right")
side.show_at(types.SimpleNamespace(x=40, y=10)); update()
assert side.win.winfo_rootx() >= area.winfo_rootx() + area.winfo_width()            # to its right
side.hide()
area.destroy()

# ---- TierChip (UI-28): a rounded pastel tier label, sized from its font
from widgets import TierChip
chip = TierChip(root, "S", TIER_COLORS[0], small); chip.pack(); update()
poly = chip.find_withtag("all")[0]
assert chip.itemcget(poly, "fill") == TIER_COLORS[0] and chip.smooth_image(poly) is not None
w0 = chip.winfo_reqwidth(); small.configure(size=20); chip.refresh(); assert chip.winfo_reqwidth() > w0
small.configure(size=11); chip.destroy()

# un-smearing ends on the word itself (reported: small text looked bold, then snapped): one copy per pixel, and
# near the end the side copies fade into the paper under a middle copy drawn last
from widgets import smear_items
cv = tk.Canvas(root, bg="#ffffff"); cv.pack()
txt = cv.create_text(10, 10, text="a smeared meaning", font=("TkDefaultFont", 11), anchor="nw", fill="#3D3A4B")
root.update()
box = cv.bbox(txt)
for amount in (1.0, 0.3, 0.05):
    cv.delete("s"); smear_items(cv, txt, "#3D3A4B", "#ffffff", amount, ("s",))
    copies = [i for i in cv.find_withtag("s") if cv.type(i) == "text"]
    pieces = {}
    for i in copies:
        pieces.setdefault(cv.itemcget(i, "text"), []).append(i)
    assert set(pieces) == {"a", " smeared meanin", "g"}            # F-33: each line's ends apart from its middle
    for piece, items in pieces.items():
        xs = [cv.coords(i)[0] for i in items]
        assert len(xs) == len(set(xs)), piece                           # (no two on one pixel)
        if amount == 0.05:                                              # side copies gone into the paper; the
            assert all(cv.itemcget(i, "fill") == "#ffffff" for i in items[:-1])   # piece itself drawn last
    assert cv.coords(pieces["a"][-1])[0] == 10                          # (each piece last where it is in the word)
    # the user's rules: the first letter smears only inward, the last only inward, the middle both ways; so nothing
    # reaches past the word (it was cut off straight there, and cropped by a canvas only as wide as the word)
    assert min(cv.coords(i)[0] for i in pieces["a"]) == 10
    assert max(cv.bbox(i)[2] for i in pieces["g"]) <= box[2] + 1
    mid = [cv.coords(i)[0] for i in pieces[" smeared meanin"]]
    if amount == 1.0:
        assert min(mid) < max(mid[-1:]) < max(mid)                      # (both ways)
        assert not [i for i in cv.find_withtag("s") if cv.type(i) == "rectangle" and cv.coords(i)[0] < box[0]]
# a wrapped text's every line keeps its ends inward
cv.delete("all")
txt = cv.create_text(10, 10, text="one two three four five six", font=("TkDefaultFont", 11), anchor="nw", width=90)
box = cv.bbox(txt); smear_items(cv, txt, "#3D3A4B", "#ffffff", 1.0, ("s",))
texts = [cv.itemcget(i, "text") for i in cv.find_withtag("s") if cv.type(i) == "text"]
assert {"o", "t", "r", "f", "x"} <= set(texts) and "ne tw" in texts                # (each line's ends: one two / three four ..)
assert all(box[0] - 1 <= cv.bbox(i)[0] and cv.bbox(i)[2] <= box[2] + 1 for i in cv.find_withtag("s") if cv.type(i) == "text")
cv.destroy()

# UI-59: the kind of a rude word, faintly above it; the card's size never changes for it, and typing hides it
from fonts import font
wc = WordCard(root, font("word"), font("body")); wc.pack(); root.update()
wc.set("table", "frequency rank #9"); root.update(); size = (wc.winfo_reqwidth(), wc.winfo_reqheight())
assert not wc.find_withtag("kind")
wc.set("bum-fuck", "frequency rank #7", kind="sexual"); root.update()
assert wc.itemcget("kind", "text") == "sexual" and (wc.winfo_reqwidth(), wc.winfo_reqheight()) == size
kb, wb = wc.bbox("kind"), wc.bbox("word")
assert kb[3] <= wb[1] + (wb[3] - wb[1]) * 0.3 and kb[1] >= 0                      # above the letters, on the card
# asked for (a little of both): the word is drawn smaller under a kind, the kind is near the sub-line's size, and it
# stays clear of the tops of the letters (tall ones: b, f, k)
labelled = abs(wc._fit.cget("size"))
wc.set("bum-fuck", "frequency rank #7"); root.update()
assert labelled < abs(wc._fit.cget("size")) and (wc.winfo_reqwidth(), wc.winfo_reqheight()) == size
wc.set("bum-fuck", "frequency rank #7", kind="sexual"); root.update()
assert wc._kind_font.metrics("linespace") >= 0.8 * font("body").metrics("linespace")
pt = abs(wc._fit.cget("size")) * float(wc.tk.call("tk", "scaling"))
ink_top = wc._word_xy[1] + wc._fit.metrics("ascent") - 0.82 * pt
assert wc.bbox("kind")[3] <= ink_top - 0.25 * font("body").metrics("linespace"), (wc.bbox("kind"), ink_top)
assert wc.itemcget("kind", "fill") != wc.itemcget("sub", "fill")                  # paler than the sub-line
# a censored word's smear never covers the kind: not as drawn, not half un-smeared, and not while the outgoing word's
# smear slides up past it (a skip sends it up; its tall letters reach the kind's row)
def smear_over_kind():
    """How many smear items over the kind are drawn above it (and how many lie over it at all)."""
    order, kb = list(wc.find_all()), wc.bbox("kind")
    over = [i for i in wc.find_overlapping(*kb) if {"smear", "oldsmear"} & set(wc.gettags(i))]
    return sum(order.index(i) > order.index(wc.find_withtag("kind")[0]) for i in over), len(over)
wc.set("cum", "frequency rank #8", censor=True, kind="sexual"); root.update()
assert wc.find_withtag("smear") and smear_over_kind()[0] == 0
wc.smear.clear = 0.5; wc.smear.paint(); assert smear_over_kind()[0] == 0
anim, crossed = Animator(root), 0
wc.set("bollocks", "frequency rank #8", censor=True, kind="crude"); root.update()     # (tall letters: they reach up)
wc.set("jizz", "frequency rank #9", censor=True, kind="sexual")
wc.transition_from("bollocks", "frequency rank #8", 0, -wc.winfo_reqheight(), anim)
frame_at = wc._frame
anim.cancel_all()
for k in range(1, 8):                             # (frame by frame, early on, while the outgoing smear shows)
    frame_at(k * 0.05); root.update()
    above, there = smear_over_kind()
    assert above == 0, above
    crossed += there
wc.delete("old"); root.update()
assert crossed                                    # (the outgoing smear did pass over the kind: the case is tested)
wc.begin_typing(); root.update(); assert not wc.find_withtag("kind")
# UI-70: the typing caret blinks (shown on every key), and stops, shown, after a while without one
caret = lambda: wc.itemcget(wc.find_withtag("caret")[0], "state")
def wait(ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        root.update(); time.sleep(0.01)
assert caret() == "normal"
wait(WordCard.BLINK_MS + 80); assert caret() == "hidden"
wc.type_key(types.SimpleNamespace(keysym="a", char="a")); root.update(); assert caret() == "normal"   # (a key: shown)
wait(WordCard.BLINK_MS + 80); assert caret() == "hidden"
wc.BLINK_FOR_MS = 2 * WordCard.BLINK_MS
wc.type_key(types.SimpleNamespace(keysym="b", char="b")); wait(3 * WordCard.BLINK_MS)
assert caret() == "normal" and wc._blink_job is None                  # (still now, and shown)
wc.end_typing(); assert wc._blink_job is None and not wc.find_withtag("caret")
wc.destroy()

# ---- LinkButton with words (UI-75: the GitHub link): the words, then the icon; muted, the text colour on hover;
# a click runs it; it re-measures when its font is resized
from widgets import LinkButton
went = []
lf = tkfont.Font(root=root, family="TkDefaultFont", size=12)
holder = tk.Toplevel(root); holder.geometry("+0+0")               # (the root is full: somewhere it shows)
link = LinkButton(holder, "external", lambda: went.append(1), text="GitHub", font=lf, bg=PALETTE["surface"])
link.pack(); update(6)
words = link.find_withtag("all")
assert len(words) == 2 and link.itemcget(words[0], "text") == "GitHub"
assert link.itemcget(words[0], "fill") == PALETTE["muted"]
assert link.winfo_reqwidth() > lf.measure("GitHub") + link.size                # (room for both)
link.event_generate("<Motion>", warp=True, x=4, y=4); update(6)      # (the real pointer, so no stray Leave follows)
assert link.itemcget(link.find_withtag("all")[0], "fill") == PALETTE["text"]
link.event_generate("<ButtonRelease-1>"); update()
assert went == [1]
w0 = link.winfo_reqwidth()
lf.configure(size=20); link.refresh(); update()
assert link.winfo_reqwidth() > w0
holder.destroy()
root.destroy()
print("WIDGETS2 OK")
