# `src/shortcuts.py`

Settings > Keyboard shortcuts (UI-48): every action's keys in cards by view; click a key and press the new one; changes apply at once and are saved.

- **Uses:** `fonts`, `keymap`, `theme`, `widgets`
- **Used by:** `app`
- **Tests:** none of its own

The module docstring has the details; this page is the map.

## Public API

- `ShortcutsDialog`: Settings > Keyboard shortcuts...: every action's keys, changeable (see the module's note).
  - methods: listen, cancel, press, swap, remove, reset, reset_all

## Rules and pitfalls (fixed before: keep them fixed)

- Keys are read with `keymap.spec_of`, the same as everywhere else.
