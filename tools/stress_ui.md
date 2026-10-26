# `tools/stress_ui.py`

Random actions on the real main window (keys, tabs, resizes, Browse, dialogs, the definitions pane, undo, censoring) on a throwaway save and a pretend 1366 x 768 screen (F-9). It fails on any error and on a window bigger than the screen. Run it after UI changes that touch layout, fitting or several windows at once.

- **Uses:** `app`, `browser`, `errors`, `sizing`, `sources`, `tierlist`
- **Used by:** nothing (run directly)
- **Tests:** none of its own

The module docstring has the details; this page is the map.

## Public API

- `setup`: The window on a small pretend screen, over a save with a few placed and a few obscene words (censored).
- `browse`: (no docstring)
- `act`: One random action.
- `main`: (no docstring)

## Rules and pitfalls (fixed before: keep them fixed)

- Every dialog that waits for a click (show_message, ask_yes_no, ...) is stubbed in each module that imported it, or the run hangs.
- Patch `usable_area` in app, browser and sizing alike (each imported its own name); one missed and the window fits a different screen than the check expects.
