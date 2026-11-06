# `src/popups.py`

The notes that float over the page: `Toast` (a message that fades in and out) and `Tooltip` (a hover note).

- **Uses:** `sizing`, `smooth`, `theme`, `ui_motion`
- **Used by:** `app`, `browser`, `buttons`, `dealing`, `review`, `syncdialog`
- **Tests:** `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `Toast`: A small rounded message that fades in near the bottom of the page, stays a moment, and fades out (UI-11).
  - methods: cget, hurry, show, wiggle, fling, hide
- `Tooltip`: A small hover note (UI-13 / UI-15 / UI-33): appears after DELAY_MS of hovering, just below what it describes, and stays there (only its text changes over another part...
  - methods: text, show_at, hide

## Rules and pitfalls (fixed before: keep them fixed)

- Each message is its own Toast, the newest on top; a key press makes it speed out of the way (`hurry`), never jump.

## Changing it

- Test each new widget in `tests/_selftest_widgets2.py`.
