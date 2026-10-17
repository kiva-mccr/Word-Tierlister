"""The tier chart (UI-13): six small bars, S..F, showing how many words sit in each tier; and each other tab's
own view in the same spot (UI-31): SettledChart (Refine), SwapStrip (Boundary), ConflictCard (Conflicts).

Built to the dataviz rules where they apply: bars at most 24 px wide with a rounded data end and a square
baseline on one hairline axis; the tier letter under each bar and its count on the cap are in text colours
(never the bar colour); bars grow with ease-out when a count changes. No hover note (UI-36: not needed). The bars are
the tier pastels with the pills' faint edge (theme.TIER_BAR): identity comes from the letter and the fixed
S..F order, not from colour, so the colours can stay pastel (the user's choice over a colour-blind-tuned set).
"""
import tkinter as tk

from theme import PALETTE, TIER_BAR
from ui_motion import lerp_color
from widgets import _rounded_points

GROW_MS = 220
PULSE_MS = 240


def compact(n):
    """1,234 -> '1,234'; 12,345 -> '12.3K'; 1,234,567 -> '1.2M' (the cap labels stay short)."""
    if n < 10_000:
        return f"{n:,}"
    if n < 1_000_000:
        return f"{n / 1000:.1f}K".replace(".0K", "K")
    return f"{n / 1_000_000:.1f}M".replace(".0M", "M")


class DistributionChart(tk.Canvas):
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
            self.create_polygon(0, 0, 0, 0, smooth=True, tags=("bar", f"bar{i}"))
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
                pts = [x1, base, x1, base, x1, y1 + r, x1, y1, x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
                       x2, base, x2, base]
                self.coords(f"bar{i}", *pts)
                # the same faint same-hue edge as the tier pills (RoundButton), so pale bars still read
                self.itemconfigure(f"bar{i}", fill=fill, outline=lerp_color(self.colors[i], PALETTE["text"], 0.18),
                                   width=1, state="normal")
            else:
                self.itemconfigure(f"bar{i}", state="hidden")
            self.coords(f"count{i}", x, base - h - 2)
            self.itemconfigure(f"count{i}", text=compact(self.counts[i]) if self.counts[i] else "")
        self.tag_raise("count")

    # ---- data --------------------------------------------------------------------------------------
    def set(self, counts, animate=True):
        """Show these per-tier counts; changed bars grow or shrink with ease-out (GROW_MS)."""
        counts = [int(c or 0) for c in counts]
        peak = max(counts) or 1
        goal = [c / peak for c in counts]
        start = list(self._shown)
        self.counts = counts
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
        """Screen position of the top centre of a tier's bar (where a flying word lands)."""
        _bw, _slot, plot_h, _top, _ll = self._metrics()
        h = max(self._shown[tier] * plot_h, 3 if self.counts[tier] else 0)
        return self.winfo_rootx() + int(self._x(tier)), self.winfo_rooty() + int(self._base - h)

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
            self.create_polygon(_rounded_points(x - bar_w / 2, top, x + bar_w / 2, self._base, 4), smooth=True,
                                fill=PALETTE["surface2"], outline="", tags=("track", f"track{i}"))
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
        if not animate or self._anim is None or start == goal:
            self._shown = goal
            self._paint()
            return

        def frame(p):
            self._shown = [a + (b - a) * p for a, b in zip(start, goal)]
            self._paint()
        self._anim.run(f"chart{id(self)}", GROW_MS, frame)


class SwapStrip(tk.Canvas):
    """Boundary check (UI-31): the six tiers as small pills in a row and, under each join (S|A .. D|F), how
    many boundary checks there swapped the two words; one muted "swaps" caption to the left says what the
    numbers are. The join being checked now is drawn bold with an accent line.

        strip = SwapStrip(parent, TIERS, font("body"), font("head"))
        strip.set([3, 2, 4, 1, 0], current=2)
    """

    CAPTION = "swaps"

    def __init__(self, parent, tiers, font=None, letter_font=None, canvas_bg=None, colors=TIER_BAR):
        super().__init__(parent, bd=0, highlightthickness=0, bg=canvas_bg or PALETTE["bg"])
        self.tiers, self.colors = list(tiers), list(colors)
        self._font, self._lfont = font, letter_font or font
        self.counts, self.current = [0] * (len(self.tiers) - 1), None
        self.shown = True
        self._draw()

    def _draw(self):
        self.delete("all")
        f, lf = self._font, self._lfont
        chip_h = int(lf.metrics("linespace") * 1.4)
        chip_w = chip_h + 4
        gap = max(f.measure("000") + 10, chip_w)
        cap_w = f.measure(self.CAPTION) + 14
        top = 6
        num_y = top + chip_h + 6
        width = cap_w + 4 + len(self.tiers) * chip_w + (len(self.tiers) - 1) * gap + 4
        super().configure(width=width, height=num_y + lf.metrics("linespace") + 4)
        self.create_text(cap_w - 8, num_y, text=self.CAPTION, font=f, fill=PALETTE["muted"], anchor="ne",
                         tags="caption")
        xs = []
        for i, name in enumerate(self.tiers):
            x1 = cap_w + 4 + i * (chip_w + gap)
            xs.append(x1)
            c = self.colors[i]
            self.create_polygon(_rounded_points(x1, top, x1 + chip_w, top + chip_h, chip_h // 2 - 1), smooth=True,
                                fill=c, outline=lerp_color(c, PALETTE["text"], 0.14), tags=("chip", f"chip{i}"))
            self.create_text(x1 + chip_w / 2, top + chip_h / 2, text=name, font=lf, fill=PALETTE["text"],
                             tags=("letter", f"letter{i}"))
        for j in range(len(self.tiers) - 1):
            a, b = xs[j] + chip_w, xs[j + 1]
            on = j == self.current
            y = top + chip_h / 2
            self.create_line(a + 4, y, b - 4, y, fill=PALETTE["accent"] if on else PALETTE["border"],
                             width=2 if on else 1, tags=("join", f"join{j}"))
            self.create_text((a + b) / 2, num_y, text=f"{self.counts[j]:,}", font=lf if on else f,
                             fill=PALETTE["text"] if on else PALETTE["muted"], anchor="n", tags=("num", f"num{j}"))

    def set(self, counts, current=None):
        """Swaps per join (S|A first) and the join being checked now (None: no pair up)."""
        counts = [int(c) for c in counts]
        if counts != self.counts or current != self.current:
            self.counts, self.current = counts, current
            self._draw()
            self.show(self.shown)

    def show(self, on):
        """Show or hide it while keeping its space (the views of all tabs share one spot)."""
        self.shown = bool(on)
        self.itemconfigure("all", state="normal" if on else "hidden")

    def refresh(self):
        self._draw()
        self.show(self.shown)


class ConflictCard(tk.Canvas):
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
        self.create_polygon(_rounded_points(1, 1, w, h, min(14, h // 3)), smooth=True, fill=PALETTE["surface2"],
                            outline=PALETTE["border"], tags="panel")
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
