"""The tier chart (UI-13): six small bars, S..F, showing how many words sit in each tier; and each other tab's
own view in the same spot (UI-31): SettledChart (Refine), ConflictCard (Conflicts); and
the progress shelf under the status line (UI-14): Bookshelf.

Built to the dataviz rules where they apply: bars at most 24 px wide with a rounded data end and a square
baseline on one hairline axis; the tier letter under each bar and its count on the cap are in text colours
(never the bar colour); bars grow with ease-out when a count changes. No hover note (UI-36: not needed). The bars are
the tier pastels with the pills' faint edge (theme.TIER_BAR): identity comes from the letter and the fixed
S..F order, not from colour, so the colours can stay pastel (the user's choice over a colour-blind-tuned set).
"""
import math

from constants import SHELF_SPINES, SHELF_ZIPF
from constants import TIERS as TIERS_LETTERS
from theme import PALETTE, TIER_BAR, TIER_COLORS, tier_blend
from ui_motion import lerp_color
from smooth import SmoothCanvas

GROW_MS = 220
PULSE_MS = 240


def compact(n):
    """1,234 -> '1,234'; 12,345 -> '12.3K'; 1,234,567 -> '1.2M' (the cap labels stay short)."""
    if n < 10_000:
        return f"{n:,}"
    if n < 1_000_000:
        return f"{n / 1000:.1f}K".replace(".0K", "K")
    return f"{n / 1_000_000:.1f}M".replace(".0M", "M")


