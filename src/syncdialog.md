# `src/syncdialog.py`

File > Sync with other devices (SY-1): install and start Syncthing, this device's code, link / accept / unlink devices, the Sync automatically tick (on to start with) and the warning that both devices must be on at the same time; and `AutoSync`, which folds the other devices' files in and writes this one's while the program runs.

- **Uses:** `deps`, `errors`, `fonts`, `problems`, `saves`, `startup`, `syncfiles`, `syncthing_api`, `theme`, `widgets`
- **Used by:** `app`
- **Tests:** none of its own

The module docstring has the details; this page is the map.

## Public API

- `default_folder`: Where the sync files live unless the save says otherwise (meta sync_folder): the user data folder's sync/.
- `AutoSync`: Keeps the save in step with the other devices' sync files while the program runs (see the module's note).
  - methods: folder, machine, auto, device, sync, flush, last
- `SyncDialog`: File > Sync with other devices (see the module's note).
  - methods: install, copy, link_pasted, link, unlink, dismiss, refresh, toggle_auto, sync_now, show_last

## Rules and pitfalls (fixed before: keep them fixed)

- Every Syncthing call runs on a worker thread (`_background`); the dialog never waits on the network.
- AutoSync reads and writes files on a worker thread and applies them on the window's thread, never while `App.busy` (a reshuffle writes the save); closing writes the file one last time (`App.on_close` -> `flush`).
- This device's file is written at most every `WRITE_GAP` seconds while things change (a 1M save's file is several MB), at once for Sync now and at closing.
- The dialog's buttons are kept by name (`StyledDialog.buttons`): each device's Accept / Unlink is named with its id and shown with the plain word.

## Changing it

- The warning's words: `GOOD_TO_KNOW`. How often it looks: `AutoSync.CHECK_MS`, `WRITE_GAP`.
