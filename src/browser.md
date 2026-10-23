# `src/browser.py`

The Browse / edit window: search, Show / Sort (or click a column heading), the list in tier colours, Move to, Unplace (Delete), Refine, and the definition pane; it opens complete and remembers its view (UI-23, UI-38).

- **Uses:** `constants`, `errors`, `fonts`, `keymap`, `sizing`, `smooth`, `store`, `theme`, `ui_motion`, `widgets`
- **Used by:** `app`, `stress_ui`, `tierlist`
- **Tests:** `_selftest_sizing`, `_selftest_ui2`

The module docstring has the details; this page is the map.

## Public API

- `Browser`: Search / browse / edit window.
  - methods: store, alive, close, zoom_by, sort_by, reload, render_def, move, unplace, undo, refine

## Rules and pitfalls (fixed before: keep them fixed)

- Censored words: a blank cell with the word smeared over it (`widgets.TreeSmears`); refresh the smears whenever rows move (`_draw_outline` does).
- Selection is an outline over the row (the row keeps its tier colour).
- Its text size is set in one place (`_set_size`); its zoom is separate from the main window's and saved.
- Messages name a word with `app.shown()`, never raw.
