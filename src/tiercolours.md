# `src/tiercolours.py`

Settings > Tier colours... (UI-61, UI-80): a colour for each tier: click its pill, then set the colour with H / S / V bars or a hex code (each follows the other); Reset to defaults; Apply saves them in the save and reopens the window in them.

- **Uses:** `constants`, `fonts`, `smooth`, `theme`, `ui_motion`, `widgets`
- **Used by:** `app`
- **Tests:** `_selftest_looks`

The module docstring has the details; this page is the map.

## Public API

- `to_hex`: #RRGGBB for an (h, s, v), each 0..1.
- `to_hsv`: (h, s, v) for #RRGGBB; where a grey has no hue (or black no saturation), `before`'s is kept, so the bar does not jump to the left end.
- `too_dark`: True when the dark ink does not read on `color` (below READABLE).
- `TierColoursDialog`: Settings > Tier colours...: tier pills, H / S / V bars and a hex code (see the module's note).
  - methods: select, drag, set_color, reset, apply

## Rules and pitfalls (fixed before: keep them fixed)

- Apply never recolours the open window: it saves (meta tier_colors; empty for the defaults) and calls `App.reopen`, so every place that draws a tier picks the colours up from `theme`.
- A colour the dark ink (`theme.TIER_TEXT`) does not read on at 4.5:1 is too dark: the note says so and Apply waits (`too_dark`). Every default tier colour passes (a test checks).
- Writing the code from the bars must not run the field's trace back into the bars (`_typing` is None meanwhile), and what is being typed is never rewritten under the caret.
- A grey has no hue and black no saturation: `to_hsv(..., before)` keeps the old ones so a knob does not jump to the left end.
- The note keeps its line when empty, so the dialog never changes size while a bar is dragged; keep its texts to one line.
