# `src/ui_style.py`

The ttk styling that gives standard widgets the pastel look (UI-3), on the `clam` theme, including the tick box images (with the minus for "some ticked").

- **Uses:** `fonts`, `theme`
- **Used by:** `app`, `errors`, `review`, `startup`, `tierlist`, `tune_rudeness`, `widgets`
- **Tests:** `_selftest_deps`, `_selftest_errors`, `_selftest_filepicker`, `_selftest_fullscreen`, `_selftest_icon`, `_selftest_looks`, `_selftest_startup`, `_selftest_sync`

The module docstring has the details; this page is the map.

## Public API

- `apply_ttk_style`: Style every ttk widget, the window background and (through the option database) menus, text panes and listboxes.
- `set_icon`: The program's icon on `root` and every window opened from it later (iconphoto's default), in each size, so the title bar, taskbar and window switcher each pick a...
- `veil`: Make `win` see-through, before it is shown.
- `unveil`: Make a veiled window opaque once it has drawn: once it is on screen (looked for every 10 ms, for at most `wait_ms`), every pending redraw is finished, and `ms` later...
- `show_drawn`: Show a withdrawn, already built and placed window so that it appears complete: veiled, shown, unveiled once drawn (veil, unveil).

## Rules and pitfalls (fixed before: keep them fixed)

- A window appears complete (F-48, asked for: no window pops up before it has finished): Tk draws a window only once it is on screen, so a plain `deiconify` shows it piece by piece. Withdraw it while building and placing, then `show_drawn` (or `veil` before `deiconify`, `unveil` after): see-through until drawn. `unveil` never runs the event loop (a polling timer, as the setup window's, could run twice under it). Without a compositor the alpha does nothing and windows show as before.

- The bottom bar's square ttk buttons stay on purpose.
- The icon (`set_icon`, IC-1) goes on through `apply_ttk_style`, so every root gets it; iconphoto's default carries it to every window opened later. It reads `src/icons` beside this file, which is also where a built program unpacks it (`standalone.pyinstaller_args` packs it as "icons"): keep the two in step. Missing files leave Tk's own icon, never an error.
