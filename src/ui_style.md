# `src/ui_style.py`

The ttk styling that gives standard widgets the pastel look (UI-3), on the `clam` theme, including the tick box images (with the minus for "some ticked").

- **Uses:** `fonts`, `theme`
- **Used by:** `app`, `errors`, `tierlist`
- **Tests:** `_selftest_deps`, `_selftest_errors`, `_selftest_filepicker`, `_selftest_icon`, `_selftest_looks`, `_selftest_startup`

The module docstring has the details; this page is the map.

## Public API

- `apply_ttk_style`: Style every ttk widget, the window background and (through the option database) menus, text panes and listboxes.
- `set_icon`: The program's icon on `root` and every window opened from it later (iconphoto's default), in each size, so the title bar, taskbar and window switcher each pick a...

## Rules and pitfalls (fixed before: keep them fixed)

- The bottom bar's square ttk buttons stay on purpose.
- The icon (`set_icon`, IC-1) goes on through `apply_ttk_style`, so every root gets it; iconphoto's default carries it to every window opened later. It reads `src/icons` beside this file, which is also where a built program unpacks it (`standalone.pyinstaller_args` packs it as "icons"): keep the two in step. Missing files leave Tk's own icon, never an error.
