# `src/theme.py`

The colours: `PALETTE` and the tier colours, plus blending helpers (UI-1). No tkinter.

- **Uses:** the standard library only
- **Used by:** `app`, `browser`, `dealing`, `errors`, `filepicker`, `shortcuts`, `startup`, `tierlist`, `ui_chart`, `ui_style`, `widgets`
- **Tests:** `_selftest_chart`, `_selftest_deps`, `_selftest_style`, `_selftest_widgets`, `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `tint`: `h` (#RRGGBB) mixed towards white by `amount` (0 = unchanged, 1 = white).
- `tier_blend`: The tier colour at x in 0..5 (S..F), blended between neighbouring tiers round the colour wheel (hue, saturation and value each go part way), so in-between colours...

## Rules and pitfalls (fixed before: keep them fixed)

- Light theme only; pastel. Take colours from here, never write a hex colour in a widget.
- Where letters or counts already carry the meaning, keep the pastels rather than colour-blind tuning (the user's choice).

## Changing it

- A new colour role: add it to `PALETTE`, then use it by name.
