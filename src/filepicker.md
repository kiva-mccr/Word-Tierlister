# `src/filepicker.py`

Choosing files for Import and Export in the app's own style on Linux (UI-42); Windows and macOS keep their system dialogs (`use_themed`).

- **Uses:** `errors`, `fonts`, `saves`, `theme`, `widgets`
- **Used by:** `app`, `sources`
- **Tests:** `_selftest_filepicker`

The module docstring has the details; this page is the map.

## Public API

- `use_themed`: True where this module's dialogs are used: X11 (Linux).
- `human_size`: A file size for the list: "1.2 MB".
- `short_date`: 'today 14:02', '12 Oct', or '12 Oct 2023' for another year.
- `places`: [(icon, label, folder)] that exist: Home, Desktop, Documents, Downloads, and the save's own folder.
- `list_folder`: Rows for a FileList: the folders (not hidden) and the files with these extensions, each sorted by name.
- `path_steps`: [(label, path)] from the top down: '/' (or the drive), then each folder.
- `found_files`: What Import offers straight away: other saves with progress, and exports named like a tier list, in the usual places; newest first.
- `FolderBrowser`: Browse folders to pick a file (mode "file": one with `exts`) or a folder (mode "folder").
  - methods: go, up
- `browse`: Open a FolderBrowser and wait; the chosen path, or None.
- `ImportDialog`: What can be imported, found in the usual places, with "Look somewhere else..." for anything else.
  - methods: look_elsewhere
- `ask_import`: The Import picker (Linux): waits, then returns the chosen file or None.
- `ExportDialog`: A name, a format and a folder; "Change folder..." to pick another folder.
  - methods: set_kind, change_folder, path, export
- `ask_export`: The Export picker (Linux): waits, then returns (the chosen path or None, its kind, its folder).

## Rules and pitfalls (fixed before: keep them fixed)

- Each dialog keeps `.result` so tests can drive it; the `ask_*` helpers wait.
