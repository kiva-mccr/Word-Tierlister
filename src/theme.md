# `src/theme.py`

The colours: `PALETTE` and the tier colours, plus blending helpers (UI-1). No tkinter.

- **Uses:** the standard library only
- **Used by:** `app`, `browser`, `dealing`, `errors`, `filepicker`, `shortcuts`, `startup`, `tiercolours`, `tierlist`, `ui_chart`, `ui_style`, `widgets`
- **Tests:** `_selftest_chart`, `_selftest_deps`, `_selftest_looks`, `_selftest_style`, `_selftest_widgets`, `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `tint`: `h` (#RRGGBB) mixed towards white by `amount` (0 = unchanged, 1 = white).
- `mix`: #RRGGBB part way (t, 0..1) from `a` to `b`.
- `is_light`: True for a light colour (a pastel, the light look's surfaces): dark ink reads on it.
- `ink_on`: The text colour for something filled with `fill`: the dark ink on a light one (every tier colour, in the dark look too), the look's own text colour on a dark one.
- `is_hex`: True for a colour written #RRGGBB.
- `apply`: Use the dark look or the light one, and these tier colours (six #RRGGBB, else the defaults), in place: everything that reads PALETTE, TIER_COLORS, TIER_ROW (and...
- `tier_blend`: The tier colour at x in 0..5 (S..F), blended between neighbouring tiers round the colour wheel (hue, saturation and value each go part way), so in-between colours...

## Rules and pitfalls (fixed before: keep them fixed)

- Two looks (UI-62): `LIGHT` (the default) and `DARK`, with the same roles; tier colours can be chosen (UI-61). `apply()` changes `PALETTE`, `TIER_COLORS`, `TIER_ROW` and `TIER_ROW_TEXT` in place before a window is built: read them when drawing, never copy one at import (a default argument, a module constant). Never write a hex colour in a widget.
- Text on a tier colour or another pastel is always the dark ink (`TIER_TEXT`, `ink_on`), in the dark look too.
- Where letters or counts already carry the meaning, keep the pastels rather than colour-blind tuning (the user's choice).

## Changing it

- A new colour role: add it to `PALETTE`, then use it by name.
