# `tools/layout_trace.py`

A debugging tool for layout jitter: drives the real window with fast key presses and reports any widget that moved when it should not have, or anything drawn over the tier buttons.

- **Uses:** `tierlist`
- **Used by:** nothing (run directly)
- **Tests:** none of its own

The module docstring has the details; this page is the map.

## Public API

- `build_app`: (no docstring)
- `walk`: (no docstring)
- `names`: Readable names for the widgets worth naming (the rest keep their Tk path).
- `snapshot`: (no docstring)
- `main`: (no docstring)

## Rules and pitfalls (fixed before: keep them fixed)

- Run under `xvfb-run` on a headless box; it uses a throwaway save and stays offline.
