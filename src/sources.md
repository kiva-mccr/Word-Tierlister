# `src/sources.py`

File > Source & Updates (T-6..T-8, U-1; one panel since U-4): Updates on top (check GitHub, update the form you are running); below, from source, make a standalone program next to `tierlist.py`; in the program, unpack its source into a folder (a sync); either way an "Update to the newest version first" tick.

- **Uses:** `constants`, `deps`, `errors`, `filepicker`, `fonts`, `problems`, `saves`, `standalone`, `startup`, `theme`, `widgets`
- **Used by:** `app`, `stress_ui`
- **Tests:** `_selftest_selfupdate`, `_selftest_sources`

The module docstring has the details; this page is the map.

## Public API

- `SourceDialog`: File > Source & Updates...
  - methods: again, update_source, wants_update, make, ask_behind, start_cleaned, packages_ready, start, change_folder, fetch, unpack, buttons, alive, close
- `update_source`: Bring the source in `root_dir` up to `release`, then start again from it with the same save (this window closes).
- `update_program`: Download this computer's program from `release` beside the running one, put it in its place (the old one is kept as .old until the new one removes it as it starts)...

## Rules and pitfalls (fixed before: keep them fixed)

- What it will do is always shown before it does it (the plan's summary); an update downloads first, shows the plan, and the next Unpack does it.
- The GitHub check runs on a worker thread; the dialog polls its answer.
- `SourceDialog(app, go=True)` does the page's action at once (T-9's yes), from the version you have; an unpack that fails shows the page.
- Starting the other form (the program, or tierlist.py after unpacking) always closes this one (`App.on_close`): two on one save would both write it.
- Making the program checks its packages first (`packages_ready`: the program's own and the builder, `deps.BUILD_PACKAGES`) with the first start's dialog; a required one left out, or a failed install, says why and builds nothing.
- One panel (U-4, asked for: there was a separate File > Check for updates): never add a second menu item or dialog for updates, building or unpacking. The Updates section's buttons sit in their own row (`update_buttons`, `StyledDialog.button(row=)`) and are replaced on every answer; "Update" becomes the default (Enter) when a newer version is out, and the bottom action is the default again when it goes.
- From source, "Update" (T-13's "Update the source only") appears only once the check found a newer version; it restarts with `--db` and the same save, and syncs with `from_program=False`. The tick is greyed until a newer version is found.
- Why the check failed is said in plain words (`standalone.describe_fetch_error`): a private repository answers a bare 404 "Not Found" (reported, U-4).
- Updating (U-1): the program's update downloads into a folder beside it (`standalone.update_folder`: the same disk, and a folder it cannot write is said before anything downloads), swaps with `replace_program` (never overwrite a running .exe: rename it to .old) and restarts with `--db`; the old version goes into meta `updated_from` first. A git checkout updates only with `git pull --ff-only`, never by syncing files over it. Tests fake `sources.show_error` / `ask_yes_no` / `errors.open_link`.
- "Clean up behind?" (T-14) is asked at every build from source, with three answers (`ask_behind`: keep / zip / remove; closing it makes nothing). Tests fake `sources.ask_buttons`, or a build waits on the real question.