class DistributionChart(SmoothCanvas):
    """Six bars, one per tier, with the letter under each and the count on top.

        chart = DistributionChart(parent, ["S", "A", "B", "C", "D", "F"], font("body"), font("head"),
                                  animator=app.anim)
        chart.set([1085, 1085, 1084, 1084, 1084, 1084])     # bars grow to the new counts
        chart.pulse(2)                                       # B's bar glows briefly (a word just landed)
        x, y = chart.bar_top(2)                              # where B's bar ends, in screen pixels

    Heights are relative to the biggest tier. A tier with any words shows at least a sliver.
    """

    def __init__(self, parent, tiers, font=None, letter_font=None, animator=None, canvas_bg=None, colors=TIER_BAR):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"])
        self.tiers, self.colors = list(tiers), list(colors)
        self._font, self._lfont, self._anim = font, letter_font or font, animator
        self.counts = [0] * len(self.tiers)
        self._shown = [0.0] * len(self.tiers)        # drawn heights as a share of the tallest (animated)
        self._goal = [0.0] * len(self.tiers)         # ...and where they are heading
        self._glow = [0.0] * len(self.tiers)
        self._visible = True
        self._draw()

    # ---- geometry --------------------------------------------------------------------------------
    def _metrics(self):
        line = self._font.metrics("linespace") if self._font else 16
        lline = self._lfont.metrics("linespace") if self._lfont else 16
        bar_w = min(24, max(10, int(line * 1.0)))
        slot = max(bar_w + 18, int(line * 2.8))
        plot_h = int(line * 2.6)
        top = line + 4                                   # room for the count above the tallest bar
        return bar_w, slot, plot_h, top, lline

    def _x(self, i):
        bar_w, slot, _ph, _top, _ll = self._metrics()
        return 4 + i * slot + slot / 2

    def _draw(self):
        self.delete("all")
        bar_w, slot, plot_h, top, lline = self._metrics()
        n = len(self.tiers)
        width = 8 + n * slot
        base = top + plot_h
        super().configure(width=width, height=base + 4 + lline + 2)
        self.create_line(4, base, width - 4, base, fill=PALETTE["border"], tags="axis")
        for i, name in enumerate(self.tiers):
            x = self._x(i)
            self.round_rect(0, 0, 0, 0, 0, tags=("bar", f"bar{i}"))
            self.create_text(x, 0, text="", font=self._font, fill=PALETTE["muted"], anchor="s",
                             tags=("count", f"count{i}"))
            self.create_text(x, base + 3, text=name, font=self._lfont, fill=PALETTE["text"], anchor="n",
                             tags=("letter", f"letter{i}"))
        self._base = base
        self._paint()

    def _paint(self):
        bar_w, _slot, plot_h, _top, _ll = self._metrics()
        base = self._base
        for i in range(len(self.tiers)):
            x = self._x(i)
            h = self._shown[i] * plot_h
            if self.counts[i] > 0:
                h = max(h, 3)
            fill = lerp_color(self.colors[i], "#FFFFFF", 0.45 * self._glow[i])
            if h >= 1:
                r = min(4, h / 2, bar_w / 2)
                # rounded data end, square baseline: corners doubled at the bottom keep it square
                x1, x2, y1 = x - bar_w / 2, x + bar_w / 2, base - h
                self.round_rect_coords(f"bar{i}", x1, y1, x2, base, radii=(r, r, 0, 0))
                # the same faint same-hue edge as the tier pills (RoundButton), so pale bars still read
                self.itemconfigure(f"bar{i}", fill=fill, outline=lerp_color(self.colors[i], PALETTE["text"], 0.18),
                                   width=1, state="normal")
            else:
                self.itemconfigure(f"bar{i}", state="hidden")
            self.coords(f"count{i}", x, base - h - 2)
            self.itemconfigure(f"count{i}", text=compact(self.counts[i]) if self.counts[i] else "")
        self.tag_raise("count")
        if not self._visible:                 # hidden (another tab): a growth or glow still running stays unseen
            self.itemconfigure("all", state="hidden")

    # ---- data --------------------------------------------------------------------------------------
    def set(self, counts, animate=True):
        """Show these per-tier counts; changed bars grow or shrink with ease-out (GROW_MS)."""
        counts = [int(c or 0) for c in counts]
        peak = max(counts) or 1
        goal = self._goal = [c / peak for c in counts]
        start = list(self._shown)
        self.counts = counts
        self._ease(start, goal, animate)

    def _ease(self, start, goal, animate):
        """The bars from `start` to `goal` (their shares of the tallest), easing over GROW_MS or at once."""
        if not animate or self._anim is None or start == goal:
            self._shown = goal
            self._paint()
            return

        def frame(p):
            self._shown = [a + (b - a) * p for a, b in zip(start, goal)]
            self._paint()
        self._anim.run(f"chart{id(self)}", GROW_MS, frame)

    def pulse(self, tier):
        """A soft glow on one bar (UI-17: a placed word just arrived in it)."""
        def frame(p):
            self._glow[tier] = 1.0 - abs(2 * p - 1)      # up and back down
            self._paint()

        def done():
            self._glow[tier] = 0.0
            self._paint()
        if self._anim is None or self._anim.reduce_motion:
            return
        self._anim.run(f"pulse{id(self)}{tier}", PULSE_MS, frame, done, ease=lambda t: t)

    def bar_top(self, tier):
        """Screen position of the top centre of a tier's bar (where a flying word lands), at the height it is
        growing to: measured mid-growth, the bar rose into the word that had landed on it."""
        _bw, _slot, plot_h, _top, _ll = self._metrics()
        h = max(self._goal[tier] * plot_h, 3 if self.counts[tier] else 0)
        return self.winfo_rootx() + int(self._x(tier)), self.winfo_rooty() + int(self._base - h)

    def bars_top(self):
        """Screen y of the top of the tallest bar (a flying word passes above it)."""
        _bw, _slot, plot_h, _top, _ll = self._metrics()
        h = max([max(a, b) * plot_h for a, b in zip(self._shown, self._goal)] + [3 if any(self.counts) else 0])
        return self.winfo_rooty() + int(self._base - h)

    @property
    def shown(self):
        return self._visible

    def show(self, on):
        """Show or hide the bars while keeping the chart's space (so the layout does not move)."""
        self._visible = bool(on)
        self.itemconfigure("all", state="normal" if on else "hidden")
        if on:
            self._paint()                     # (empty tiers keep their bar hidden)

    def refresh(self):
        self._draw()
        if not self._visible:
            self.itemconfigure("all", state="hidden")


