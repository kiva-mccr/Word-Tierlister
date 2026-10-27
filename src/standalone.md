# `src/standalone.py`

Turning the source into a program and back (T-3, T-6..T-8): the list of source files and their manifest, the PyInstaller build that carries the source inside, unpacking / syncing it into a folder, and the newest release on GitHub (update tick).

- **Uses:** `bundle`, `constants`, `deps`
- **Used by:** `app`, `build`, `check_release`, `sources`, `tierlist`
- **Tests:** `_selftest_build`, `_selftest_fonts`, `_selftest_icon`, `_selftest_selfupdate`, `_selftest_sources`, `_selftest_updates`

The module docstring has the details; this page is the map.

## Public API

- `walk`: Files under `d` (relative to `root`), skipping version control, environments and caches; at the top only the folders that ship (SHIP_DIRS).
- `source_files`: The complete source, with its folders: code, docs, tests, the Claude files, the licence and git's own lists (REPO_FILES); never saves, logs, caches, exports or a...
- `manifest`: {"files": {path ("/" between folders): sha256 of its bytes}} for `files` (default: source_files).
- `output_name`: (no docstring)
- `output_path`: Where the built program ends up in `dist` for `platform` (sys.platform).
- `program_path`: Where File > Source & Updates puts the program: next to tierlist.py, so it keeps the same save.
- `remove_renamed_program`: After a build put the program beside `root`: remove one built there under the program's old name (word-tierlist, "Word Tier List.app") and its build record, which the...
- `executable`: The file to run inside what was built (the .app's own executable on macOS).
- `last_build`: The manifest of the program beside tierlist.py ({"files": ..., "made": time}), or None.
- `up_to_date`: True if the program beside tierlist.py exists and was built from the source exactly as it is now (every file the same, none added or removed).
- `pyinstaller_args`: The PyInstaller command line (after "python -m PyInstaller") for this system.
- `has_pyinstaller`: (no docstring)
- `ensure_pyinstaller`: Install PyInstaller if this Python lacks it, or reinstall it if it is there but incomplete (pip; with --break-system-packages on a Python that refuses plain pip...
- `build`: Build the program into `dist` (installing PyInstaller first if needed): its path, or None if it failed.
- `biggest_parts`: [(package or file, MB before compression)] of the n biggest things PyInstaller packed, from the tables it leaves in its work `folder` (PKG-00.toc: files and...
- `make_program`: File > Source & Updates, from source (T-6): build the program from the source as it is now and put it next to tierlist.py (replacing an older one), with its manifest...
- `give_icon`: Linux: show the program's icon on its file in the file manager (reported: none on Fedora).
- `clean_env`: A copy of the environment fit for starting the other form, Python or the builder: without what a built program sets for itself, which outlives it and points into its...
- `start`: Start the program at `path` on its own, not as a child of this window (which then closes); `args`: its command-line options.
- `bundled_source`: The source carried inside this program (SOURCE_DIR), or None when running from source or built without it.
- `read_manifest`: The record `name` in `folder` (or under its name from before the rename, OLD_RECORDS), or None.
- `remove_old_record`: Remove the record `name` under its name from before the rename, once it is written under the new one.
- `plan_unpack`: What unpacking `source` (a folder with MANIFEST) into `target` would do, without doing it: {"add": [...], "update": [...], "remove": [...], "backup": [...], "same":...
- `summary`: "3 updated, 1 added, 1 removed (1 edited file kept as .bak first).", or that it is all the same already.
- `unpack`: Unpack (or sync) `source` into `target` as plan_unpack says, then record what was unpacked (UNPACKED).
- `came_from_program`: True if an unpack record (UNPACKED) is of a folder unpacked from the program, not only updated from GitHub.
- `cleanup_place`: Where a program made from `root` goes when the source is to be cleaned up behind it (asked for: offered whenever the program is made, however the source came here;...
- `mark_for_removal`: Before the program made from `root` removes it (remove_source): write down the files it may remove there, the source's own (source_files), so a folder that was not...
- `zip_source`: Pack the source in `root` (source_files, with its folders, under one folder named like `root`) into a zip in `folder`, never over a file there ("name (2).zip", ...).
- `move_save`: Move a save file (with its -wal / -shm, its .bak backups and the log beside it) into `folder`, never over a file already there (then it is saved as tierlist-2.db, ...).
- `remove_source`: Remove an unpacked source folder (T-12), run by the new program as it starts (the old one may still be closing: on Windows a folder in use cannot be removed, so it...
- `default_source_folder`: Where the source goes unless you pick another folder: beside the program, in "Word Tierlister source".
- `existing_source`: A copy of the source the program sits beside already, or None: tierlist.py right there (it was built from that source: T-6 puts it next to tierlist.py), or a folder...
- `start_source`: Start tierlist.py in `folder` with `python` (and `args`), on its own (not a child of this program, which then closes).
- `python_for_source`: A Python on this computer to start the unpacked tierlist.py with, or None (a built program has its own Python inside, which cannot run loose source files).
- `open_folder`: Show a folder in the system's file manager.
- `version_tuple`: (1, 2, 0) for "v1.2.0" (the numbers in it, three at most).
- `read_version`: The VERSION in `root`'s src/constants.py (the source being built may be another version than this one).
- `describe_fetch_error`: Why asking GitHub failed, in a line.
- `latest_release`: The newest release on GitHub, {"version", "tag", "source" (its source as a zip), "page"}, or None when offline, GitHub cannot be reached or there is none yet.
- `newer`: True if `release` (latest_release) is a newer version than `version`.
- `fetch_source`: Download `release`'s source (GitHub's zip of the repository at its tag) into `folder`, with its manifest, ready to unpack (plan_unpack) or build from; returns `folder`.
- `running_program`: The program now running (the .exe or the Linux file; on macOS its .app), or None when running from source.
- `program_download`: {"url", "size"} of the program in `release` (latest_release) for this computer, or None (none built for it).
- `fetch_program`: Download this computer's program from `release` into `folder` (macOS: the .app out of its zip) and return its path, ready for replace_program.
- `update_folder`: A new, empty folder beside `program` to download the new one into (the same disk, so swapping it in is one move); raises OSError when the program's folder cannot be...
- `replace_program`: Put the program `new` where `current` is (the running one: Windows lets a running .exe be renamed, never overwritten), keeping the old one as current + OLD_SUFFIX...
- `remove_old_program`: As an updated program starts: remove the program it replaced (OLD_SUFFIX) and any download folder left beside it (UPDATE_DIR).
- `git_checkout`: True if `root` is a git checkout and git is installed: then an update is a git pull.
- `git_pull`: `git pull --ff-only` in `root`: (True, what git said) if it worked, else (False, why).

## Rules and pitfalls (fixed before: keep them fixed)

- The build checks PyInstaller by importing what the build uses (`PYINSTALLER_CHECK`), repairs an incomplete one, and runs pip and PyInstaller from a neutral folder (reported: "No module named PyInstaller.utils").
- The rename (Word Tier List -> Word Tierlister, after 1.0.2): every release also carries each program under its old name (`OLD_RELEASE_ASSETS`, copied by the workflow), which 1.0.2 and older look for to update; records under their old names (`OLD_RECORDS`) are still read; a build removes the old-named program beside it (`remove_renamed_program`). Keep the old asset names in every release.
- Unpacking only ever touches the program's own files (its manifest and the last unpack's record); a file you edited is kept as `.bak` first; saves, logs and `.venv` are never looked at.
- `source_files` is the one list of what ships: the zip, the program and the manifest all use it.
- No tkinter: the dialog is `sources.py`.
- Everything started from here (the other form, Python, PyInstaller, pip, the file manager) gets `clean_env()`: a built program's Tcl / Tk paths and library path point into its temporary folder, which is gone once it closes (reported: PyInstaller's "Tk data/library directory ... could not be collected!").
- Cleaning up behind (T-12): `remove_source` removes only what the unpack record lists, `OURS` and `__pycache__`, and nothing without that record; `move_save` never writes over a file. The program goes where the source was, in its folder (T-15, asked for: not the folder holding it); `remove_source` keeps a program in the folder, its build record (`SIDE_FILE`) and the log. Only a folder unpacked from a program beside it replaces that program (`cleanup_place`). `.gitignore` and `.gitattributes` are source files (`REPO_FILES`, F-24): in every download and clone, left out they kept a removed source's folder alive. Checked for real: a built program removed its source and kept itself, the save, the log and the build record. The deleting is done by the new program (`--remove-source`), never by the window running from the folder (Windows keeps it locked).
- `existing_source` decides whether the first start unpacks (T-10): tierlist.py beside the program, or any folder beside it with tierlist.py or the unpack record, counts as a copy already there.
- Moving out of the temporary folders is `shutil.move`, never `os.replace` / `os.rename`: they can be on another disk (reported: "[Errno 18] Invalid cross-device link").
- Self-update (U-1): `replace_program` renames the running program to `OLD_SUFFIX` and moves the new one in; a failed move puts the old one back. `remove_old_program` (main, frozen only) removes only `<name>.*.old` and `UPDATE_DIR` folders beside the program, retried while the old one closes. `fetch_program` refuses a download shorter than the release says (`size`). macOS unzips with `ditto` (keeps the app's links and signature).
- A build over `BIG_MB` logs its biggest parts (`biggest_parts`, from PyInstaller's PKG / PYZ tables): what else on the computer got pulled in.

## Changing it

- What ships: `SHIP_DIRS` / `source_files`. Program names: `output_name` and, for releases, `RELEASE_ASSETS` (the workflow's names must match).
- Release lookups: `latest_release` / `fetch_source` (tests pass their own `fetch`). GitHub's API answers a private repository's releases with 404 "Not Found" to anyone not signed in: `describe_fetch_error` says so (U-4); the program never signs in.
- The unpack record (`UNPACKED`) says whether the folder came from the program (`from_program`; older records: yes, `came_from_program`). Only such a folder is offered to be cleaned up behind or removed (`cleanup_place`, `remove_source`): a source only updated from GitHub (T-13, `unpack(..., from_program=False)`) could be someone's own clone (T-13).
- `give_icon` (IC-2) sets GNOME Files' custom icon on a Linux program (gio, to `deps.kept_icon`); it fails quietly where no desktop metadata service runs.
- Removing a source (T-14) only ever takes the files written down for it: the unpack record's or `REMOVE_RECORD`'s (`mark_for_removal`: `source_files`), plus OURS; a folder with neither is never touched.
