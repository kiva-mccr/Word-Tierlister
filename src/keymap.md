# `src/keymap.py`

Every keyboard shortcut (UI-48): one table of actions with their view and default keys, the user's changes on top, and turning a Tk key event into a key name (`spec_of` / `event_spec`).

- **Uses:** the standard library only
- **Used by:** `app`, `browser`, `shortcuts`
- **Tests:** `_selftest_keymap`, `_selftest_shortcuts`

The module docstring has the details; this page is the map.

## Public API

- `event_spec`: The key name for a key press (Tk's keysym and state; on Windows also its keycode).
- `spec_of`: event_spec for a Tk key event.
- `split`: (modifier prefix, key): "Ctrl+Shift+Tab" -> ("Ctrl+Shift+", "Tab").
- `display`: How a key reads on screen: "Ctrl+z" -> "Ctrl Z", "Up" -> "↑", "question" -> "?".
- `place_keys`: The six keys of the placing set that starts at `first` (same modifiers on all six), or None when fewer than five keys follow it on its keyboard row.
- `place_display`: The placing keys as a hint names them: "1 … 6" (the first and the last), or the one key.
- `Keymap`: The defaults with the user's changes on top.
  - methods: dumps, keys_of, display, place_tier, lookup, clash, is_default, set, reset

## Rules and pitfalls (fixed before: keep them fixed)

- Every key the program reacts to or names comes from here (`App.keys`); never hard-code a key or its name in a hint, button or menu.
- Read events with `spec_of(e, windowing)`, never by hand: it handles Shift, the keypad, macOS Command, and Windows' Ctrl+key names (the zoom keys are read by keycode there, `WIN_CTRL_KEYS`: they did nothing on Windows).
- Placing is a set of six keys that moves together (`place_keys`).

## Changing it

- A new action: a row in `ACTIONS` (its view, label, default keys), then handle it in `App.on_key`; the shortcuts dialog lists it by itself.
