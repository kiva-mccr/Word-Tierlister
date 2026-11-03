# `src/syncthing_api.py`

Syncthing (SY-1): finding it, starting it in the background and at every log-in, and its local web API for linking devices and sharing the sync folder (folder id `word-tierlister`).

- **Uses:** `deps`
- **Used by:** `startup`, `syncdialog`
- **Tests:** `_selftest_sync`

The module docstring has the details; this page is the map.

## Public API

- `SyncthingError`: Syncthing could not be reached, or refused a change (the message says which, in words).
- `find_syncthing`: The Syncthing program's path, or None when it is not installed.
- `version`: Syncthing's version as a tuple (1, 27, 2), or (0,) when it cannot be told.
- `serve_args`: The command that runs Syncthing in the background: no browser opening, no console (Windows).
- `config_path`: Where Syncthing keeps its config.xml: what `syncthing --paths` says (1.21 and later), else the usual place, the first one that exists (or the first, for a Syncthing...
- `read_gui`: (the API's address, its key) from Syncthing's config.xml, or None while it has none.
- `clean_id`: A device ID as typed or pasted: capitals, dashes in place, spaces and line breaks gone.
- `short_id`: The first group of a device ID: what Syncthing itself shows to tell devices apart.
- `Client`: Syncthing's local API (REST): every call sends the key; an https API's own certificate is accepted, since the address is this computer's.
  - methods: call, get, ping, my_id, devices, pending_devices, nearby_devices, folder, up_to_date, ensure_folder, link, unlink, dismiss, rescan
- `start`: Start Syncthing in the background, on its own (it keeps running when Word Tierlister closes).
- `connect`: A Client for this computer's Syncthing, started first if it is not running (`start_it`).
- `autostart_path`: Where the start-at-log-in entry goes when there is no service to enable: Linux's autostart folder, the Windows Startup folder, macOS's LaunchAgents.
- `start_at_login`: Make Syncthing start at every log-in (asked for: sync should not wait for Word Tierlister to be open).

## Rules and pitfalls (fixed before: keep them fixed)

- It uses the computer's usual Syncthing (its config.xml, found with `syncthing --paths`), never a private copy: the user's own Syncthing and ours would fight over the same ports.
- Never set `autoAcceptFolders` on a linked device (S-3): it lets that device make any folder on this computer unasked. Both devices share `FOLDER_ID` themselves, which is all syncing needs (tried with two real Syncthings); `ensure_folder` turns it off on devices linked by 1.0.3 and older.
- Starting it sets `STNODEFAULTFOLDER=1`, or its first start makes a ~/Sync folder nobody asked for.
- Before Syncthing 1.19 there is no `serve` and the options have one dash (`serve_args`); Ubuntu 22.04 ships 1.18.
- Changes go through `GET` then `PUT` of the whole object (folder, device), starting from `/rest/config/defaults/...` for a new one: a partial object would reset the rest.
- `unlink` only forgets a device that shares nothing else with this one: the user's other Syncthing folders are theirs.
- Tried against two real Syncthing 1.27 instances here (link, accept the pending request, a file synced); the Windows Startup shortcut and the macOS LaunchAgent were never run.

## Changing it

- Install commands: `deps.SYSTEM_PACKAGES` / `system_install_command("syncthing")`. Where it is looked for: `find_syncthing`.
