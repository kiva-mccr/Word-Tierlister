"""Settings > Tier colours... (UI-61, asked for; UI-80 made it simpler, from mock-ups): a colour for each tier, S to F.
The six tier pills sit in a row; click one (it gets a ring), then set its colour with three bars, H (hue), S
(saturation) and V (value), or type it as a hex code: the bars and the code follow each other, and the pill shows the
colour as it changes. Then click the next tier. Each bar's track runs through the colours it would give, the others
held (smooth.gradient_image). The letters on a tier are always the dark ink (theme.TIER_TEXT), so a colour it does not
read on at 4.5:1 (UI-76) is called too dark and Apply waits. Reset puts back the look's defaults. Apply saves them in
the save (meta tier_colors) and reopens the window (App.reopen), so every place that shows a tier (the pills, the chart,
the shelf, Browse's rows) takes them; dark mode keeps them.

    TierColoursDialog(app)                # app: the App (its store, animator and reopen)
"""
import colorsys
import json
import tkinter as tk
from tkinter import ttk

from constants import TIERS
from fonts import font
from smooth import SmoothCanvas, gradient_image
from theme import PALETTE, TIER_COLORS, TIER_TEXT, contrast, default_tiers, is_hex
from ui_motion import lerp_color
from widgets import EDGE, StyledDialog

READABLE = 4.5            # the dark ink on a tier colour at least this (WCAG's text contrast; UI-76)
BARS = (("H", 360, "°"), ("S", 100, "%"), ("V", 100, "%"))     # each bar's letter, the reading at its right, its unit


def to_hex(hsv):
    """#RRGGBB for an (h, s, v), each 0..1."""
    return "#%02X%02X%02X" % tuple(round(c * 255) for c in colorsys.hsv_to_rgb(*hsv))


def to_hsv(color, before=None):
    """(h, s, v) for #RRGGBB; where a grey has no hue (or black no saturation), `before`'s is kept, so the bar does
    not jump to the left end."""
    h, s, v = colorsys.rgb_to_hsv(*(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)))
    if before is not None:
        if v == 0:
            h, s = before[0], before[1]
        elif s == 0:
            h = before[0]
    return [h, s, v]


def too_dark(color):
    """True when the dark ink does not read on `color` (below READABLE)."""
    return contrast(TIER_TEXT, color) < READABLE


