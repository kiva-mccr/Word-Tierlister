# `src/sources.py`

File > Source & Updates (T-6..T-8): from source, make a standalone program next to `tierlist.py`; in the program, unpack its source into a folder (a sync); either way an "Update to the newest version first" tick.

- **Uses:** `constants`, `deps`, `errors`, `filepicker`, `problems`, `saves`, `standalone`, `startup`, `widgets`
- **Used by:** `app`, `stress_ui`
- **Tests:** `_selftest_selfupdate`, `_selftest_sources`

The module docstring has the details; this page is the map.

## Public API

- `SourceDialog`: (no docstring)
  - methods: wants_update, make, ask_behind, update_source, start_cleaned, packages_ready, start, change_folder, fetch, unpack, buttons, alive, close
- `update_source`: Bring the source in `root_dir` up to `release`, then start again from it with the same save (this window closes).
- `update_program`: Download this computer's program from `release` beside the running one, put it in its place (the old one is kept as .old until the new one removes it as it starts)...
- `UpdateDialog`: File > Check for updates...
  - methods: again, buttons, alive

## Rules and pitfalls (fixed before: keep them fixed)

- What it will do is always shown before it does it (the plan's summary); an update downloads first, shows the plan, and the next Unpack does it.
- The GitHub check runs on a worker thread; the dialog polls its answer.
- `SourceDialog(app, go=True)` does the page's action at once (T-9's yes), from the version you have; an unpack that fails shows the page.
- Starting the other form (the program, or tierlist.py after unpacking) always closes this one (`App.on_close`): two on one save would both write it.
- Making the program checks its packages first (`packages_ready`: the program's own and the builder, `deps.BUILD_PACKAGES`) with the first start's dialog; a required one left out, or a failed install, says why and builds nothing.
- "Update the source only" (T-13) appears only once the check found a newer version, from source; it restarts with `--db` and the same save, and syncs with `from_program=False`.
- Check for updates (U-1): the program's update downloads into a folder beside it (`standalone.update_folder`: the same disk, and a folder it cannot write is said before anything downloads), swaps with `replace_program` (never overwrite a running .exe: rename it to .old) and restarts with `--db`; the old version goes into meta `updated_from` first. A git checkout updates only with `git pull --ff-only`, never by syncing files over it. Tests fake `sources.show_error` / `ask_yes_no` / `errors.open_link`.
- "Clean up behind?" (T-14) is asked at every build from source, with three answers (`ask_behind`: keep / zip / remove; closing it makes nothing). Tests fake `sources.ask_buttons`, or a build waits on the real question.
