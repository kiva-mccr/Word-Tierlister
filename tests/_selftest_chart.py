"""The tier chart (UI-13, ui_chart.py): bar sizes and shapes, labels in text colours, growth, pulse, hiding."""
import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import tkinter as tk
import tkinter.font as tkfont
from theme import PALETTE, TIER_BAR
from ui_motion import Animator
from ui_chart import (Bookshelf, ConflictCard, DistributionChart, SettledChart, compact, format_coverage,
                      format_share, leaning, soft_median)
from theme import TIER_COLORS, tier_blend

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
# Conflicts: one number on a soft card
title = tkfont.Font(root=root, family="TkDefaultFont", size=20)
cc = ConflictCard(root, title, body); cc.pack(); root.update()
assert cc.itemcget("big", "text") == "None" and cc.itemcget("small", "text") == "nicely consistent"
cc.set(3); assert cc.itemcget("big", "text") == "3" and cc.itemcget("small", "text") == "to look at"
cc.set(1234); assert cc.itemcget("big", "text") == "1,234"
cc.show(False); cc.set(2); assert cc.itemcget("big", "state") == "hidden"
# ---- the progress shelf (UI-14)
assert [format_share(*x) for x in ((0, 10), (10, 10), (97, 100), (3, 1000), (1, 640000), (999, 1000), (0, 0))] == \
    ["0%", "100%", "97%", "0.3%", "<0.001%", "99.9%", "0%"]
assert [format_coverage(x) for x in (0.5, 0.93, 0.994, 0.9997, 0.99999, 1.0)] == \
    ["50% of text", "93% of text", "99.4% of text", "99.97% of text", "99.999% of text", "100% of text"]
assert format_coverage(0.99999999) != "100% of text"                              # never 100% until it is
# the median, part way through its tier; the leaning tier; colours blended round the wheel stay bright
assert soft_median([0, 0, 10, 0, 0, 0]) == 2.0 and soft_median([0] * 6) is None
assert soft_median([0, 0, 5, 5, 0, 0]) == 2.5 and soft_median([10, 0, 0, 0, 0, 0]) == 0.0      # between C and D
assert abs(soft_median([0, 0, 3, 7, 0, 0]) - (3 - 0.5 + 2 / 7)) < 1e-9                 # 2/7 of the way into D
assert leaning([5, 1, 1, 1, 1, 1], [10, 30, 30, 30, 30, 30]) == 0 and leaning([0] * 6, [1] * 6) is None
assert [tier_blend(k) for k in range(6)] == TIER_COLORS                           # whole tiers: exactly their pastel
import colorsys
def sat(h):
    return colorsys.rgb_to_hsv(*(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)))[1]
for k in range(5):                                                                 # half-way: as bright as the two ends
    assert sat(tier_blend(k + 0.5)) >= min(sat(TIER_COLORS[k]), sat(TIER_COLORS[k + 1])) - 0.02
sh = Bookshelf(root, body); sh.pack(); root.update()
data = {"zones": [("page", 2), ("chapter", 3)], "coverage": 0.952,
        "spines": [{"zone": "page", "words": 10, "placed": 10, "tiers": [10, 0, 0, 0, 0, 0]},
                   {"zone": "page", "words": 20, "placed": 10, "tiers": [0, 0, 5, 5, 0, 0]},
                   {"zone": "chapter", "words": 40, "placed": 0, "tiers": [0] * 6},
                   {"zone": "chapter", "words": 50, "placed": 5, "tiers": [0, 5, 0, 0, 0, 0]},
                   {"zone": "chapter", "words": 60, "placed": 60, "tiers": [0, 0, 0, 0, 0, 60]}]}
sh.set(data)
def fh(i):
    ys = sh.coords(f"fill{i}")[1::2]; return max(ys) - min(ys)
def full(i):
    ys = sh.coords(f"spine{i}")[1::2]; return max(ys) - min(ys)
