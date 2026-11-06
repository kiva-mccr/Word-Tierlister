# `src/menus.py`

The program's own drop-down menus, choices, header menus and tabs (`DropMenu`, `ChoiceButton`, `HeaderMenus`, `TabBar`), and closing every open drop-down when the program loses focus.

- **Uses:** `buttons`, `sizing`, `smooth`, `theme`
- **Used by:** `app`, `browser`, `tune_rudeness`
- **Tests:** `_selftest_fullscreen`, `_selftest_motion`, `_selftest_ui`, `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `TabBar`: Folder-style tabs over a page (UI-10): a hairline runs the full width under the tabs, and the chosen tab is drawn in the page colour with its sides and rounded top...
  - methods: tab_x, set, show_only, get, refresh
- `DropMenu`: A styled drop-down menu (UI-10): a borderless window with roomy rows, the pastel highlight, check marks and shortcut hints, used by the header's File / Edit / View /...
  - methods: labels, is_open, prepare, open, invoke, close
- `ChoiceButton`: A drop-down choice (UI-43): a soft button showing the current value and a little arrow; a click opens a DropMenu with the choices (a check mark on the current one).
  - methods: set_values, toggle, refresh
- `HeaderMenus`: The row of header menu buttons (File, Edit, View, Settings) with their DropMenus (UI-10).
  - methods: open_name, toggle, open_menu, close
- `close_popups`: Close every drop-down the program has open (UI-43): all DropMenus (header menus, ChoiceButtons).
- `watch_focus`: When the whole program loses focus (another program came to the front), close its drop-downs (close_popups) and call on_lost().

## Rules and pitfalls (fixed before: keep them fixed)

- A DropMenu's window is built once and kept, hidden while closed (F-49, reported: building it at every open took 40-190 ms on GNOME / Wayland). `open` refreshes the kept rows (check marks, the items' current functions: App.apply_keys makes the list again); different labels or shortcuts (`_shape`) make it again. HeaderMenus builds each one ahead while idle (`prepare`). `is_open` is the shown flag, not `win`.
- `prepare` also warms the hidden window (`_warm`, F-56): layout, every row's system window, the check mark's font (a font fallback search, slow the first time on systems with many fonts). It never shows the window.
- A closed DropMenu is hidden (withdrawn) everywhere, never parked mapped off-screen (F-54, reported: on GNOME the move back on screen was sometimes lost, so the menu never showed while its button stayed lit, and the next click "closed" it). Use `is_open` for "open".
- HeaderMenus closes its menu on the main window's `<Configure>` only when it really moved or changed size since the menu opened (`_top_configured` compares `_top_geometry()` with `_top_geo`, taken in `open_menu`; never the event's own numbers): Windows sends one when the window just comes to the front, which closed the menu opened by hovering from File to Edit (T-20, GitHub's Windows).
- No `ttk.Combobox` / `tk.Menu` pop-ups (they grab input on Linux): use `ChoiceButton` / `DropMenu`. Dialogs build on `StyledDialog` (`StyledDialog.text` for wrapped lines).

## Changing it

- Test each new widget in `tests/_selftest_widgets2.py`.
