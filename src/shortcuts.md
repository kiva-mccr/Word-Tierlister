# `src/shortcuts.py`

Settings > Keyboard shortcuts (UI-48): every action's keys in cards by view; click a key and press the new one; changes apply at once and are saved.

- **Uses:** `buttons`, `dialogs`, `fonts`, `keymap`, `sizing`, `theme`
- **Used by:** `app`
- **Tests:** none of its own

The module docstring has the details; this page is the map.

## Public API

- `ShortcutsDialog`: Settings > Keyboard shortcuts...: every action's keys, changeable (see the module's note).
  - methods: listen, cancel, press, swap, remove, reset, reset_all

## Rules and pitfalls (fixed before: keep them fixed)

- Keys are read with `keymap.spec_of`, the same as everywhere else.
- The cards wrap to the next row when the screen is too narrow for three (`_arrange`), re-checked as rows of keys grow.
- The review's keys (`keymap.DEV_GROUPS`) show only while its window is open, never just because Developer tools is
  on (F-48: that long card made the three stack on a screen under ~1,500 px wide).
