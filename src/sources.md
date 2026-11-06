# `src/sources.py`

File > Source & Updates (T-6..T-8, U-1; one panel since U-4): Updates on top (check GitHub, update the form you are running); below, from source, make a standalone program next to `tierlist.py`; in the program, unpack its source into a folder (a sync); either way an "Update to the newest version first" tick.

- **Uses:** `background`, `constants`, `deps`, `dialogs`, `errors`, `filepicker`, `fonts`, `problems`, `saves`, `standalone`, `startup`, `theme`
- **Used by:** `app`, `stress_ui`, `tierlist`
- **Tests:** `_selftest_devtools`, `_selftest_nightly`, `_selftest_selfupdate`, `_selftest_sources`

The module docstring has the details; this page is the map.

## Public API

- `SourceDialog`: File > Source & Updates...
  - methods: again, update_nightly, update_source, add_to_menu, wants_update, make, ask_behind, start_cleaned, packages_ready, start, change_folder, fetch, unpack, buttons, alive, close
- `ago`: "3 hours ago" for a time (seconds since 1970).
- `update_source`: Bring the source in `root_dir` up to `release`, then start again from it with the same save (this window closes).
- `update_program`: Download this computer's program from `release` beside the running one, put it in its place (the old one is kept as .old until the new one removes it as it starts)...
- `update_nightly_program`: In the program, "Update to nightly" (asked for: from main's source, built here): main's source goes into the source folder beside the program...

## Rules and pitfalls (fixed before: keep them fixed)

- The nightly is for developers only (DT-2): `_nightly_on` (Developer tools on, the Nightly bubble lit) gates the whole section, and main is not asked for while Developer tools is off. It once showed to everyone whenever main was ahead.
- The nightly section's buttons sit in a row frame inside `nightly_box`: clearing it (the Nightly bubble) drops them from `dlg.buttons` by their path too, or a stale entry stayed.
- What it will do is always shown before it does it (the plan's summary); an update downloads first, shows the plan, and the next Unpack does it.
- The GitHub check runs on a worker thread; the dialog polls its answer.
- `SourceDialog(app, go=True)` does the page's action at once (T-9's yes), from the version you have; an unpack that fails shows the page.
- Starting the other form (the program, or tierlist.py after unpacking) always closes this one (`App.on_close`): two on one save would both write it.
- Making the program checks its packages first (`packages_ready`: the program's own and the builder, `deps.BUILD_PACKAGES`) with the first start's dialog; a required one left out, or a failed install, says why and builds nothing.
- One panel (U-4, asked for: there was a separate File > Check for updates): never add a second menu item or dialog for updates, building or unpacking. The Updates section's buttons sit in their own row (`update_buttons`, `StyledDialog.button(row=)`) and are replaced on every answer; "Update" becomes the default (Enter) when a newer version is out, and the bottom action is the default again when it goes.
- The applications menu / Start menu section (U-5, U-6) shows only in the program, only where Word Tierlister can add itself (`deps.menu_name`: not macOS), and only until it is in the menu (`deps.in_menu`: a Linux launcher with NoDisplay is not in it); once added its button goes. From source, making the program has a tick ("Add the program to the ...", ticked to start with: U-7), shown only while it is not in the menu; when it is, the menu moves to the new program anyway (`was_in_menu`) before it starts, so a source cleaned up behind never leaves a broken entry. No File menu item for it any more.
- From source, "Update" (T-13's "Update the source only") appears only once the check found a newer version; it restarts with `--db` and the same save, and syncs with `from_program=False`. The tick is greyed until a newer version is found.
- Why the check failed is said in plain words (`standalone.describe_fetch_error`): a private repository answers a bare 404 "Not Found" (reported, U-4).
- Updating (U-1): the program's update downloads into a folder beside it (`standalone.update_folder`: the same disk, and a folder it cannot write is said before anything downloads), swaps with `replace_program` (never overwrite a running .exe: rename it to .old) and restarts with `--db`; the old version goes into meta `updated_from` first. A git checkout updates only with `git pull --ff-only`, never by syncing files over it. Tests fake `sources.show_error` / `ask_yes_no` / `errors.open_link`.
- "Clean up behind?" (T-14) is asked at every build from source, with three answers (`ask_behind`: keep / zip / remove; closing it makes nothing). Tests fake `sources.ask_buttons`, or a build waits on the real question.
- Nightly (asked for: a button that shows up only when one is available, fully manual): the check asks for main too (`nightly`, default `standalone.latest_main`) and `nightly_box` shows the line and "Update to nightly" only when files differ; never a toast or a check at start. From source it is `update_source` with main (git: `git pull --ff-only origin main`, refused when the checkout is not on main). In the program (`update_nightly_program`) main's source is synced into the source folder beside it (or pulled there when that is a git checkout), which starts with `--build-nightly <program>`: `SourceDialog(go=True, target=)` builds in the program's place without the clean-up question or the menu tick, sets `updated_from` to "nightly <sha>" (from meta `nightly_pending`, so the building source says nothing itself) and starts the program with `--db`. Needs a Python on the computer (offered like unpacking's).
