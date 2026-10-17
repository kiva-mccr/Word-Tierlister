"""Widgets from UI-7 on: TierRow (and RoundButton's hover lift), DuelCards (and flat buttons), AnchorLadder,
SegmentedControl, DropMenu and HeaderMenus (UI-10)."""
import tkinter as tk
import tkinter.font as tkfont
from theme import PALETTE, TIER_COLORS
from ui_motion import Animator
from widgets import AnchorLadder, DropMenu, DuelCards, HeaderMenus, RoundButton, SegmentedControl, TierRow

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
row.press(2); update(1)
assert picked == [2] and row.buttons[2].coords("label")[1] == ys + 2           # action ran, pill dipped
root.after(150, root.quit); root.mainloop()
assert row.buttons[2].coords("label")[1] == ys                                 # ...and came back up
row.press(9); assert picked == [2]                                             # out of range: nothing
row.buttons[0].set_enabled(False); row.press(0); assert picked == [2]          # disabled: nothing
row.set_enabled(True); row.press(0); assert picked == [2, 0]
# a click on a pill picks too
p = row.buttons[5]
p.event_generate("<Enter>"); p.event_generate("<ButtonPress-1>", x=6, y=8); update()
p.event_generate("<ButtonRelease-1>", x=6, y=8); update()
assert picked == [2, 0, 5]
# pill shape: radius clamps to half the height (a true pill)
assert str(p.itemcget("shape", "smooth")) in ("1", "true")

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
yl = duel.left.coords("label")[1]
for side in DuelCards.SIDES:
    duel.press(side)
assert answers == ["left", "right", "tie", "skip"]
update(1); assert duel.left.coords("label")[1] == yl + 2                     # the pressed dip
duel.press("nonsense"); assert len(answers) == 4
duel.set_enabled(False); duel.press("left"); assert len(answers) == 4        # disabled: nothing
duel.show("a", "b"); duel.press("right"); assert answers[-1] == "right"      # show() re-enables
b = duel.tie; b.event_generate("<Enter>"); b.event_generate("<ButtonPress-1>", x=6, y=6); update()
b.event_generate("<ButtonRelease-1>", x=6, y=6); update(); assert answers[-1] == "tie"

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

# ---- SegmentedControl (UI-10)
changes = []
opts = [("place", "Place new words"), ("refine", "Refine within tier"), ("boundary", "Boundary check")]
seg = SegmentedControl(root, opts, changes.append, small, animator=anim); seg.pack(); update()
assert seg.get() == "place" and len(seg.find_withtag("label")) == 3
seg_w = (seg.winfo_reqwidth() - 2 - 8) / 3
def seg_click(i):
    x = int(5 + seg_w * i + seg_w / 2)
    seg.event_generate("<Motion>", x=x, y=10); seg.event_generate("<ButtonRelease-1>", x=x, y=10); update()
assert seg.itemcget("label_place", "fill") == PALETTE["text"] and seg.itemcget("label_refine", "fill") == PALETTE["muted"]
t0 = seg.coords("thumb")[0]
seg_click(2)
assert changes == ["boundary"] and seg.get() == "boundary"
anim.finish_all(); assert seg.coords("thumb")[0] > t0 + seg_w * 1.5           # the thumb slid two segments
seg_click(2); assert changes == ["boundary"]                                     # clicking the chosen one: nothing
seg.set("refine"); anim.finish_all(); assert seg.get() == "refine" and changes == ["boundary"]   # set() is silent
seg.set("nonsense"); assert seg.get() == "refine"
seg.event_generate("<Leave>"); update()
assert seg.itemcget("label_refine", "fill") == PALETTE["text"] and seg.itemcget("label_place", "fill") == PALETTE["muted"]

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
root.destroy()
print("WIDGETS2 OK")
