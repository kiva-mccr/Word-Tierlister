# `src/syncfiles.py`

How this save's progress travels between devices (SY-1): one gzip JSON file per device and save in the sync folder, written from a snapshot on a worker thread and folded into the save word by word (newer change wins, `Store.apply_sync`).

- **Uses:** `store`
- **Used by:** `syncdialog`
- **Tests:** `_selftest_sync`

The module docstring has the details; this page is the map.

## Public API

- `machine_id`: This computer's part of the file name: made once and kept in `data_dir` (saves.user_data_dir()).
- `save_id`: This save's part of the file name (meta sync_save_id), made the first time it is asked for.
- `device_name`: What other devices call this one ("Synced from <name>").
- `prepare_folder`: Make the folder, with a .stignore so Syncthing never copies a file still being written.
- `snapshot`: This save's progress as a sync file's contents, read through a connection of its own (a worker thread may call it while the window keeps the save open: WAL lets it...
- `write_file`: Write the sync file whole and then put it in place (never half a file in the folder).
- `read_file`: Another device's sync file: its contents, checked.
- `trim`: Leave out what was folded in from this device before (on a worker thread): its words changed no later than the newest one taken from it last time (they were weighed...
- `apply`: Fold a read (and trimmed) sync file into the save, on the window's thread, a step at a time: yields each step's Store.apply_sync counts (the words in steps of...
- `other_files`: {path: (modified, size)} for the other devices' sync files in the folder (not this computer's, not Syncthing's conflict copies or temporary files).

## Rules and pitfalls (fixed before: keep them fixed)

- Each device writes only its own file (`<machine>-<save>.wtsync`), so Syncthing never sees two devices change one file; files whose name starts with this computer's id are never read back.
- A file is written whole beside the folder's others (`.~name.tmp`, left alone by `.stignore`) and then put in place with `os.replace`.
- `snapshot` reads through a read-only connection of its own (a worker thread); only `apply` (the window's thread) writes the save.
- A second read of a device's file folds in only what changed since (`trim`, meta `sync_marks`): re-folding a 300k-word file took 0.6 s on the window's thread each time. The first sync of a big save goes in steps of `CHUNK` words (`apply` yields; 8 s at once on a 1M save froze the window).
- `read_file` refuses a newer `FORMAT`: bump it when the file's shape changes, and keep reading the old one.

## Changing it

- What a file holds: `Store.sync_rows` (written) and `Store.apply_sync` (read); the merge rules live in the Store.
