# `src/saves.py`

Finding, choosing, remembering and exporting save files, and where a built program keeps its save (T-1), so replacing `tierlist.py` or switching to the program never loses progress.

- **Uses:** `constants`
- **Used by:** `app`, `filepicker`, `sources`, `tierlist`
- **Tests:** `_selftest_appdir`, `_selftest_tidy`

The module docstring has the details; this page is the map.

## Public API

- `is_frozen`: True when running as a built program (PyInstaller), not as tierlist.py.
- `user_data_dir`: The per-user folder for programs' data: %APPDATA% on Windows, ~/Library/Application Support on macOS, $XDG_DATA_HOME (~/.local/share) elsewhere; with this program's...
- `program_dir`: The folder a built program sits in: the executable's own, or on macOS the folder holding the .app (its executable is inside, Word Tierlister.app/Contents/MacOS/,...
- `app_dir`: Where the save, its log and exports live.
- `restart_args`: The arguments to start this program again with sys.executable: the script and its options, or just the options for a built program (its executable is the program;...
- `default_save_path`: tierlist.db next to the script, or in your home folder if that folder is read-only.
- `save_progress`: How far along a tier-list save file is, or None if `path` is not one (opened read-only).
- `find_saves`: Files that might be tier-list saves, in the places people usually keep them.
- `choose_save`: Pick the save file to open when --db is not given.
- `remember_save`: Remember which save file is in use, so a replaced or moved tierlist.py finds it again.
- `is_code_note`: True when `path` is the note beside a code file (tierlist.md beside tierlist.py, R-1's notes), which a Markdown export of the same name would overwrite (found in a...
- `write_export`: Write the tier list as .csv, .md or .txt (chosen by the extension).

## Rules and pitfalls (fixed before: keep them fixed)

- A Markdown export never overwrites a code file's note (`is_code_note`: tierlist.md beside tierlist.py is tierlist.py's note); App.export saves it as tierlist-export.md instead (F-31).
- The program was called "Word Tier List" until 1.0.2: `user_data_dir` keeps a data folder under the old name while it is the only one, and the old pointer file (~/.word_tierlist_path) is read until the new one is written. Never drop these, or an old save goes missing.
- A built program keeps its save beside itself (never in PyInstaller's temporary folder); a read-only folder falls back to the user data folder.
- The pointer file in your home folder names the save used last; a stray empty `tierlist.db` never hides the real one.

## Changing it

- Export formats: `write_export`. Where saves are looked for: `find_saves`.
