# `src/syncdialog.py`

File > Sync with other devices (SY-1): install and start Syncthing, this device's code, link / accept / unlink devices, the Sync automatically tick (on to start with) and the warning that both devices must be on at the same time; and `AutoSync`, which folds the other devices' files in and writes this one's while the program runs.

- **Uses:** `deps`, `errors`, `fonts`, `problems`, `saves`, `startup`, `syncfiles`, `syncthing_api`, `theme`, `widgets`
- **Used by:** `app`
- **Tests:** `_selftest_sync`

The module docstring has the details; this page is the map.

## Public API

- `default_folder`: Where the sync files live unless the save says otherwise (meta sync_folder): the user data folder's sync/.
- `AutoSync`: Keeps the save in step with the other devices' sync files while the program runs (see the module's note).
  - methods: folder, machine, auto, device, start_syncthing, sync, confirm, flush, last
- `SyncDialog`: File > Sync with other devices (see the module's note).
  - methods: offer_install, install, toggle_code, copy, link_pasted, link, unlink, dismiss, refresh, toggle_auto, sync_now, show_last

## Rules and pitfalls (fixed before: keep them fixed)

- Every Syncthing call runs on a worker thread (`_background`); the dialog never waits on the network.
- AutoSync reads and writes files on a worker thread and applies them on the window's thread, never while `App.busy` (a reshuffle writes the save); closing writes the file one last time (`App.on_close` -> `flush`).
- Test the window shown (as the program does), never built and kept hidden (`show=False`): on macOS Tk then never runs out of events and `update()` never returns (GitHub's Macs, T-18).
- This device's file is written at most every `WRITE_GAP` seconds while things change (a 1M save's file is several MB), at once for Sync now and at closing.
- Only another device's answer is a sync (SY-2, reported: writing this device's own file showed "Last synced" with nothing ever received): its file read here, or `Client.up_to_date` (Syncthing: a connected device has it all, the folder idle). `sync_last` keeps `when` and `with`; a note without `with` (older saves) reads as never synced.
- The device code is hidden (`HIDDEN_CHAR`) until the eye inside its box is clicked (`toggle_code`): the eye is placed in the entry, and both code boxes use `Code.TEntry` (room on the right) so they line up.
- The dialog's buttons are kept by name (`StyledDialog.buttons`): each device's Accept / Unlink is named with its id and shown with the plain word.

## Changing it

- The warning's words: `GOOD_TO_KNOW`. How often it looks: `AutoSync.CHECK_MS`, `WRITE_GAP`.