assert abs(fh(0) - full(0)) < 1 and abs(fh(1) - full(1) / 2) < 1 and not sh.find_withtag("fill2")   # height = share
assert sh.itemcget("fill0", "fill") == TIER_COLORS[0] and sh.itemcget("fill4", "fill") == TIER_COLORS[5]
assert sh.itemcget("fill1", "fill") == tier_blend(soft_median([0, 0, 5, 5, 0, 0]))
gap = sh.coords("spine2")[0] - sh.coords("spine1")[2]
assert gap > 2 * (sh.coords("spine1")[0] - sh.coords("spine0")[2])                # a gap between zones
assert [sh.itemcget(f"zone{i}", "text") for i in (0, 1)] == ["page", "chapter"] and sh.itemcget("tag", "text") == "95% of text"
x = lambda i: (sh.coords(f"spine{i}")[0] + sh.coords(f"spine{i}")[2]) / 2
# hover: the spine lifts and its outline darkens; its neighbours lift less; leaving puts them all back
top = lambda i: sh.coords(f"spine{i}")[1]
rest = [top(i) for i in range(5)]
edge0 = sh.itemcget("spine1", "outline")
sh.hover(1)
assert rest[1] - top(1) > rest[0] - top(0) > 0 and rest[2] - top(2) == rest[0] - top(0)       # neighbours: less
assert top(3) == rest[3] and top(4) == rest[4]
assert sh.coords("fill1")[3] < sh.coords("spine1")[3] + 1 and sh.coords("fill1")[3] == sh.coords("spine1")[3]
assert sh.itemcget("spine1", "outline") != edge0 and sh.itemcget("spine0", "outline") == edge0
sh.set(dict(data, coverage=0.9)); assert top(1) < rest[1]                         # a redraw keeps the lift
sh.hover(None)
assert [top(i) for i in range(5)] == rest and sh.itemcget("spine1", "outline") == edge0
# UI-55: marks over the spines the words on screen come from; one for two words in the same spine
sh.mark([1, 3, 3, None, 99]); assert sh._marks == [1, 3]                         # repeats / unknowns ignored
m1, m3 = sh.find_withtag("mark1"), sh.find_withtag("mark3")
assert len(sh.find_withtag("mark")) == 2 and m1 and m3
mx = sh.coords("mark1")[0] + sh.triangle_image(*sh._mark_size(), "#B19BD9").width() / 2
assert sh.coords("spine1")[0] <= mx <= sh.coords("spine1")[2] + 1                # centred over its spine
assert sh.bbox("mark1")[3] <= min(sh.coords(f"spine{i}")[1] for i in range(5)) + 1  # above every spine
y = sh.coords("mark1")[1]; sh.hover(1); assert sh.coords("mark1")[1] < y            # it rises with its spine...
assert y - sh.MARK_ROOM <= sh.coords("mark1")[1] and sh.bbox("mark1")[1] >= 0        # ...a hair: never cut off (M-3)
sh._set_lift(1, 100); assert sh.bbox("mark1")[1] >= 0; sh._set_lift(1, sh._rise())  # (however far the spine goes)
sh.hover(None); assert sh.coords("mark1")[1] == y
sh.set(dict(data, coverage=0.5)); assert len(sh.find_withtag("mark")) == 2         # kept through a redraw
sh.mark([]); assert not sh.find_withtag("mark")
# with an animator: eased, and moving on mid-way never snaps (a replaced lift does nothing more)
from ui_motion import Animator
sha = Bookshelf(root, body, animator=Animator(root)); sha.pack(); sha.set(data); root.update()
r2, r3 = sha.coords("spine2")[1], sha.coords("spine3")[1]
sha.hover(2); root.after(40, root.quit); root.mainloop()
mid = r2 - sha.coords("spine2")[1]
assert 0 < mid < sha._rise()                                                        # on its way up
sha.hover(4); now = r2 - sha.coords("spine2")[1]
assert abs(now - mid) < 0.01                                                        # no jump when the pointer moves on
sha._anim.finish_all()
assert abs(sha.coords("spine2")[1] - r2) < 0.01                                     # back down: not a neighbour
assert abs(r3 - sha.coords("spine3")[1] - round(sha._rise() * sha.NEIGHBOUR_LIFT)) < 0.01
sha.destroy()
# zone names stay whole: never cut off at the left edge, never overlapping, even for a one-spine zone
narrow = {"zones": [("page", 1), ("chapter", 1), ("book", 30)], "coverage": None,
          "spines": [{"zone": "page", "words": 3, "placed": 0, "tiers": [0] * 6},
                     {"zone": "chapter", "words": 9, "placed": 0, "tiers": [0] * 6}]
          + [{"zone": "book", "words": 50, "placed": 0, "tiers": [0] * 6}] * 30}
sh2 = Bookshelf(root, body); sh2.pack(); sh2.set(narrow); root.update()
boxes = [sh2.bbox(f"zone{i}") for i in range(3)]
assert boxes[0][0] >= 0 and all(b[2] <= int(sh2.cget("width")) for b in boxes), boxes
assert boxes[0][2] <= boxes[1][0] and boxes[1][2] <= boxes[2][0], boxes            # no overlaps
sh2.destroy()
assert sh.note(x(0)) == "page \u00b7 10 words \u00b7 100% placed \u00b7 mostly S, leans S".replace(", leans S", "")
assert sh.note(x(2)) == "chapter \u00b7 40 words \u00b7 none placed yet"
assert sh.note(x(3)).startswith("chapter \u00b7 50 words \u00b7 10% placed \u00b7 mostly A") and sh.note(-5) is None
root.destroy()
print("CHART OK")
