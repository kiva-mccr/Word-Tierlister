# `src/tiercolours.py`

Settings > Tier colours... (UI-61): a colour for each tier, picked from pastel swatches or typed as #RRGGBB, with a preview of the pill; Reset to defaults; Apply saves them in the save and reopens the window in them.

- **Uses:** `constants`, `fonts`, `smooth`, `theme`, `ui_motion`, `widgets`
- **Used by:** `app`
- **Tests:** none of its own

The module docstring has the details; this page is the map.

## Public API

- `TierColoursDialog`: Settings > Tier colours...: a swatch strip and a #RRGGBB field per tier (see the module's note).
  - methods: pick, reset, apply

## Rules and pitfalls (fixed before: keep them fixed)

- Apply never recolours the open window: it saves (meta tier_colors; empty for the defaults) and calls `App.reopen`, so every place that draws a tier picks the colours up from `theme`.
- Every swatch must stay light enough for the dark ink (`theme.is_light`; a test checks).
