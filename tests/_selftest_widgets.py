"""RoundButton (UI-5) and WordCard (UI-6): drawing, states, clicks, config, font refresh, animation."""
import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
from theme import PALETTE
from ui_motion import Animator, lerp_color
from widgets import RoundButton, WordCard, refresh_widgets

root = tk.Tk()
clicks = []
fnt = tkfont.Font(root=root, family="TkDefaultFont", size=12)

def make(**kw):
    b = RoundButton(root, kw.pop("text", "Hello"), lambda: clicks.append(1), font=fnt, **kw)
    b.pack(padx=10, pady=10); root.update()
    return b

def press(b, x=5, y=5):
    b.event_generate("<Enter>"); b.event_generate("<ButtonPress-1>", x=x, y=y); root.update()
def release(b, x=5, y=5):
    b.event_generate("<ButtonRelease-1>", x=x, y=y); root.update()

# ---- looks and size
b = make(bg=PALETTE["better"])
assert b.winfo_reqwidth() > 40 and b.winfo_reqheight() > 20 and b.cget("text") == "Hello"
assert len(b.find_withtag("shape")) == 1 and len(b.find_withtag("label")) == 1 and not b.find_withtag("hint")
assert b.smooth_image("shape") is not None, "rounded corners are drawn as a smooth image (smooth.py)"
assert b.itemcget("shape", "fill") == PALETTE["better"]
h = make(hint="Space")
assert h.find_withtag("hint") and h.winfo_reqheight() > b.winfo_reqheight()       # the caption adds a line
assert h.itemcget("hint", "text") == "Space"

# ---- clicks: fire on release inside; not outside; not while disabled
press(b); assert not clicks                                                       # nothing on press
release(b); assert clicks == [1]                                                  # fires on release
press(b); release(b, x=-50, y=-50); assert clicks == [1]                          # released outside: cancelled
b.set_enabled(False); assert not b.enabled
press(b); release(b); assert clicks == [1]                                        # disabled ignores clicks
assert str(b.cget("cursor")) == "arrow" and b.itemcget("label", "fill") == PALETTE["disabled"]
b.set_enabled(True); assert str(b.cget("cursor")) == "hand2"
b.invoke(); assert clicks == [1, 1]
b.set_enabled(False); b.invoke(); assert clicks == [1, 1]                         # invoke respects disabled
b.set_enabled(True)

# ---- states change the colours (no animator: immediate)
plain = make(bg=PALETTE["left"])
base = plain.itemcget("shape", "fill")
plain.event_generate("<Enter>"); root.update()
hover = plain.itemcget("shape", "fill"); assert hover != base and plain.itemcget("shape", "outline") == PALETTE["accent"]
plain.event_generate("<Leave>"); root.update(); assert plain.itemcget("shape", "fill") == base
y0 = plain.coords("label")[1]
press(plain); assert plain.coords("label")[1] > y0                                # the dip
assert plain.itemcget("shape", "fill") != base
release(plain); assert plain.coords("label")[1] == y0                             # back up

# ---- config: text, hint, wraplength, colours, font; the size follows
w0 = plain.winfo_reqwidth()
plain.config(text="A considerably longer label than before")
root.update(); assert plain.winfo_reqwidth() > w0 and plain.cget("text").startswith("A considerably")
plain.config(wraplength=80); root.update(); assert plain.winfo_reqwidth() < plain.cget("wraplength") + 120
assert plain.winfo_reqheight() > h.winfo_reqheight() - 5                          # wrapped onto several lines
plain.config(hint="Key"); assert plain.cget("hint") == "Key"
plain.event_generate("<Leave>"); root.update()
plain.config(bg="#112233"); assert plain.itemcget("shape", "fill") == "#112233" and plain.cget("bg") == "#112233"
plain.config(cursor="arrow"); assert str(plain.cget("cursor")) == "arrow"         # ordinary Canvas options pass through

# ---- a resized shared Font needs refresh()
before = b.winfo_reqwidth()
fnt.configure(size=24)
refresh_widgets(root); root.update()
assert b.winfo_reqwidth() > before, (before, b.winfo_reqwidth())
frame = ttk.Frame(root); nested = RoundButton(frame, "Deep", lambda: None, font=fnt); nested.pack(); frame.pack()
w1 = nested.winfo_reqwidth(); fnt.configure(size=10); refresh_widgets(root); assert nested.winfo_reqwidth() < w1   # finds nested ones

