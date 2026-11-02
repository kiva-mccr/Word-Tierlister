"""Sync files (SY-1): how this save's progress travels to other devices through a shared folder.

Each device writes one file of its own into the folder (Syncthing keeps the folder the same on every linked device,
syncthing_api.py), so two devices never write the same file and nothing conflicts. A file holds that device's whole
progress: every word with a tier, skips or a change since syncing came, with the time it last changed; the anchors
and when they changed; the duels made there. Reading another device's file folds it in (Store.apply_sync): the
newer change of each word wins, so working on two devices in turn, or on both while apart, merges cleanly.

A file is gzip-compressed JSON named <this computer>-<this save>.wtsync. The computer's part is kept in the user
data folder (machine_id), the save's in the save (save_id): a save copied to another computer, or a second save on
this one, gets a name of its own, and files from this computer are never read back in.

Nothing here touches tkinter; snapshot() and read_file() run on worker threads (snapshot reads through a
connection of its own), Store.apply_sync on the window's thread.
"""
import gzip
import json
import os
import socket
import sqlite3
import time
import uuid
from pathlib import Path

from store import Store

SUFFIX = ".wtsync"
FORMAT = 1
PROGRAM = "Word Tierlister"
IGNORE = "*.tmp\n.~*\n"          # (.stignore: Syncthing leaves a file being written alone)


def machine_id(data_dir):
    """This computer's part of the file name: made once and kept in `data_dir` (saves.user_data_dir())."""
    path = os.path.join(data_dir, "sync-device-id")
    try:
        with open(path, encoding="utf-8") as f:
            got = f.read().strip()
        if got:
            return got
    except OSError:
        pass
    got = uuid.uuid4().hex[:12]
    os.makedirs(data_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(got + "\n")
    return got


def save_id(store):
    """This save's part of the file name (meta sync_save_id), made the first time it is asked for."""
    got = store.get_meta("sync_save_id")
    if not got:
        got = uuid.uuid4().hex[:8]
        store.set_meta("sync_save_id", got)
    return got


def device_name():
    """What other devices call this one ("Synced from <name>")."""
    return socket.gethostname() or "another device"


def prepare_folder(folder):
    """Make the folder, with a .stignore so Syncthing never copies a file still being written."""
    os.makedirs(folder, exist_ok=True)
    ignore = os.path.join(folder, ".stignore")
    if not os.path.exists(ignore):
        with open(ignore, "w", encoding="utf-8") as f:
            f.write(IGNORE)


def snapshot(save_path, device, name=None):
    """This save's progress as a sync file's contents, read through a connection of its own (a worker thread may
    call it while the window keeps the save open: WAL lets it read a consistent copy)."""
    con = sqlite3.connect(Path(os.path.abspath(save_path)).as_uri() + "?mode=ro", uri=True, timeout=10)
    try:
        rows, anchors, when, comps = Store.sync_rows(con)
    finally:
        con.close()
    return {"format": FORMAT, "program": PROGRAM, "device": device, "name": name or device_name(),
            "written": time.time(), "words": rows, "anchors": anchors, "anchors_changed": when, "comparisons": comps}


def write_file(folder, name, payload):
    """Write the sync file whole and then put it in place (never half a file in the folder)."""
    prepare_folder(folder)
    path = os.path.join(folder, name)
    tmp = os.path.join(folder, f".~{name}.tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as f:
        json.dump(payload, f, separators=(",", ":"))
    os.replace(tmp, path)
    return path


def read_file(path):
    """Another device's sync file: its contents, checked. ValueError if it is not one this version can read."""
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, EOFError, ValueError) as exc:
        raise ValueError(f"not a readable sync file ({exc})") from None
    if not isinstance(data, dict) or data.get("program") != PROGRAM:
        raise ValueError("not a Word Tierlister sync file")
    if data.get("format", 0) > FORMAT:
        raise ValueError("made by a newer version of Word Tierlister: update this one to read it")
    words = data.get("words") or []
    if not isinstance(words, list) or any(not isinstance(r, list) or len(r) != 6 for r in words):
        raise ValueError("its word list is damaged")
    comps = [c for c in data.get("comparisons") or [] if isinstance(c, list) and len(c) == 5]
    anchors = data.get("anchors")
    return {"device": str(data.get("device") or ""), "name": str(data.get("name") or "another device"),
            "written": float(data.get("written") or 0), "words": words, "comparisons": comps,
            "anchors": anchors if isinstance(anchors, list) else None,
            "anchors_changed": float(data.get("anchors_changed") or 0)}


def apply(store, data):
    """Fold a read sync file into the save (the window's thread). Returns Store.apply_sync's counts."""
    return store.apply_sync(data["device"] or "?", data["words"], data["anchors"], data["anchors_changed"],
                            data["comparisons"])


def other_files(folder, machine):
    """{path: (modified, size)} for the other devices' sync files in the folder (not this computer's, not
    Syncthing's conflict copies or temporary files)."""
    found = {}
    try:
        names = os.listdir(folder)
    except OSError:
        return found
    for n in names:
        if not n.endswith(SUFFIX) or n.startswith((machine + "-", ".")) or ".sync-conflict-" in n:
            continue
        p = os.path.join(folder, n)
        try:
            st = os.stat(p)
        except OSError:
            continue
        found[p] = (st.st_mtime, st.st_size)
    return found
