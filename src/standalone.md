# `src/standalone.py`

Turning the source into a program and back (T-3, T-6..T-8): the list of source files and their manifest, the PyInstaller build that carries the source inside, unpacking / syncing it into a folder, and the newest release on GitHub (update tick).

- **Uses:** `bundle`, `constants`
- **Used by:** `app`, `build`, `check_release`, `sources`, `tierlist`
- **Tests:** `_selftest_build`, `_selftest_sources`, `_selftest_updates`

The module docstring has the details; this page is the map.

## Public API

- `walk`: Files under `d` (relative to `root`), skipping version control, environments and caches; at the top only the folders that ship (SHIP_DIRS).
- `source_files`: The complete source, with its folders: code, docs, tests, the Claude files and the licence; never saves, logs, caches, exports or a built program (docs/ may hold...
- `manifest`: {"files": {path ("/" between folders): sha256 of its bytes}} for `files` (default: source_files).
- `output_name`: (no docstring)
- `output_path`: Where the built program ends up in `dist` for `platform` (sys.platform).
- `program_path`: Where File > Source & Updates puts the program: next to tierlist.py, so it keeps the same save.
- `executable`: The file to run inside what was built (the .app's own executable on macOS).
- `last_build`: The manifest of the program beside tierlist.py ({"files": ..., "made": time}), or None.
- `up_to_date`: True if the program beside tierlist.py exists and was built from the source exactly as it is now (every file the same, none added or removed).
- `pyinstaller_args`: The PyInstaller command line (after "python -m PyInstaller") for this system.
- `has_pyinstaller`: (no docstring)
- `ensure_pyinstaller`: Install PyInstaller if this Python lacks it, or reinstall it if it is there but incomplete (pip; with --break-system-packages on a Python that refuses plain pip...
- `build`: Build the program into `dist` (installing PyInstaller first if needed): its path, or None if it failed.
- `biggest_parts`: [(package or file, MB before compression)] of the n biggest things PyInstaller packed, from the tables it leaves in its work `folder` (PKG-00.toc: files and...
- `make_program`: File > Source & Updates, from source (T-6): build the program from the source as it is now and put it next to tierlist.py (replacing an older one), with its manifest...
- `clean_env`: A copy of the environment fit for starting the other form, Python or the builder: without what a built program sets for itself, which outlives it and points into its...
- `start`: Start the program at `path` on its own, not as a child of this window (which then closes); `args`: its command-line options.
- `bundled_source`: The source carried inside this program (SOURCE_DIR), or None when running from source or built without it.
- `read_manifest`: (no docstring)
- `plan_unpack`: What unpacking `source` (a folder with MANIFEST) into `target` would do, without doing it: {"add": [...], "update": [...], "remove": [...], "backup": [...], "same":...
- `summary`: "3 updated, 1 added, 1 removed (1 edited file kept as .bak first).", or that it is all the same already.
- `unpack`: Unpack (or sync) `source` into `target` as plan_unpack says, then record what was unpacked (UNPACKED).
- `cleanup_place`: Where a program made from `root` goes when the source is to be cleaned up behind it: the folder holding `root`, when `root` was unpacked from a program (UNPACKED) and...
- `move_save`: Move a save file (with its -wal / -shm, its .bak backups and the log beside it) into `folder`, never over a file already there (then it is saved as tierlist-2.db, ...).
- `remove_source`: Remove an unpacked source folder (T-12), run by the new program as it starts (the old one may still be closing: on Windows a folder in use cannot be removed, so it...
- `default_source_folder`: Where the source goes unless you pick another folder: beside the program, in "Word Tier List source".
- `existing_source`: A copy of the source the program sits beside already, or None: tierlist.py right there (it was built from that source: T-6 puts it next to tierlist.py), or a folder...
- `start_source`: Start tierlist.py in `folder` with `python`, on its own (not a child of this program, which then closes).
- `python_for_source`: A Python on this computer to start the unpacked tierlist.py with, or None (a built program has its own Python inside, which cannot run loose source files).
- `open_folder`: Show a folder in the system's file manager.
- `version_tuple`: (1, 2, 0) for "v1.2.0" (the numbers in it, three at most).
- `read_version`: The VERSION in `root`'s src/constants.py (the source being built may be another version than this one).
- `latest_release`: The newest release on GitHub, {"version", "tag", "source" (its source as a zip), "page"}, or None when offline, GitHub cannot be reached or there is none yet.
- `newer`: True if `release` (latest_release) is a newer version than `version`.
- `fetch_source`: Download `release`'s source (GitHub's zip of the repository at its tag) into `folder`, with its manifest, ready to unpack (plan_unpack) or build from; returns `folder`.

## Rules and pitfalls (fixed before: keep them fixed)

- The build checks PyInstaller by importing what the build uses (`PYINSTALLER_CHECK`), repairs an incomplete one, and runs pip and PyInstaller from a neutral folder (reported: "No module named PyInstaller.utils").
- Unpacking only ever touches the program's own files (its manifest and the last unpack's record); a file you edited is kept as `.bak` first; saves, logs and `.venv` are never looked at.
- `source_files` is the one list of what ships: the zip, the program and the manifest all use it.
- No tkinter: the dialog is `sources.py`.
- Everything started from here (the other form, Python, PyInstaller, pip, the file manager) gets `clean_env()`: a built program's Tcl / Tk paths and library path point into its temporary folder, which is gone once it closes (reported: PyInstaller's "Tk data/library directory ... could not be collected!").
- Cleaning up behind (T-12): `remove_source` removes only what the unpack record lists, `OURS` and `__pycache__`, and nothing without that record; `move_save` never writes over a file. The deleting is done by the new program (`--remove-source`), never by the window running from the folder (Windows keeps it locked).
- `existing_source` decides whether the first start unpacks (T-10): tierlist.py beside the program, or any folder beside it with tierlist.py or the unpack record, counts as a copy already there.
- Moving out of the temporary folders is `shutil.move`, never `os.replace` / `os.rename`: they can be on another disk (reported: "[Errno 18] Invalid cross-device link").
- A build over `BIG_MB` logs its biggest parts (`biggest_parts`, from PyInstaller's PKG / PYZ tables): what else on the computer got pulled in.

## Changing it

- What ships: `SHIP_DIRS` / `source_files`. Program names: `output_name` and, for releases, `RELEASE_ASSETS` (the workflow's names must match).
- Release lookups: `latest_release` / `fetch_source` (tests pass their own `fetch`).
