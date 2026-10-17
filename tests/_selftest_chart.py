"""The tier chart (UI-13, ui_chart.py): bar sizes and shapes, labels in text colours, growth, pulse, hiding."""
import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import tkinter as tk
import tkinter.font as tkfont
from theme import PALETTE, TIER_BAR
from ui_motion import Animator
from ui_chart import ConflictCard, DistributionChart, SettledChart, SwapStrip, compact

assert compact(0) == "0" and compact(1085) == "1,085" and compact(9999) == "9,999"
assert compact(12345) == "12.3K" and compact(20000) == "20K" and compact(1234567) == "1.2M" and compact(3000000) == "3M"

root = tk.Tk()
body = tkfont.Font(root=root, family="TkDefaultFont", size=12)
head = tkfont.Font(root=root, family="TkDefaultFont", size=14, weight="bold")
anim = Animator(root)
ch = DistributionChart(root, list("SABCDF"), body, head, animator=anim)
ch.pack(); root.update()

def height(i):
    ys = ch.coords(f"bar{i}")[1::2]
    return max(ys) - min(ys) if ch.itemcget(f"bar{i}", "state") != "hidden" else 0

ch.set([100, 50, 0, 25, 1, 100], animate=False); root.update()
hs = [height(i) for i in range(6)]
assert hs[0] == hs[5] == max(hs) and abs(hs[1] - hs[0] / 2) <= 1 and abs(hs[3] - hs[0] / 4) <= 1   # to scale
assert hs[2] == 0 and ch.itemcget("bar2", "state") == "hidden"                    # empty tier: no bar
assert 3 <= hs[4] < 6                                                              # one word: still a sliver
assert all(ch.itemcget(f"bar{i}", "fill") == TIER_BAR[i] for i in (0, 1, 3, 4, 5))
assert ch.itemcget("bar0", "outline") not in ("", TIER_BAR[0])                   # the pills' faint edge
xs = [ch.coords(f"letter{i}")[0] for i in range(6)]; assert xs == sorted(xs)       # S..F, left to right
w = max(ch.coords("bar0")[0::2]) - min(ch.coords("bar0")[0::2]); assert w <= 24   # thin marks
base = max(ch.coords("bar0")[1::2]); assert all(abs(max(ch.coords(f"bar{i}")[1::2]) - base) < 0.5 for i in (0, 1, 3))
assert ch.coords("axis")[1] == base                                                # one shared baseline
# labels: letters under, counts on the caps, both in text colours (never the bar colour)
assert [ch.itemcget(f"letter{i}", "text") for i in range(6)] == list("SABCDF")
assert ch.itemcget("letter0", "fill") == PALETTE["text"] and ch.itemcget("count0", "fill") == PALETTE["muted"]
assert ch.itemcget("count1", "text") == "50" and ch.itemcget("count2", "text") == ""
assert ch.coords("count1")[1] <= min(ch.coords("bar1")[1::2])                    # above its bar
assert ch.coords("letter0")[1] >= base
# growth: animated toward the new counts, finished by a key press (finish_all)
ch.set([100, 100, 0, 25, 1, 100])
assert height(1) < hs[0]                                                           # mid-growth
anim.finish_all(); assert abs(height(1) - hs[0]) <= 1
anim.reduce_motion = True
ch.set([10, 100, 0, 25, 1, 100]); assert abs(height(0) - hs[0] / 10) <= 1          # Reduce motion: jumps
anim.reduce_motion = False
# pulse: the bar brightens, then is back to its own colour
ch.pulse(1); root.after(120, root.quit); root.mainloop()
assert ch.itemcget("bar1", "fill") != TIER_BAR[1]
anim.finish_all(); assert ch.itemcget("bar1", "fill") == TIER_BAR[1]
# where a flying word lands: the top of its bar, on screen
x, y = ch.bar_top(1)
assert abs(x - (ch.winfo_rootx() + (min(ch.coords("bar1")[0::2]) + max(ch.coords("bar1")[0::2])) / 2)) <= 1
assert abs(y - (ch.winfo_rooty() + min(ch.coords("bar1")[1::2]))) <= 1
assert not ch.bind("<Motion>")                                                     # no hover note (UI-36)
# hidden (other tabs): nothing drawn, no hover note, but the same size
ch.set([1, 0, 0, 0, 0, 0], animate=False)
w1, h1 = ch.winfo_reqwidth(), ch.winfo_reqheight()
ch.show(False); assert not ch.shown and ch.itemcget("bar0", "state") == "hidden" and ch.itemcget("axis", "state") == "hidden"
assert (ch.winfo_reqwidth(), ch.winfo_reqheight()) == (w1, h1)
ch.refresh(); assert ch.itemcget("letter0", "state") == "hidden"                     # stays hidden on refresh
ch.show(True); assert ch.itemcget("letter0", "state") == "normal" and ch.itemcget("bar1", "state") == "hidden"  # (empty)
# hidden in the middle of a growth or a glow (switching tabs while it runs): it stays hidden (reported)
ch.set([5, 3, 0, 0, 0, 0]); ch.show(False); anim.finish_all()
assert all(ch.itemcget(i, "state") == "hidden" for i in ch.find_withtag("all"))
ch.show(True); ch.pulse(0); ch.show(False); anim.finish_all()
assert all(ch.itemcget(i, "state") == "hidden" for i in ch.find_withtag("all"))
ch.show(True)
# a font change re-measures
w0 = ch.winfo_reqwidth(); body.configure(size=20); ch.refresh(); assert ch.winfo_reqwidth() > w0
body.configure(size=12)

