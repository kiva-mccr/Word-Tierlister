"""The tier chart (UI-13, ui_chart.py): bar sizes and shapes, labels in text colours, growth, pulse, hover."""
import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import types
import tkinter as tk
import tkinter.font as tkfont
from theme import PALETTE, TIER_BAR
from ui_motion import Animator
from ui_chart import DistributionChart, compact

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
# hover note per bar
ev = types.SimpleNamespace(x=int((min(ch.coords("bar3")[0::2]) + max(ch.coords("bar3")[0::2])) / 2), y=40)
assert ch.tier_at(ev.x) == 3 and ch.tier_at(-5) is None
assert ch._tip_text(ev) == "Tier C: 25 words (11% of placed)"                   # 25 of 236
ch.tooltip.show_at(ev); root.update()
assert ch.tooltip.text.startswith("Tier C") and ch.tooltip.win.winfo_ismapped()
ch.tooltip.hide(); assert ch.tooltip.text == ""
ch.set([1, 0, 0, 0, 0, 0], animate=False)
assert ch._tip_text(types.SimpleNamespace(x=ev.x - 3 * (xs[1] - xs[0]), y=40)).endswith("1 word (100% of placed)")
# hidden (other tabs): nothing drawn, no hover note, but the same size
w1, h1 = ch.winfo_reqwidth(), ch.winfo_reqheight()
ch.show(False); assert not ch.shown and ch.itemcget("bar0", "state") == "hidden" and ch.itemcget("axis", "state") == "hidden"
assert ch._tip_text(ev) is None and (ch.winfo_reqwidth(), ch.winfo_reqheight()) == (w1, h1)
ch.refresh(); assert ch.itemcget("letter0", "state") == "hidden"                     # stays hidden on refresh
ch.show(True); assert ch.itemcget("letter0", "state") == "normal" and ch.itemcget("bar1", "state") == "hidden"  # (empty)
# a font change re-measures
w0 = ch.winfo_reqwidth(); body.configure(size=20); ch.refresh(); assert ch.winfo_reqwidth() > w0
root.destroy()
print("CHART OK")