class TierColoursDialog:
    """Settings > Tier colours...: tier pills, H / S / V bars and a hex code (see the module's note)."""

    def __init__(self, app):
        self.app = app
        self.colors = list(TIER_COLORS)
        self.hsv = [to_hsv(c) for c in self.colors]
        self.current = 0
        self._typing = False                      # (the code is being typed: the bars follow, the field is left)
        self.dlg = dlg = StyledDialog(app.root, "Tier colours", "Tier colours",
                                      "Click a tier, then set its colour with the bars or a hex code. Apply reopens "
                                      "the window in them.", animator=app.anim, wrap_chars=56)
        bg = PALETTE["bg"]
        line = font("body").metrics("linespace")
        # the tier pills, one canvas: a click picks the tier to edit, which wears a ring
        head = font("head")
        self._pill_h = ph = int(head.metrics("linespace") * 1.5)
        self._pill_w = pw = max(ph, head.measure("W") + head.metrics("linespace"))
        self._gap = gap = 10
        self.pills = SmoothCanvas(dlg.body, bd=0, highlightthickness=0, bg=bg, cursor="hand2",
                                  width=len(TIERS) * (pw + gap) + 4, height=ph + 10)
        self.pills.pack(anchor="w", pady=(0, 10))
        for t, name in enumerate(TIERS):
            x = 5 + t * (pw + gap)
            self.pills.round_rect(x - 4, 1, x + pw + 4, ph + 9, (ph + 8) // 2, outline="", width=2, tags=(f"ring{t}",))
            self.pills.round_rect(x, 5, x + pw, ph + 5, ph // 2, fill=self.colors[t], tags=(f"pill{t}", f"t{t}"))
            self.pills.create_text(x + pw / 2, 5 + ph / 2, text=name, font=head, fill=TIER_TEXT, tags=(f"t{t}",))
        self.pills.bind("<Button-1>", lambda e: self.select(self.tier_at(e.x)))
        # the three bars: a letter, the track with its knob, the reading
        grid = tk.Frame(dlg.body, bg=bg)
        grid.pack(anchor="w")
        self._knob = kd = int(line * 1.2)
        self._bar_h = max(8, int(line * 0.75))
        self._bar_w = font("body").measure("n") * 34
        self.bars, self.readings = [], []
        for i, (letter, _top, _unit) in enumerate(BARS):
            ttk.Label(grid, text=letter, font=head).grid(row=i, column=0, sticky="w", padx=(0, 12), pady=4)
            bar = SmoothCanvas(grid, bd=0, highlightthickness=0, bg=bg, cursor="hand2",
                               width=self._bar_w + kd + 2, height=kd + 4)
            bar.grid(row=i, column=1, pady=4)
            bar.create_image(kd // 2, (kd + 4 - self._bar_h) // 2, anchor="nw", tags=("track",))
            bar.round_rect(0, 1, kd + 2, kd + 3, (kd + 2) / 2, fill=lerp_color("#FFFFFF", TIER_TEXT, 0.35),
                           tags=("knob", "edge"))                  # (a faint rim round the knob's white ring)
            bar.round_rect(1, 2, kd + 1, kd + 2, kd / 2, outline="#FFFFFF", width=3, tags=("knob", "dot"))
            for event in ("<Button-1>", "<B1-Motion>"):
                bar.bind(event, lambda e, i=i: self.drag(i, e.x))
            reading = ttk.Label(grid, foreground=PALETTE["muted"], width=5, anchor="e")
            reading.grid(row=i, column=2, sticky="e", padx=(12, 0), pady=4)
            self.bars.append(bar), self.readings.append(reading)
        # the hex code, with a swatch of the colour beside it
        row = tk.Frame(dlg.body, bg=bg)
        row.pack(anchor="w", pady=(8, 0))
        ttk.Label(row, text="Hex", foreground=PALETTE["muted"]).pack(side="left", padx=(0, 10))
        self.var = tk.StringVar()
        self.field = ttk.Entry(row, textvariable=self.var, width=9, font=font("body"))
        self.field.pack(side="left")
        self.swatch = SmoothCanvas(row, bd=0, highlightthickness=0, bg=bg, width=line + 6, height=line + 6)
        self.swatch.pack(side="left", padx=(10, 0))
        self.swatch.round_rect(2, 2, line + 4, line + 4, line // 3, tags=("sw",))
        self.var.trace_add("write", lambda *_a: self._typed())
        # a note (too dark, or not a colour; one line): its room kept, so the dialog never changes size while dragging
        warn_bg, warn_fg = PALETTE["warn"]
        self._note_colors = (warn_bg, warn_fg)
        self.note = tk.Label(dlg.body, text="", font=font("body"), bg=bg, fg=warn_fg, padx=10, pady=4,
                             wraplength=dlg.wrap, justify="left", anchor="w")
        self.note.pack(anchor="w", fill="x", pady=(12, 0))
        dlg.button("Reset to defaults", self.reset, side="left")
        dlg.button("Cancel", dlg.close)
        self.apply_button = dlg.button("Apply", self.apply, default=True)
        self._draw()
        dlg.show()

    # -- choosing
    def select(self, tier):
        """Edit `tier` now: it wears the ring, and the bars and the code show its colour."""
        self.current = tier
        self._draw()

    def tier_at(self, x):
        """The tier whose pill is at canvas x (the whole pill and half the gap each side: a pill's shape is an image,
        which a tag_bind never sees, so only its letter answered clicks)."""
        return max(0, min(len(TIERS) - 1, int((x - 5 + self._gap / 2) // (self._pill_w + self._gap))))

    def drag(self, bar, x):
        """A click or drag on bar 0 (H), 1 (S) or 2 (V) at canvas x: the current tier takes that value."""
        start = self._knob // 2 + 1                  # (where the track starts: its image has a pixel round it)
        self.hsv[self.current][bar] = min(1.0, max(0.0, (x - start) / self._bar_w))
        self.colors[self.current] = to_hex(self.hsv[self.current])
        self._draw()

    def set_color(self, color):
        """The current tier takes #RRGGBB (as typed): the bars move to it."""
        color = color.upper()
        self.hsv[self.current] = to_hsv(color, self.hsv[self.current])
        self.colors[self.current] = color
        self._draw()

    def _typed(self):
        """The code changed: a whole colour (the # may be left out) recolours the tier; anything else waits, and says
        so."""
        if self._typing is None:
            return                                   # (the bars wrote it)
        text = self.var.get().strip()
        if text and text[0] != "#":
            text = "#" + text
        if not is_hex(text):
            self._note("Write the colour as #RRGGBB, for example #FFB3C1.")
            self._enable(False)
            return
        self._typing = True
        try:
            self.set_color(text)
        finally:
            self._typing = False

    def reset(self):
        for t, c in enumerate(default_tiers()):          # (the look's own: Dusk's in dark mode, UI-77)
            self.colors[t] = c
            self.hsv[t] = to_hsv(c)
        self._draw()

    # -- drawing
    def _draw(self):
        """Everything shown from the colours: pills, ring, bars and their knobs, readings, code, swatch, note, Apply."""
        cur, hsv = self.current, self.hsv[self.current]
        color = self.colors[cur]
        for t, c in enumerate(self.colors):
            self.pills.itemconfigure(f"pill{t}", fill=c, outline=lerp_color(c, TIER_TEXT, EDGE))
            self.pills.itemconfigure(f"ring{t}", outline=PALETTE["accent"] if t == cur else "")
        h, s, v = hsv
        tracks = ([colorsys.hsv_to_rgb(x, s, v) for x in self._steps()],
                  [colorsys.hsv_to_rgb(h, x, v) for x in self._steps()],
                  [colorsys.hsv_to_rgb(h, s, x) for x in self._steps()])
        edge = PALETTE["border"]
        for i, bar in enumerate(self.bars):
            cols = [tuple(round(c * 255) for c in rgb) for rgb in tracks[i]]
            bar._track = gradient_image(bar, self._bar_w, self._bar_h, cols, edge)    # (kept alive by the canvas)
            bar.itemconfigure("track", image=bar._track)
            kd, x = self._knob, self._bar_w * hsv[i]
            bar.round_rect_coords("edge", x, 1, x + kd + 2, kd + 3)
            bar.round_rect_coords("dot", x + 1, 2, x + kd + 1, kd + 2)
            bar.itemconfigure("dot", fill=color)
            top, unit = BARS[i][1], BARS[i][2]
            self.readings[i].config(text=f"{round(hsv[i] * top)}{unit}")
        if not self._typing:
            self._typing = None
            try:
                self.var.set(color)
            finally:
                self._typing = False
        self.swatch.itemconfigure("sw", fill=color, outline=lerp_color(color, TIER_TEXT, EDGE))
        dark = [TIERS[t] for t, c in enumerate(self.colors) if too_dark(c)]
        if dark:
            self._note(f"Too dark for the letter to read: {', '.join(dark)}. Drag V up or S down.")
        else:
            self._note("")
        self._enable(not dark)

    def _steps(self):
        """0..1 at each pixel column of a track."""
        n = self._bar_w
        return [x / (n - 1) for x in range(n)]

    def _enable(self, on):
        if self.apply_button._enabled != on:            # (only a change: it eases to its new look)
            self.apply_button.set_enabled(on)

    def _note(self, text):
        self.note.config(text=text, bg=self._note_colors[0] if text else PALETTE["bg"])

    def apply(self):
        """Save the colours and reopen the window in them (Apply waits while a colour is too dark)."""
        if any(too_dark(c) for c in self.colors):
            return
        self.dlg.close()
        if [c.upper() for c in self.colors] == [c.upper() for c in TIER_COLORS]:
            return                                             # (nothing changed: no need to reopen)
        same = [c.upper() for c in self.colors] == [c.upper() for c in default_tiers()]
        self.app.store.set_meta("tier_colors", "" if same else json.dumps(self.colors))
        self.app.reopen()
