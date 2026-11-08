# `src/buttons.py`

The program's buttons, drawn on canvases: `RoundButton`, the tier pills (`TierRow`, `TierChip`), the small icon link, the censor pill, the yes button naming a smeared word and the developer tools' bubbles.

- **Uses:** `fonts`, `popups`, `smears`, `smooth`, `theme`, `ui_motion`
- **Used by:** `app`, `browser`, `cards`, `dealing`, `dialogs`, `drawer`, `filepicker`, `fullscreen`, `menus`, `shortcuts`, `syncdialog`, `tiercolours`
- **Tests:** `_selftest_deps`, `_selftest_devtools`, `_selftest_errors`, `_selftest_widgets`, `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `RoundButton`: A rounded, pastel button with a hover tint, a pressed 'dip', a disabled look and a key hint.
  - methods: configure, cget, set_enabled, enabled, set_selected, refresh, veil, invoke, flash
- `TierRow`: The six tier pills S..F, each with its key hint (1-6), a hover lift and the pressed dip (UI-7).
- `TierChip`: A small tier label drawn like the tier pills (rounded, pastel, a faint edge of the same hue), for places that name a tier without being a button: the Anchor words...
  - methods: refresh, set_color
- `LinkButton`: A small icon (smooth.ICONS) that does something when clicked, muted until hovered, with a hover note: the Wiktionary link at the top right of a definition (asked for).
  - methods: refresh
- `DevBubble`: A small lilac pill with a dot and a few words: a developer tool in a dialog's top right corner (asked for: dev tools reachable from the window, not only by command;...
  - methods: invoke, lit, refresh

## Rules and pitfalls (fixed before: keep them fixed)

- DevBubble with `stop=`: the ring is the stop button only while running (`_half` gives "stop" left of `_ring_end`); the bubble never changes size for it (a wider bubble would shift the corner's text). The Tooltip reads `_note` after the bubble's own Motion handler set `_hover` (bound first).
- A RoundButton draws on <Configure> only when its size changed (`_drawn`): every new button was drawn twice. A ShapeCard redraws on `set` only when its spread or choice changed.
- RoundButton and WordCard redraw for a `wraplength` only when it changes (F-50: every re-fit sets it).
- RoundButton.configure with a new bg / fg stops a fade still running (it ended at the old colour: a lit button
  lagged one step behind the arrow keys).
- A button's and a pill's edge is its fill `EDGE` (0.07) of the way to the ink (UI-78: the user chose it softer from mock-ups); keep RoundButton and TierChip on the same constant.
- `smear_items` reads a text item's top left: draw the text with `anchor="nw"` (centred text smeared below and beside itself). `round_rect`'s corners are soft splines: a pill needs `r` about the full height, not half.

## Changing it

- Test each new widget in `tests/_selftest_widgets2.py`.
