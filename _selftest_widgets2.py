"""Widgets from UI-7 on: TierRow (and RoundButton's hover lift)."""
import tkinter as tk
import tkinter.font as tkfont
from theme import PALETTE, TIER_COLORS
from ui_motion import Animator
from widgets import RoundButton, TierRow

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
root.destroy()
print("WIDGETS2 OK")
