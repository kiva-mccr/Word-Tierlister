# `tools/speed_check.py`

Times what runs per word, per duel and per click (refresh, place, skip, undo, both duel tabs, every Browse sort and filter) on a big throwaway save, dense and sparse (F-9). Run it after any change to those paths; it fails when one takes more than twice its budget.

- **Uses:** `app`, `definitions`, `store`
- **Used by:** nothing (run directly)
- **Tests:** none of its own

The module docstring has the details; this page is the map.

## Public API

- `build`: A save of `n` words with `placed` of them in random tiers (ratings and duel counts spread out).
- `timed`: (no docstring)
- `check`: (no docstring)
- `main`: (no docstring)

## Rules and pitfalls (fixed before: keep them fixed)

- Budgets: about 40 ms an action, 200 ms a Browse sort. A dense save and a sparse one both matter: a query can be quick on one and slow on the other.
- Under xvfb-run on a headless box; it never touches your save and stays offline.
