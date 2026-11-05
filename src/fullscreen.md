# `src/fullscreen.py`

Full screen (FS-2): the pause menu that stands in for the top menus while the window fills the screen (`PauseMenu`), and the Back bar a dialog wears there (`dialog_bar`).

- **Uses:** `fonts`, `keymap`, `smooth`, `theme`, `ui_motion`, `widgets`
- **Used by:** `app`
- **Tests:** `_selftest_fullscreen`

The module docstring has the details; this page is the map.

## Public API

- `backdrop_colour`: The colour behind the pause menu: the page tinted toward the accent (lilac in both looks).
- `key_names`: How navigation keys read on screen (keymap.NAMES), joined: ("Escape", "BackSpace") -> "Esc / Backspace".
- `PauseMenu`: The full screen menu: a card in the middle of a backdrop that covers the whole window (see the module).
  - methods: is_open, open, close, trail, go, back, activate
- `dialog_bar`: Full screen: a StyledDialog's top gets a Back button and the trail of pages to it ("Menu > Settings > Tier colours"); its own Cancel / Close button goes (Back is...

## Rules and pitfalls (fixed before: keep them fixed)

- The menu is one SmoothCanvas placed over the whole root, redrawn whole on every page change (`_draw`); its key binding returns "break" so nothing reaches App.on_key behind it. Keys it does not use go to `extra_keys` (App: only Full screen's own key, which leaves).
- A pop or slide still running belongs to the page being replaced: `_draw` stops both and every frame checks `_gen`, or the old page's pop resized the new page's row with the same tag (seen: a stray box over "Always compare").
- `canvas.lift()` on a Canvas raises items (it is tag_raise), not the widget: the widget is raised with Tk's own `raise`.
- Tk has no see-through widgets: the backdrop is a tint of the page, not the page dimmed (UI-74, UI-32).
- `dialog_bar` drops the title bar with overrideredirect except on macOS, where such a window gets no keys.
