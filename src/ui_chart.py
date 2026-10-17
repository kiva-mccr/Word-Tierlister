"""The tier chart (UI-13): six small bars, S..F, showing how many words sit in each tier.

Built to the dataviz rules where they apply: bars at most 24 px wide with a rounded data end and a square
baseline on one hairline axis; the tier letter under each bar and its count on the cap are in text colours
(never the bar colour); one hover note per bar; bars grow with ease-out when a count changes. The bars are
the tier pastels with the pills' faint edge (theme.TIER_BAR): identity comes from the letter and the fixed
S..F order, not from colour, so the colours can stay pastel (the user's choice over a colour-blind-tuned set).
"""
import tkinter as tk

from theme import PALETTE, TIER_BAR
from ui_motion import lerp_color
from widgets import Tooltip

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
        self.tooltip = Tooltip(self, self._tip_text, font=font)

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

    def tier_at(self, x):
        """Which tier's column is under canvas x (None between / outside)."""
        _bw, slot, _ph, _top, _ll = self._metrics()
        i = int((x - 4) // slot)
        return i if 0 <= i < len(self.tiers) and x >= 4 else None

    def _tip_text(self, e):
        i = self.tier_at(e.x) if self._visible else None
        if i is None:
            return None
        total = sum(self.counts) or 1
        n = self.counts[i]
        return f"Tier {self.tiers[i]}: {n:,} word{'s' if n != 1 else ''} ({100 * n / total:.0f}% of placed)"

    @property
    def shown(self):
        return self._visible

    def show(self, on):
        """Show or hide the bars while keeping the chart's space (so the layout does not move)."""
        self._visible = bool(on)
        self.itemconfigure("all", state="normal" if on else "hidden")
        if on:
            self._paint()                     # (empty tiers keep their bar hidden)
        else:
            self.tooltip.hide()

    def refresh(self):
        self._draw()
        if not self._visible:
            self.itemconfigure("all", state="hidden")