# ---- stretching: the shape fills the space the layout gives it
big = RoundButton(root, "Wide", lambda: None, font=fnt); big.pack(fill="x", padx=10); root.update()
x1, y1, x2, y2 = big.bbox("shape")
assert x2 - x1 >= big.winfo_width() - 4

# ---- animation: the tint fades over several frames, ends exactly on target; reduce motion jumps
now = [0.0]
an = Animator(root, clock=lambda: now[0])
fade = RoundButton(root, "Fade", lambda: None, font=fnt, bg=PALETTE["left"], animator=an); fade.pack(); root.update()
start = fade.itemcget("shape", "fill")
fade.event_generate("<Enter>"); root.update()
assert an.busy
now[0] += 0.05; root.after(40, root.quit); root.mainloop()
mid = fade.itemcget("shape", "fill"); assert mid != start
an.finish_all(); end = fade.itemcget("shape", "fill")
assert end == lerp_color(PALETTE["left"], "#FFFFFF", 0.45).lower() or end.upper() == lerp_color(PALETTE["left"], "#FFFFFF", 0.45).upper()
an.reduce_motion = True
fade.event_generate("<Leave>"); root.update(); assert not an.busy and fade.itemcget("shape", "fill").upper() == PALETTE["left"].upper()
# flash (keyboard feedback): pressed look, then restored
fl = make(bg=PALETTE["right"]); yb = fl.coords("label")[1]
fl.flash(ms=30); assert fl.coords("label")[1] > yb
root.after(80, root.quit); root.mainloop(); assert fl.coords("label")[1] == yb

# ---- WordCard (UI-6)
wf = tkfont.Font(root=root, family="TkDefaultFont", size=40, weight="bold")
sf = tkfont.Font(root=root, family="TkDefaultFont", size=12)
card = WordCard(root, wf, sf); card.pack(); root.update()
assert card.word == "" and card.sub == ""
card.set("cat", "frequency rank #1,234"); root.update()
assert card.word == "cat" and card.sub.startswith("frequency")
assert card.itemcget("word", "text") == "cat" and card.itemcget("sub", "text") == card.sub
assert len(card.find_withtag("card")) == 1 and len(card.find_withtag("shadow")) == 1
assert card.smooth_image("card") is not None                                         # rounded, smooth
sx2, sy2 = card.bbox("shadow")[2:]; cx2, cy2 = card.bbox("card")[2:]
assert sx2 > cx2 and sy2 > cy2, "the shadow peeks out below and to the right"
size = (card.winfo_reqwidth(), card.winfo_reqheight())
card.set("be", ""); root.update()
assert not card.find_withtag("sub")                                                 # no sub-line when empty
card.set("pneumonoultramicroscopicsilicovolcanoconiosis", "x"); root.update()
assert (card.winfo_reqwidth(), card.winfo_reqheight()) == size, "the card's size never depends on the word"
cb, wb = card.bbox("card"), card.bbox("word")
assert cb[0] < wb[0] and wb[2] < cb[2] and cb[1] < wb[1] and wb[3] < cb[3]          # a long word shrinks inside it
assert card.cget("font").cget("size") == 40                                          # (the shared font is untouched)
card.config(wraplength=200); root.update()
assert card.winfo_reqwidth() < size[0] and card.cget("wraplength") == 200          # less room: a narrower card
wb = card.bbox("word"); assert wb[2] - wb[0] <= 205
assert card.winfo_reqheight() == size[1] > wf.metrics("linespace") + sf.metrics("linespace"), size   # (word, sub-line)
assert card.cget("font") is wf
h_before, p_before = card.winfo_reqheight(), card.padx
wf.configure(size=20); refresh_widgets(root); root.update()                          # nested search finds cards too
assert card.padx < p_before and card.winfo_reqheight() < h_before                    # padding follows the font
wf.configure(size=40)
root.destroy()
print("WIDGETS OK")
