# `src/sources.py`

File > Source & Updates (T-6..T-8): from source, make a standalone program next to `tierlist.py`; in the program, unpack its source into a folder (a sync); either way an "Update to the newest version first" tick.

- **Uses:** `constants`, `deps`, `errors`, `filepicker`, `problems`, `saves`, `standalone`, `startup`, `widgets`
- **Used by:** `app`, `stress_ui`
- **Tests:** `_selftest_sources`

The module docstring has the details; this page is the map.

## Public API

- `SourceDialog`: (no docstring)
  - methods: wants_update, make, packages_ready, start, change_folder, fetch, unpack, buttons, alive, close

## Rules and pitfalls (fixed before: keep them fixed)

- What it will do is always shown before it does it (the plan's summary); an update downloads first, shows the plan, and the next Unpack does it.
- The GitHub check runs on a worker thread; the dialog polls its answer.
- `SourceDialog(app, go=True)` does the page's action at once (T-9's yes), from the version you have; an unpack that fails shows the page.
- Making the program checks its packages first (`packages_ready`: the program's own and the builder, `deps.BUILD_PACKAGES`) with the first start's dialog; a required one left out, or a failed install, says why and builds nothing.
