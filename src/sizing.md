# `src/sizing.py`

How big windows can be: the usable screen of the monitor in use, Windows dpi awareness, the UI scale factor, and placing windows and pop-ups (on their own monitor).

- **Uses:** the standard library only
- **Used by:** `app`, `browser`, `shortcuts`, `startup`, `stress_ui`, `tierlist`, `widgets`
- **Tests:** `_selftest_sizing`

The module docstring has the details; this page is the map.

## Public API

- `ui_factor`: How much bigger than the classic 96 dpi layout this screen's text is (about 0.75 ..
- `parse_xrandr`: Monitors from `xrandr --current` output: [(x, y, w, h, is_primary)], connected ones with a mode.
- `monitors`: Every monitor as (x, y, w, h, is_primary), asked once; [] when the system cannot tell (then Tk's single screen is used).
- `monitor_at`: (x, y, w, h) of the monitor the point is on: else the nearest one, else Tk's whole screen.
- `monitor_box`: (x, y, w, h) of the monitor to use: the one `root`'s window is on (or its parent's, for a dialog about to open); for a window not on screen yet, the one under the...
- `clamp_to_monitor`: (x, y) moved just enough that a w x h pop-up stays on the monitor of the point `at` (default: x, y).
- `set_dpi_awareness`: Windows: tell the system this program handles display scaling itself (per monitor), before the first window opens.
- `usable_area`: (x, y, w, h): the part of the monitor a window may occupy.
- `is_maximized`: True while `win` is maximized: its state is "zoomed" on Windows and macOS; on Linux the window manager says so through the -zoomed attribute (Tk keeps it up to date;...
- `fit_size`: Window size: the preferred size, but at least the content needs, and never bigger than `area` (w, h).
- `center_geometry`: Tk geometry string putting a w x h window in the middle of `area` = (x, y, w, h).
- `keep_on_screen`: After a window grew (a message shown, a row grew): move it, and if need be shrink it, so it stays on its monitor's usable area.
- `place_dialog`: Size a dialog to its contents and centre it over `parent` (over the screen when the parent is hidden), kept on the screen.

## Rules and pitfalls (fixed before: keep them fixed)

- Every window size comes from here; tests pretend other screens by replacing `usable_area`.
- Pop-ups stay on their monitor (`clamp_to_monitor`).
- `usable_area` / `monitor_box` use the monitor the window (or a dialog's parent) is on; only a window not shown yet goes by the pointer. Dialogs that grow stay on it (`keep_on_screen`).
