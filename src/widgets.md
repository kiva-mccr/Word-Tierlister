# `src/widgets.py`

The map of the program's widget modules (smears, popups, buttons, menus, drawer, cards, dialogs: see the docstring), and `refresh_widgets`, which re-measures them all after the shared fonts were resized.

- **Uses:** `dialogs`, `drawer`
- **Used by:** `app`, `browser`
- **Tests:** `_selftest_release`, `_selftest_widgets`, `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `refresh_widgets`: Re-measure every canvas widget of ours (RoundButton, WordCard, AnchorLadder, TabBar, the chart...) under `widget` after shared fonts were resized; a definitions...

## Rules and pitfalls (fixed before: keep them fixed)

- A new widget goes in the module for its kind (the list is this file's docstring); `refresh_widgets` finds it if it is a canvas with `refresh()`.

## Changing it

- An open dialog follows a change of the shared fonts (a zoom): `refresh_widgets` calls `StyledDialog.rescale`, which re-wraps every wrapped label in proportion, then sizes and centres the dialog again. Without it the text grew inside a window that kept its size and was cut off (F-18).
- A definitions pane's italics (part of speech, examples) are a copy of the body font's size: `definition_tags` keeps the body on the Text and `refresh_widgets` sets them again after a zoom (F-26: they kept their old size until the pane was refilled).