# ---- each tab's own view (UI-31)
# Refine: how settled each tier's order is, a track per tier (100%), the percentage on top, a caption
sc = SettledChart(root, list("SABCDF"), body, head, animator=anim); sc.pack(); root.update()
sc.set([0.8, 0.5, 0.0, 0.25, None, 1.0], animate=False)
def sh(i):
    ys = sc.coords(f"bar{i}")[1::2]; return max(ys) - min(ys)
track = max(sc.coords("track0")[1::2]) - min(sc.coords("track0")[1::2])
assert abs(sh(5) - track) <= 2 and abs(sh(1) - track / 2) <= 2 and sh(0) > sh(1)    # absolute shares, not peak
assert sc.itemcget("count0", "text") == "80%" and sc.itemcget("count4", "text") == "" and sc.itemcget("bar4", "state") == "hidden"
assert sc.itemcget("count2", "text") == "0%" and sc.itemcget("bar2", "state") == "hidden"   # none settled yet: no sliver
assert "settled" in sc.itemcget("caption", "text") and max(sc.bbox("caption")[0::2]) < min(sc.coords("track0")[0::2])
sc.set([0.2] * 6); assert anim.is_running(f"chart{id(sc)}"); anim.finish_all()           # grows like the tier chart
sc.show(False); assert sc.itemcget("track0", "state") == "hidden"; sc.show(True)
# Boundary: six pills, one swap count per join under it, one "swaps" caption, the current join bold
st = SwapStrip(root, list("SABCDF"), body, head); st.pack(); root.update()
st.set([3, 2, 4, 1, 0], current=2)
assert [st.itemcget(f"num{j}", "text") for j in range(5)] == ["3", "2", "4", "1", "0"]
assert st.itemcget("caption", "text") == "swaps" and len(st.find_withtag("chip")) == 6
for j in range(5):                                                               # each number under its join
    nx = st.coords(f"num{j}")[0]
    assert max(st.coords(f"chip{j}")[0::2]) < nx < min(st.coords(f"chip{j + 1}")[0::2])
assert st.itemcget("num2", "font") != st.itemcget("num1", "font") and st.itemcget("join2", "fill") == PALETTE["accent"]
st.set([3, 2, 4, 1, 0], current=None); assert st.itemcget("join2", "fill") == PALETTE["border"]
st.show(False); st.set([5, 2, 4, 1, 0]); assert st.itemcget("num0", "state") == "hidden"   # stays hidden on redraw
w0 = st.winfo_reqwidth(); body.configure(size=20); head.configure(size=22); st.refresh()
assert st.winfo_reqwidth() > w0; body.configure(size=12); head.configure(size=14)
# Conflicts: one number on a soft card
title = tkfont.Font(root=root, family="TkDefaultFont", size=20)
cc = ConflictCard(root, title, body); cc.pack(); root.update()
assert cc.itemcget("big", "text") == "None" and cc.itemcget("small", "text") == "nicely consistent"
cc.set(3); assert cc.itemcget("big", "text") == "3" and cc.itemcget("small", "text") == "to look at"
cc.set(1234); assert cc.itemcget("big", "text") == "1,234"
cc.show(False); cc.set(2); assert cc.itemcget("big", "state") == "hidden"
root.destroy()
print("CHART OK")