class SettledChart(DistributionChart):
    """Refine within tier (UI-31): how settled each tier's order is. Six bars like the tier chart, each the
    share of that tier's words with enough duels, over a faint full-height track (so 100% is visible), the
    percentage on the cap, and a muted "order settled" caption to the left.

        chart = SettledChart(parent, TIERS, font("body"), font("head"), animator=app.anim)
        chart.set([0.79, 0.68, 0.44, 0.28, 0.09, None])     # None: an empty tier (no bar, no number)
    """

    CAPTION = "order\nsettled"
    shares = ()

    def _caption_w(self):
        return max(self._font.measure(t) for t in self.CAPTION.split("\n")) + 14 if self._font else 60

    def _x(self, i):
        return self._caption_w() + super()._x(i)

    def _draw(self):
        super()._draw()
        bar_w, _slot, plot_h, top, _ll = self._metrics()
        super().configure(width=int(self.cget("width")) + self._caption_w())
        self.coords("axis", self._caption_w() + 4, self._base, int(self.cget("width")) - 4, self._base)
        for i in range(len(self.tiers)):
            x = self._x(i)
            self.round_rect(x - bar_w / 2, top, x + bar_w / 2, self._base, 4, fill=PALETTE["surface2"],
                            tags=("track", f"track{i}"))
        self.tag_lower("track")
        self.create_text(self._caption_w() - 8, top + plot_h / 2, text=self.CAPTION, font=self._font,
                         fill=PALETTE["muted"], anchor="e", justify="right", tags="caption")
        self._paint()

    def _paint(self):
        super()._paint()
        _bw, _slot, _ph, top, _ll = self._metrics()
        for i in range(len(self.tiers)):
            share = self.shares[i] if i < len(self.shares) else None
            self.coords(f"count{i}", self._x(i), top - 2)            # the percentage sits over the track
            self.itemconfigure(f"count{i}", text="" if share is None else f"{round(share * 100)}%")

    def set(self, shares, animate=True):
        """Show these per-tier shares (0..1, or None for an empty tier); bars grow with ease-out."""
        self.shares = list(shares)
        goal = [s or 0.0 for s in self.shares]
        start = list(self._shown)
        self.counts = [1 if s else 0 for s in self.shares]           # a sliver for any settled word
        self._ease(start, goal, animate)


