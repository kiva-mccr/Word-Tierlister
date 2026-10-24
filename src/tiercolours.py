"""Settings > Tier colours... (UI-61, asked for): a colour for each tier, S to F. Each row shows the tier's pill as
it will look, a strip of pastel swatches (theme.SWATCHES) and the colour written #RRGGBB, to type any other. Reset
puts back the defaults. Apply saves them in the save (meta tier_colors) and reopens the window (App.reopen), so
every place that shows a tier (the pills, the chart, the shelf, Browse's rows) takes them; dark mode keeps them.

    TierColoursDialog(app)                # app: the App (its store, animator and reopen)
"""
import json
import tkinter as tk
from tkinter import ttk

from constants import TIERS
from fonts import font
from smooth import SmoothCanvas
from theme import DEFAULT_TIERS, PALETTE, SWATCHES, TIER_COLORS, is_hex
from ui_motion import lerp_color
from widgets import StyledDialog, TierChip


class TierColoursDialog:
    """Settings > Tier colours...: a swatch strip and a #RRGGBB field per tier (see the module's note)."""
    SIZE = 22                                 # a swatch's side at the body font's size (it follows the font)

    def __init__(self, app):
        self.app = app
        self.colors = list(TIER_COLORS)
        self.dlg = dlg = StyledDialog(app.root, "Tier colours", "Tier colours",
                                      "Pick a colour for each tier, or type one (#RRGGBB). Apply reopens the window "
                                      "in them.", animator=app.anim, wrap_chars=60)
        bg = PALETTE["bg"]
        grid = tk.Frame(dlg.body, bg=bg)
        grid.pack(anchor="w")
        self.chips, self.strips, self.fields, self.vars = [], [], [], []
        size = self._size = max(self.SIZE, int(font("body").metrics("linespace") * 1.3))
        for t, name in enumerate(TIERS):
            chip = TierChip(grid, name, self.colors[t], font("head"), canvas_bg=bg)
            chip.grid(row=t, column=0, padx=(0, 12), pady=4)
            strip = SmoothCanvas(grid, bd=0, highlightthickness=0, bg=bg, cursor="hand2",
                                 width=len(SWATCHES) * (size + 4) + 2, height=size + 4)
            strip.grid(row=t, column=1, pady=4)
            for i, c in enumerate(SWATCHES):
                x = 2 + i * (size + 4)
                strip.round_rect(x, 2, x + size, 2 + size, size // 3, fill=c,
                                 outline=lerp_color(c, PALETTE["text"], 0.14), tags=(f"sw{i}",))
                strip.tag_bind(f"sw{i}", "<Button-1>", lambda e, t=t, c=c: self.pick(t, c))
            var = tk.StringVar(value=self.colors[t])
            field = ttk.Entry(grid, textvariable=var, width=9, font=font("body"))
            field.grid(row=t, column=2, padx=(12, 0), pady=4)
            var.trace_add("write", lambda *_a, t=t: self._typed(t))
            self.chips.append(chip), self.strips.append(strip), self.fields.append(field), self.vars.append(var)
            self._ring(t)
        self.note = dlg.text("", muted=True, pady=(10, 0))
        dlg.button("Reset to defaults", self.reset, side="left")
        dlg.button("Cancel", dlg.close)
        dlg.button("Apply", self.apply, default=True)
        dlg.show()

    def pick(self, tier, color):
        """A swatch clicked: that tier takes it (its field and pill follow)."""
        self.vars[tier].set(color)

    def _typed(self, tier):
        """The field changed (typed, or a swatch): a whole #RRGGBB recolours the pill; anything else waits."""
        text = self.vars[tier].get().strip()
        if not is_hex(text):
            return
        self.colors[tier] = text.upper()
        self.chips[tier].set_color(self.colors[tier])
        self._ring(tier)
        self.note.config(text="")

    def _ring(self, tier):
        """A ring round the swatch the tier has now (none when it was typed)."""
        strip = self.strips[tier]
        strip.delete("ring")
        if self.colors[tier] in SWATCHES:            # (a soft lilac halo behind the swatch, drawn smooth)
            i = SWATCHES.index(self.colors[tier])
            x = 2 + i * (self._size + 4)
            strip.round_rect(x - 2, 0, x + self._size + 2, self._size + 4, self._size // 3 + 2, fill=PALETTE["accent"],
                             outline=PALETTE["accent"], tags=("ring",))
            strip.tag_lower("ring")

    def reset(self):
        for t, c in enumerate(DEFAULT_TIERS):
            self.vars[t].set(c)

    def apply(self):
        """Save the colours and reopen the window in them; a field that is not a colour says so instead."""
        bad = [TIERS[t] for t, v in enumerate(self.vars) if not is_hex(v.get().strip())]
        if bad:
            self.note.config(text=f"Write {' and '.join(bad)} as #RRGGBB (for example #FFB3C1).")
            self.dlg.refit()
            return
        self.dlg.close()
        if [c.upper() for c in self.colors] == [c.upper() for c in TIER_COLORS]:
            return                                             # (nothing changed: no need to reopen)
        same = self.colors == list(DEFAULT_TIERS)
        self.app.store.set_meta("tier_colors", "" if same else json.dumps(self.colors))
        self.app.reopen()
