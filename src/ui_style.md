# `src/ui_style.py`

The ttk styling that gives standard widgets the pastel look (UI-3), on the `clam` theme, including the tick box images (with the minus for "some ticked").

- **Uses:** `fonts`, `theme`
- **Used by:** `app`, `errors`, `tierlist`
- **Tests:** `_selftest_deps`, `_selftest_errors`, `_selftest_filepicker`, `_selftest_startup`

The module docstring has the details; this page is the map.

## Public API

- `apply_ttk_style`: Style every ttk widget, the window background and (through the option database) menus, text panes and listboxes.

## Rules and pitfalls (fixed before: keep them fixed)

- The bottom bar's square ttk buttons stay on purpose.