class ConflictCard(SmoothCanvas):
    """Resolve conflicts (UI-31): not a chart, one number on a soft card, "3 / to look at", or "None / nicely
    consistent" once the last one is resolved."""

    def __init__(self, parent, title_font, body_font, canvas_bg=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"])
        self._tf, self._bf = title_font, body_font
        self.count = 0
        self.shown = True
        self._draw()

    def _draw(self):
        self.delete("all")
        tf, bf = self._tf, self._bf
        big = f"{self.count:,}" if self.count else "None"
        small = "to look at" if self.count else "nicely consistent"
        pad = bf.metrics("linespace") // 2 + 2
        w = max(tf.measure(big), bf.measure(small), bf.measure("nicely consistent")) + 4 * pad
        h = tf.metrics("linespace") + bf.metrics("linespace") + 2 * pad
        super().configure(width=w + 2, height=h + 2)
        self.round_rect(1, 1, w, h, min(14, h // 3), fill=PALETTE["surface2"], outline=PALETTE["border"], tags="panel")
        self.create_text(1 + w / 2, 1 + pad, text=big, font=tf, fill=PALETTE["text"], anchor="n", tags="big")
        self.create_text(1 + w / 2, 1 + pad + tf.metrics("linespace"), text=small, font=bf, fill=PALETTE["muted"],
                         anchor="n", tags="small")

    def set(self, count):
        if count != self.count:
            self.count = count
            self._draw()
            self.show(self.shown)

    def show(self, on):
        """Show or hide it while keeping its space (the views of all tabs share one spot)."""
        self.shown = bool(on)
        self.itemconfigure("all", state="normal" if on else "hidden")

    def refresh(self):
        self._draw()
        self.show(self.shown)


def format_share(placed, total):
    """A segment's share placed, short: '100%' only when complete, '97%', '0.3%', '0%' when none."""
    if not total or not placed:
        return "0%"
    if placed >= total:
        return "100%"
    pct = 100.0 * placed / total
    for d in (0, 1, 2, 3):
        text = f"{pct:.{d}f}"
        if 0 < float(text) < 100:                        # never rounds to a flat 0% or 100%
            return f"{text}%"
    return "<0.001%"


def format_coverage(frac):
    """The coverage text (UI-14): the share of running text made of placed words, "95% of text", with as many
    decimals as it takes to keep moving near 100% (93%, 99.4%, 99.97%), rounded down, so it never shows 100%
    before everything is covered."""
    if frac >= 1:
        return "100% of text"
    pct = 100.0 * frac
    left = 100.0 - pct
    d = 0 if left >= 1 else 1 if left >= 0.1 else 2 if left >= 0.01 else 3
    shown = math.floor(round(pct * 10 ** d, 6)) / 10 ** d     # (round first: 99.4 * 10 is 993.9999...)
    return f"{min(shown, 100 - 10 ** -d):.{d}f}% of text"


def soft_median(tiers):
    """Where the middle placed word falls, as a position on the tier scale 0 (S) .. 5 (F), part way through its
    tier: if half the words are in S..B and the middle word is 30% of the way through the C words, 2.8 (the
    tiers are treated as spans around 0, 1, 2...). None when nothing is placed."""
    total = sum(tiers)
    if not total:
        return None
    half, acc = total / 2, 0
    for k, n in enumerate(tiers):
        if n and acc + n >= half:
            return max(0.0, min(len(tiers) - 1.0, k - 0.5 + (half - acc) / n))
        acc += n
    return len(tiers) - 1.0


def leaning(tiers, overall):
    """The tier most over-represented in `tiers` compared with the whole list (`overall`, per-tier counts), or
    None when nothing is placed."""
    total, whole = sum(tiers), sum(overall)
    if not total or not whole:
        return None
    return max((k for k in range(len(tiers)) if overall[k]), key=lambda k: (tiers[k] / total) / (overall[k] / whole))


def _mark_lilac():
    """The lilac of selections, a little deeper (read when drawing: the look can change, UI-62)."""
    return lerp_color(PALETTE["accent"], PALETTE["text"], 0.3)


def mark_color(tier):
    """A shelf mark's colour: its word's tier pastel, deepened so a small triangle still shows on the page
    (M-4); the lilac for a word with no tier."""
    return _mark_lilac() if tier is None else lerp_color(TIER_COLORS[tier], PALETTE["text"], 0.3)


class Bookshelf(SmoothCanvas):
    """The progress shelf (UI-14): a shelf of book spines on a log scale of commonness, split into zones named
    for how often you would meet such a word (page, chapter, book, shelf, library), with "95% of text" after it.

        shelf = Bookshelf(parent, font("body"))
        shelf.set(store.shelf())         # {"zones": [(name, n spines)], "spines": [...], "coverage": 0.95}
        shelf.note(x)                     # the hover note for the spine under x

    A spine's height is the share of its words placed. Its colour is the median tier of those words, part way
    to the next tier and blended round the colour wheel (theme.tier_blend), so it stays as bright as the pastels.
    Spines are equal steps of commonness (each a fixed factor rarer than the last), not equal word counts: one
    near the start holds a few words, one near the end thousands; the hover note says how many. Every spine is the
    same width (UI-79, asked for): a short list, with fewer spines, has a shorter shelf.
    Hovering a spine darkens its outline and lifts it a little off the shelf, its two neighbours less
    (hover(i); eased over LIFT_MS, at once with Reduce motion).
    mark([i, j]) puts a little triangle over those spines, pointing down at them (UI-55: where the words
    on screen in a duel come from; one triangle when both are in the same spine); mark([]) clears them.
    """
    GAP = 10                                   # space between zones
    LIFT_MS = 140
    NEIGHBOUR_LIFT = 0.45                      # the neighbours rise this share of the hovered spine's lift
    MARK_LIFT, MARK_ROOM = 0.25, 2             # a mark rises only a hair with its spine, within the room above it

    def __init__(self, parent, font=None, canvas_bg=None, animator=None):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"])
        self._font, self._anim = font, animator
        self.data = {"zones": [], "spines": [], "coverage": None}
        self._x = []                           # left edge and width of each spine, for note()
        self._edges = []                       # each spine's (outline, fill outline) colours at rest
        self._hover = None                     # the spine under the pointer
        self._lift = {}                        # spine -> pixels it is raised right now
        self._gen = 0                          # bumped by every hover change
        self._marks = []                       # spines with a triangle over them
        self._mark_colors = {}                 # spine -> its triangle's colour(s): two for a split triangle
        self.bind("<Motion>", lambda e: self.hover(self.spine_at(e.x)), add="+")
        self.bind("<Leave>", lambda e: self.hover(None), add="+")
        self._draw()

    def _metrics(self):
        """(line, spine width, tallest spine): every spine is one width however many there are (asked for), the
        width that puts a full list's spines (about SHELF_SPINES, a log scale) in 30 lines; a short list's shelf is
        shorter."""
        line = self._font.metrics("linespace") if self._font else 16
        return line, (line * 30 - self.GAP * len(SHELF_ZIPF)) / SHELF_SPINES, 2 * line

    def _rise(self):
        """How far the hovered spine lifts, in pixels (there is that much room above the tallest spine)."""
        return max(3, int(self._metrics()[0] * 0.35))

    def _mark_size(self):
        """(width, height) of a mark's triangle: about a spine wide, never smaller than 7 x 5."""
        h = max(5, int(self._metrics()[0] * 0.38))
        return h + h // 2 + 1, h

    def _draw(self):
        self.delete("all")
        line, sw, hmax = self._metrics()
        zones, spines = self.data["zones"], self.data["spines"]
        top = 1 + self.MARK_ROOM + self._mark_size()[1] + 2 + self._rise()   # room for a mark, a spine lifting
        self._edges = []
        base = top + hmax
        self._x = []
        x, i = 1.0, 0
        labels = []
        edge = lerp_color(PALETTE["border"], PALETTE["text"], 0.25)
        for zi, (name, count) in enumerate(zones):
            x0 = x
            for k in range(count):
                sp = spines[i]
                full = hmax - (k % 3) * 2                  # slightly uneven tops, like real books
                x1, x2 = x, x + sw - 1.5
                self.create_rectangle(x1, base - full, x2, base, fill=PALETTE["bg"], outline=PALETTE["border"],
                                      tags=("spine", f"spine{i}"))
                share = sp["placed"] / sp["words"] if sp["words"] else 0.0
                h = full * share
                col = None
                if sp["placed"] and h >= 1:
                    col = tier_blend(soft_median(sp["tiers"]))
                    self.create_rectangle(x1, base - h, x2, base, fill=col,
                                          outline=lerp_color(col, PALETTE["text"], 0.18), tags=("fill", f"fill{i}"))
                self._edges.append(col)
                self._x.append((x, sw, zi))
                x += sw
                i += 1
            self.create_line(x0 - 1, base + 1, x - 1, base + 1, fill=edge, width=2, tags="board")
            labels.append((name, x0, x, zi))
            x += self.GAP
        right = x - self.GAP
        # zone names under their zones, kept whole: inside the shelf, and pushed along rather than overlapping
        # when a zone is narrower than its name
        last_end = 0.0
        for name, x0, x1, zi in labels:
            tw = self._font.measure(name) if self._font else 8 * len(name)
            left = max((x0 + x1) / 2 - tw / 2, 0.0, last_end + line / 2)
            left = min(left, max(0.0, right - tw))
            self.create_text(left, base + 4, text=name, font=self._font, fill=PALETTE["muted"], anchor="nw",
                             tags=("zone", f"zone{zi}"))
            last_end = left + tw
        if self.data["coverage"] is not None:      # quiet text at the end, like the zone names
            self.create_text(right + line // 2, top + hmax / 2, text=format_coverage(self.data["coverage"]),
                             font=self._font, fill=PALETTE["muted"], anchor="w", tags="tag")
            right += line // 2 + (self._font.measure("99.999% of text") if self._font else 100)
        super().configure(width=max(right, line * 4) + 2, height=base + 4 + line + 2)
        self._top = top
        self._marks = [i for i in self._marks if i < len(self._x)]
        self._draw_marks(lifted=False)
        # a redraw (a word placed) keeps the hovered spine and its neighbours where they are
        lifted, self._lift = self._lift, {}
        for j, v in lifted.items():
            if j < len(self._x):
                self._set_lift(j, v)
        if self._hover is not None and self._hover >= len(self._x):
            self._hover = None
        self._outline(self._hover, True)

    def _draw_marks(self, lifted=True):
        """The marks, over the tallest a spine can be, pointing down at theirs. Only these are redrawn when the
        duel changes (redrawing the whole shelf for them cost ~14 ms a duel). lifted: a spine lifted right now
        (hover) has its mark raised the same hair as _set_lift gives it."""
        self.delete("mark")
        mw, mh = self._mark_size()
        for i in self._marks:
            x0, w, _zi = self._x[i]
            cols = self._mark_colors.get(i, (_mark_lilac(),))
            up = min(self.MARK_ROOM, self._lift.get(i, 0.0) * self.MARK_LIFT) if lifted else 0
            self.create_image(int(round(x0 + (w - 1.5) / 2 - mw / 2)), self._top - self._rise() - mh - 1 - up,
                              image=self.triangle_image(mw, mh, *cols[:2]), anchor="nw", tags=("mark", f"mark{i}"))

    def _set_lift(self, i, v):
        was = self._lift.get(i, 0.0)
        dy = v - was
        if dy:
            self.move(f"spine{i}", 0, -dy)
            self.move(f"fill{i}", 0, -dy)
            # a mark moves the slightest bit with its spine: rising all the way, it went past the top and was cut off
            mark = lambda lift: min(self.MARK_ROOM, lift * self.MARK_LIFT)
            self.move(f"mark{i}", 0, mark(was) - mark(v))
        self._lift[i] = v

    def _outline(self, i, dark):
        if i is None or i >= len(self._edges):
            return
        col = self._edges[i]
        self.itemconfigure(f"spine{i}", outline=lerp_color(PALETTE["border"], PALETTE["text"], 0.6) if dark
                           else PALETTE["border"])
        if col is not None:
            self.itemconfigure(f"fill{i}", outline=lerp_color(col, PALETTE["text"], 0.55 if dark else 0.18))

    def hover(self, i):
        """Lift spine i (None: the pointer left) and its neighbours, and darken its outline."""
        if i == self._hover:
            return
        self._outline(self._hover, False)
        self._hover = i
        self._outline(i, True)
        targets = {}
        if i is not None:
            rise = self._rise()
            for j in (i - 1, i + 1):
                if 0 <= j < len(self._x):
                    targets[j] = round(rise * self.NEIGHBOUR_LIFT)
            targets[i] = rise
        start = dict(self._lift)
        moving = set(start) | set(targets)
        self._gen = gen = self._gen + 1     # a replaced lift (the pointer moved on) does nothing more:
                                                           # finishing it would snap the spines to its end first

        def frame(p):
            if gen == self._gen:
                for j in moving:
                    a = start.get(j, 0.0)
                    self._set_lift(j, a + (targets.get(j, 0) - a) * p)

        def done():
            if gen == self._gen:
                for j in [j for j, v in self._lift.items() if not v]:
                    del self._lift[j]
        if self._anim is None:
            frame(1.0)
            done()
        else:
            self._anim.run(f"shelf{id(self)}", self.LIFT_MS, frame, done)

    def set(self, data):
        if data != self.data:
            self.data = data
            self._draw()

    def mark(self, spines, tiers=None):
        """Triangles over these spines (indices; None and repeats are ignored), none for []. `tiers` (the same
        length: each word's tier, or None) colours each one like its word's tier; two words of different tiers
        in one spine share a triangle split down the middle, the first word's colour on the left."""
        tiers = list(tiers) if tiers is not None else [None] * len(spines)
        colors = {}
        for i, t in zip(spines, tiers):
            if i is not None and 0 <= i < len(self.data["spines"]):
                c = mark_color(t)
                if c not in colors.setdefault(i, []):
                    colors[i].append(c)
        colors = {i: tuple(c) for i, c in colors.items()}
        if colors != self._mark_colors or sorted(colors) != self._marks:
            self._marks, self._mark_colors = sorted(colors), colors
            self._draw_marks()

    def spine_at(self, x):
        for i, (x0, w, _zi) in enumerate(self._x):
            if x0 <= x < x0 + w:
                return i
        return None

    def note(self, x):
        """'book · 412 words · 61% placed · mostly C, leans A' for the spine under x, or None."""
        i = self.spine_at(x)
        if i is None:
            return None
        sp = self.data["spines"][i]
        head = f"{sp['zone']} \u00b7 {sp['words']:,} word{'s' if sp['words'] != 1 else ''}"
        if not sp["placed"]:
            return f"{head} \u00b7 none placed yet"
        overall = [sum(s_["tiers"][k] for s_ in self.data["spines"]) for k in range(len(TIERS_LETTERS))]
        mostly = TIERS_LETTERS[min(len(TIERS_LETTERS) - 1, round(soft_median(sp["tiers"])))]
        lean = leaning(sp["tiers"], overall)
        tail = f"mostly {mostly}" + (f", leans {TIERS_LETTERS[lean]}" if lean is not None and TIERS_LETTERS[lean] != mostly else "")
        return f"{head} \u00b7 {format_share(sp['placed'], sp['words'])} placed \u00b7 {tail}"

    def refresh(self):
        self._draw()
