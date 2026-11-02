"""File > Sync with other devices (SY-1): link devices through Syncthing, and keep the save in step with theirs.

SyncDialog: installs Syncthing if it is missing (the system's package manager, as the install window does), starts
it, shares the sync folder, and links devices: this device's code to copy, a box to paste the other's, requests to
accept, devices found on this network, the linked devices with whether each is connected now, the "Sync
automatically" tick (on to start with) and what to know before relying on it (both devices on at the same time).

AutoSync: while the program runs, every few seconds it reads the other devices' sync files that changed and folds
them in (newer change wins, Store.apply_sync), and every minute or so, when something changed here, writes this
device's file (syncfiles.py). Reading and writing the files happen on a worker thread with a connection of their
own; only applying touches the save, on the window's thread, never while a long job (App.busy) writes it. Closing
the program writes the file one last time.
"""
import json
import os
import queue
import sqlite3
import threading
import time
import tkinter as tk
from tkinter import ttk

import deps
import errors
import syncfiles
import syncthing_api as st
from fonts import font
from problems import STOPPED_MESSAGE
from saves import user_data_dir
from startup import run_with_progress
from theme import PALETTE
from widgets import StyledDialog

TITLE = "Sync with other devices"
INTRO = ("Keeps your tier list the same on your other computers. It uses Syncthing, a free program that copies a "
         "folder straight between your own devices: no account and no cloud.")
# what to know before relying on it (asked for: a list of what it cannot do, then what keeps the list safe)
LIMITS = ["Both devices must be switched on, with Syncthing running, at the same time for changes to travel.",
          "Syncthing starts when you log in (if you let it), so Word Tierlister itself need not be open.",
          "On the same network devices find each other; elsewhere they meet through Syncthing's free relays.",
          "If both devices change the same word, the later change wins."]
PROTECTIONS = ["Your progress goes straight between your own devices, encrypted on the way; no account, and "
               "nothing is kept in a cloud.",
               "Only devices you link or accept can sync with this one.",
               "Each device writes only its own sync file, so no device can overwrite another's."]
AUTOSTART_HEADLINE = "Start Syncthing when you log in?"
AUTOSTART_TEXT = ("Then your devices sync whenever both are switched on, even with Word Tierlister closed. Without "
                  "it, Syncthing runs until you log out, and Word Tierlister starts it again whenever it opens.")
DOWNLOAD_PAGE = "https://syncthing.net/downloads/"


def default_folder():
    """Where the sync files live unless the save says otherwise (meta sync_folder): the user data folder's sync/."""
    return os.path.join(user_data_dir(), "sync")


def _ago(when, now=None):
    secs = max(0, (now or time.time()) - when)
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)} min ago"
    if secs < 86400:
        return f"{int(secs // 3600)} h ago"
    return time.strftime("%d %b %Y, %H:%M", time.localtime(when))


class AutoSync:
    """Keeps the save in step with the other devices' sync files while the program runs (see the module's note)."""
    FIRST_MS = 4000               # the first look, once the window is up
    CHECK_MS = 10000              # how often the folder is looked at (a few file dates: cheap)
    WRITE_GAP = 60                # seconds between writes of this device's file while something keeps changing

    def __init__(self, app, data_dir=None, start=True):
        self.app, self.store = app, app.store
        self._data_dir, self._machine = data_dir, None
        self.seen = {}            # the other files as they were when last folded in: {path: (modified, size)}
        self.written = None       # store.version when this device's file was last written
        self.wrote_at = 0.0
        self.working = False
        self.listeners = []       # called after each round (the open dialog shows when it last synced)
        if start:
            app.root.after(self.FIRST_MS, self._tick)

    @property
    def folder(self):
        return self.store.get_meta("sync_folder")

    @property
    def machine(self):
        """This computer's part of the sync file's name (read, or made, only once syncing is set up)."""
        if self._machine is None:
            self._machine = syncfiles.machine_id(self._data_dir or user_data_dir())
        return self._machine

    @property
    def auto(self):
        return self.store.get_meta("sync_auto", "1") == "1"

    def device(self):
        return f"{self.machine}-{syncfiles.save_id(self.store)}"

    started = False

    def start_syncthing(self, connect=None):
        """Once, when syncing is set up: start Syncthing if it is not running (it was not let start at log-in, or
        was stopped), on a worker thread; nothing is said if it cannot be."""
        self.started = True

        def work():
            try:
                (connect or st.connect)()
            except (st.SyncthingError, OSError):
                pass
        threading.Thread(target=work, daemon=True).start()

    def _tick(self):
        if getattr(self.app, "shut", False) or self.store.closed:
            return
        try:
            if self.folder and not self.started:
                self.start_syncthing()
            if self.folder and self.auto:
                self.sync()
        finally:
            self.app.root.after(self.CHECK_MS, self._tick)

    def sync(self, force=False, then=None):
        """One round: write this device's file if it changed (at most every WRITE_GAP seconds, unless `force`), read
        the other files that changed, and fold them in. Returns False when there was nothing to do (or a round or a
        long job is running). `then()` runs after the round."""
        folder, store = self.folder, self.store
        if not folder or self.working or self.app.busy or store.closed:
            return False
        write = self.written != store.version and (force or time.time() - self.wrote_at >= self.WRITE_GAP)
        theirs = {p: v for p, v in syncfiles.other_files(folder, self.machine).items() if self.seen.get(p) != v}
        if not write and not theirs:
            if then:
                then()
            return False
        self.working = True
        version, device, path = store.version, self.device(), store.path
        try:
            marks = json.loads(store.get_meta("sync_marks", "") or "{}")
        except ValueError:
            marks = {}
        out = queue.Queue()

        def work():
            got = {"wrote": False, "files": [], "errors": [], "bad": {}}
            try:
                files(got)
            except Exception as exc:                 # (anything else: said, and the round still ends)
                got["errors"].append(f"Syncing stopped: {exc!r}")
            out.put(got)

        def files(got):
            if write:
                try:
                    syncfiles.write_file(folder, device + syncfiles.SUFFIX, syncfiles.snapshot(path, device))
                    got["wrote"] = True
                except (OSError, sqlite3.Error) as exc:
                    got["errors"].append(f"This device's sync file could not be written ({exc})")
            for p, v in theirs.items():
                try:
                    data, mark = syncfiles.trim(syncfiles.read_file(p), marks)
                    got["files"].append((p, v, data, mark))
                except ValueError as exc:            # (said once, not at every look: until the file changes)
                    got["errors"].append(f"{os.path.basename(p)}: {exc}")
                    got["bad"][p] = v
        threading.Thread(target=work, daemon=True).start()
        self._collect(out, version, then)
        return True

    def _collect(self, out, version, then):
        try:
            got = out.get_nowait()
        except queue.Empty:
            self.app.root.after(100, lambda: self._collect(out, version, then))
            return
        if getattr(self.app, "shut", False) or self.store.closed:
            return
        if got["wrote"]:
            self.written, self.wrote_at = version, time.time()
        self.seen.update(got["bad"])
        files = [f for f in got["files"] if not f[2]["device"].startswith(self.machine + "-")]
        self.seen.update((p, v) for p, v, data, _ in got["files"] if data["device"].startswith(self.machine + "-"))
        self._fold(files, got, {"words": 0, "names": []}, None, then)

    def _fold(self, files, got, total, steps, then):
        """Fold the files in a step at a time (syncfiles.apply), letting the window run between steps (the first
        sync of a big save is hundreds of thousands of words); then say what came."""
        if getattr(self.app, "shut", False) or self.store.closed:
            return
        if self.app.busy:                                  # (a long job writes the save: carry on afterwards)
            self.app.root.after(500, lambda: self._fold(files, got, total, steps, then))
            return
        while files:
            p, v, data, mark = files[0]
            steps = steps or syncfiles.apply(self.store, data)
            try:
                res = next(steps)
            except StopIteration:                          # (that file done: remember how far it was taken)
                try:
                    marks = json.loads(self.store.get_meta("sync_marks", "") or "{}")
                except ValueError:
                    marks = {}
                marks[data["device"]] = mark
                self.store.set_meta("sync_marks", json.dumps(marks))
                self.seen[p] = v
                files.pop(0)
                steps = None
                continue
            except sqlite3.Error as exc:
                got["errors"].append(f"{data['name']}: could not be folded in ({exc})")
                files.pop(0)
                steps = None
                continue
            if res["words"] or res["anchors"]:
                total["words"] += res["words"]
                total["names"].append(data["name"])
            self.app.root.after(1, lambda s=steps: self._fold(files, got, total, s, then))
            return
        self.working = False
        words, names = total["words"], total["names"]
        if got["files"] or got["wrote"] or got["errors"]:
            self.store.set_meta("sync_last", json.dumps({"when": time.time(), "from": sorted(set(names)),
                                                         "errors": got["errors"][-3:]}))
        if words or names:
            self.app.after_external_change()
            what = f"{words:,} word{'s' if words != 1 else ''}" if words else "the anchors"
            self.app.flash(f"Synced {what} from {', '.join(sorted(set(names)))}", kind="info")
        for f in list(self.listeners):
            f()
        if then:
            then()

    def flush(self):
        """Closing: write this device's file one last time if anything changed since (on this thread: quick, and
        the save is about to close)."""
        if self.store.closed or not self.folder or self.written == self.store.version:
            return
        try:
            device = self.device()
            syncfiles.write_file(self.folder, device + syncfiles.SUFFIX, syncfiles.snapshot(self.store.path, device))
            self.written = self.store.version
        except (OSError, sqlite3.Error):
            pass

    def last(self):
        """What the dialog says about the last round: "Last synced 3 min ago (from laptop)" or None."""
        try:
            got = json.loads(self.store.get_meta("sync_last", "") or "{}")
        except ValueError:
            return None
        if not got.get("when"):
            return None
        text = f"Last synced {_ago(got['when'])}"
        if got.get("from"):
            text += f", with changes from {', '.join(sorted(set(got['from'])))}"
        if got.get("errors"):
            text += ".\n" + got["errors"][-1]
        return text


class SyncDialog:
    """File > Sync with other devices (see the module's note). `find() -> path or None`, `connect(exe) -> Client` and
    `autostart(exe)`: how Syncthing is found, reached and set to start at log-in (tests pass fakes)."""
    REFRESH_MS = 3000

    def __init__(self, app, find=None, connect=None, autostart=None, show=True):
        self.app, self.store = app, app.store
        self.find = find or st.find_syncthing
        self.connect = connect or st.connect
        self.autostart = autostart or st.start_at_login
        self.client = None
        self.my_id = ""
        self.shown = None          # what the lists show now, to redraw them only when it changes
        self.dlg = None
        exe = self.find()
        if not exe:                                        # (asked for: ask to install it first, then open)
            self.offer_install()
            return
        if self.store.get_meta("sync_autostart") is None:  # (asked for: asked once, at the start; no tick box)
            yes = errors.ask_yes_no(TITLE, AUTOSTART_HEADLINE, AUTOSTART_TEXT, yes="Start at log-in",
                                    no="Not at log-in", parent=app.root, wrap_chars=56)
            self.store.set_meta("sync_autostart", "yes" if yes else "0")
        # (asked for: landscape. Left, what syncing is and what to know; right, this device and its links)
        self.dlg = dlg = StyledDialog(app.root, TITLE, animator=app.anim, wrap_chars=48)
        self.left = tk.Frame(dlg.body, bg=PALETTE["bg"])
        self.left.pack(side="left", anchor="n", fill="y")
        tk.Frame(dlg.body, bg=PALETTE["border"], width=1).pack(side="left", fill="y", padx=26)
        self.area = tk.Frame(dlg.body, bg=PALETTE["bg"])
        self.area.pack(side="left", anchor="n", fill="y")
        self._good_to_know()
        dlg.button("Close", dlg.close, default=True)
        self._start(exe)
        if show:
            dlg.show()

    def _good_to_know(self):
        """The limits, then the protections, a line each."""
        left = self.left
        tk.Label(left, text=TITLE, font=font("head"), bg=PALETTE["bg"], fg=PALETTE["text"]).pack(anchor="w")
        self.dlg.text(INTRO, muted=True, parent=left, pady=(8, 0))
        self._heading("Good to know", parent=left)
        for title, lines in (("What it needs", LIMITS), ("What keeps your list safe", PROTECTIONS)):
            ttk.Label(left, text=title, font=font("body")).pack(anchor="w", pady=(6, 2))
            for line in lines:
                self.dlg.text("\u2022  " + line, muted=True, parent=left, room=24, padx=(12, 0))

    # ---- small helpers ----------------------------------------------------------------------------------------
    def _clear(self):
        for w in self.area.winfo_children():
            w.destroy()
        for name in [n for n, b in self.dlg.buttons.items() if not b.winfo_exists()]:
            del self.dlg.buttons[name]

    def _heading(self, text, parent=None, top=16):
        ttk.Label(parent or self.area, text=text, font=font("head")).pack(anchor="w", pady=(top, 4))

    def _row(self, parent=None, top=6):
        row = tk.Frame(parent or self.area, bg=PALETTE["bg"])
        row.pack(anchor="w", fill="x", pady=(top, 0))
        return row

    def _background(self, fn, done):
        """Run `fn` on a worker thread (Syncthing's answers take a moment); `done(ok, value or message)` on this
        thread, if the dialog is still open."""
        out = queue.Queue()

        def work():
            try:
                out.put((True, fn()))
            except (st.SyncthingError, OSError) as exc:
                out.put((False, str(exc)))
        threading.Thread(target=work, daemon=True).start()

        def poll():
            if not self.dlg.alive():
                return
            try:
                ok, value = out.get_nowait()
            except queue.Empty:
                self.dlg.win.after(100, poll)
                return
            done(ok, value)
        poll()

    # ---- Syncthing missing ------------------------------------------------------------------------------------
    def offer_install(self):
        """Syncthing is not installed: ask to install it first (then this window opens), or, with nothing to install
        it with here, offer its download page."""
        cmd = deps.system_install_command("syncthing", window=True)
        size = deps.SIZE.get("syncthing")
        why = (f"Syncing uses Syncthing, a free program that copies a folder straight between your own devices "
               f"(about {size} MB).")
        if cmd:
            if errors.ask_yes_no(TITLE, "Install Syncthing first?", f"{why} It can be installed with:\n    "
                                 f"{' '.join(cmd)}\n\nYour system may ask for your password.", yes="Install it",
                                 no="Not now", parent=self.app.root, wrap_chars=56):
                return self.install(cmd)
        elif errors.ask_yes_no(TITLE, "Get Syncthing first?", f"{why} Install it from its page, then open "
                               "File > Sync with other devices again.", yes="Open its page", no="Not now",
                               parent=self.app.root, wrap_chars=56):
            errors.open_link(DOWNLOAD_PAGE)
        return None

    def install(self, cmd, runner=None):
        """"Install it": behind the progress window; then the sync window opens."""
        app = self.app
        try:
            ok = run_with_progress(app.root, lambda log: (runner or deps.run_system_install)(cmd, log),
                                   title="Installing Syncthing", initial_stage="Installing...",
                                   intro="Your system may ask for your password.")
        except SystemExit as exc:                          # (the progress window was closed: stopped)
            if str(exc) != STOPPED_MESSAGE:
                raise
            ok = False
        if not ok or not self.find():
            errors.show_error(TITLE, "Syncthing could not be installed. You can get it from "
                              f"{DOWNLOAD_PAGE} and then open File > Sync with other devices again.", parent=app.root,
                              headline="Not installed")
            return None
        return SyncDialog(app, self.find, self.connect, self.autostart)

    # ---- starting it ------------------------------------------------------------------------------------------
    def _start(self, exe):
        self._clear()
        self.status = self.dlg.text("Starting Syncthing...", parent=self.area)
        folder = self.store.get_meta("sync_folder") or default_folder()
        autostart = self.store.get_meta("sync_autostart") == "yes"      # (said yes, not done yet)

        def work():
            client = self.connect(exe)
            syncfiles.prepare_folder(folder)
            client.ensure_folder(folder)
            told = None
            if autostart:
                try:
                    self.autostart(exe)
                    told = True
                except OSError as exc:
                    told = str(exc)
            return client, client.my_id(), told
        self._background(work, lambda ok, got: self._started(ok, got, folder))

    def _started(self, ok, got, folder):
        if not ok:
            self.status.config(text=f"{got}\nSyncthing is installed but could not be reached; try again in a "
                                    "moment.")
            self.dlg.refit()
            return
        self.client, self.my_id, told = got
        self.store.set_meta("sync_folder", folder)
        if told is True:
            self.store.set_meta("sync_autostart", "1")
        self._linked_page(None if told in (None, True) else told)
        self.refresh()

    # ---- linking ----------------------------------------------------------------------------------------------
    def _linked_page(self, autostart_problem=None):
        """The right side (asked for): the devices wanting to sync first and large, then the linked devices and
        syncing, and at the bottom, small, linking by code."""
        self._clear()
        dlg, area = self.dlg, self.area
        self._heading("Devices that want to sync", top=0)
        self.requests = tk.Frame(area, bg=PALETTE["bg"])
        self.requests.pack(anchor="w", fill="x")
        self.link_msg = dlg.text("", parent=area, muted=True)

        self._heading("Linked devices")
        self.devices = tk.Frame(area, bg=PALETTE["bg"])
        self.devices.pack(anchor="w", fill="x")
        self.auto_var = tk.BooleanVar(value=self.store.get_meta("sync_auto", "1") == "1")
        ttk.Checkbutton(area, text="Sync automatically", variable=self.auto_var, command=self.toggle_auto,
                        takefocus=1).pack(anchor="w", pady=(14, 0))
        row = self._row(top=8)
        self.last = ttk.Label(row, text="", foreground=PALETTE["muted"], wraplength=dlg.wrap - 140,
                              justify="left")
        self.last.pack(side="left")
        dlg.button("Sync now", self.sync_now, row=row)
        self._code_section()
        if autostart_problem:
            dlg.text(f"Syncthing could not be set to start at log-in ({autostart_problem}); it runs until you log "
                     "out.", parent=area, muted=True, pady=(8, 0))
        sync = getattr(self.app, "autosync", None)
        if sync is not None:
            sync.listeners.append(self.show_last)
            self.dlg.win.bind("<Destroy>", lambda e: self._forget_listener(e, sync), add="+")
        self.show_last()
        dlg.refit()

    def _code_section(self):
        """Linking by hand, small: this device's code to copy, the other's to paste (when it is not found nearby)."""
        dlg, area, small = self.dlg, self.area, font("small")
        tk.Frame(area, bg=PALETTE["border"], height=1).pack(fill="x", pady=(18, 10))
        ttk.Label(area, text="Link by code (when the other device is not listed above)", font=small,
                  foreground=PALETTE["muted"]).pack(anchor="w")
        self.code = tk.StringVar(value=self.my_id)
        self.paste = tk.StringVar()
        width = len(self.my_id) + 1
        for label, var, button, command in (("This device", self.code, "Copy", self.copy),
                                            ("Other device", self.paste, "Link", self.link_pasted)):
            row = self._row(top=4)
            ttk.Label(row, text=label, font=small, width=12).pack(side="left")
            entry = ttk.Entry(row, textvariable=var, width=width, font=small,
                              state="readonly" if var is self.code else "normal")
            entry.pack(side="left")
            dlg.button(button, command, row=row).config(font=small)
            if var is self.paste:
                entry.bind("<Return>", lambda e: (self.link_pasted(), "break")[1])
            else:
                self.copied = ttk.Label(row, text="", font=small, foreground=PALETTE["muted"])
                self.copied.pack(side="left", padx=(8, 0))

    def _forget_listener(self, event, sync):
        if event.widget is self.dlg.win and self.show_last in sync.listeners:
            sync.listeners.remove(self.show_last)

    def copy(self):
        self.dlg.win.clipboard_clear()
        self.dlg.win.clipboard_append(self.my_id)
        self.copied.config(text="Copied")

    def link_pasted(self):
        text = self.paste.get()
        if not st.clean_id(text):
            self.link_msg.config(text="That is not a device code: it is eight groups of seven letters and digits, "
                                      "shown on the other device.")
            self.dlg.refit()
            return
        self.link(text)

    def link(self, device_id, name=""):
        """Link a device (or accept its request) on a worker thread; the lists show it once Syncthing has it."""
        self.link_msg.config(text="Linking...")

        def done(ok, value):
            if ok:
                self.paste.set("")
                self.link_msg.config(text=f"Linked {name or st.short_id(value)}. It syncs once that device has "
                                          "accepted (or linked this one).")
            else:
                self.link_msg.config(text=value)
            self.dlg.refit()
            self.refresh()
        self._background(lambda: self.client.link(device_id, name), done)

    def unlink(self, device):
        if not errors.ask_yes_no(TITLE, f"Stop syncing with {device['name']}?",
                                 "Your tier list stays as it is on both devices; they just stop exchanging changes. "
                                 "You can link them again any time.", yes="Stop syncing", no="Cancel",
                                 parent=self.dlg.win):
            return
        self._background(lambda: self.client.unlink(device["id"]), lambda ok, v: self.refresh())

    def dismiss(self, device):
        self._background(lambda: self.client.dismiss(device["id"]), lambda ok, v: self.refresh())

    def refresh(self):
        """Ask Syncthing for the devices again (every few seconds while open)."""
        if self.client is None or not self.dlg.alive():
            return
        c = self.client
        self._background(lambda: (c.devices(), c.pending_devices(), c.nearby_devices()), self._show_lists)

    def _show_lists(self, ok, got):
        if ok:
            linked, pending, nearby = got
            state = (tuple((d["id"], d["name"], d["connected"]) for d in linked),
                     tuple((d["id"], d["name"]) for d in pending), tuple(nearby))
            if state != self.shown:
                self.shown = state
                self._draw_lists(linked, pending, nearby)
        self.dlg.win.after(self.REFRESH_MS, self.refresh)

    def _draw_lists(self, linked, pending, nearby):
        dlg = self.dlg
        for frame in (self.requests, self.devices):
            for w in frame.winfo_children():
                w.destroy()
        for name in [n for n, b in dlg.buttons.items() if not b.winfo_exists()]:
            del dlg.buttons[name]
        def asking(name, note, top):
            row = self._row(self.requests, top=top)
            words = tk.Frame(row, bg=PALETTE["bg"])
            words.pack(side="left", anchor="w")
            tk.Label(words, text=name, font=font("title"), bg=PALETTE["bg"], fg=PALETTE["text"]).pack(anchor="w")
            ttk.Label(words, text=note, foreground=PALETTE["muted"]).pack(anchor="w")
            buttons = tk.Frame(row, bg=PALETTE["bg"])
            buttons.pack(side="right", padx=(24, 0))
            return buttons
        for i, d in enumerate(pending):
            row = asking(d["name"], f"wants to sync with this device  ·  code {st.short_id(d['id'])}", 4 if i else 0)
            # (the dialog keeps its buttons by name: each device's own, shown with the plain word)
            dlg.button(f"Not now {d['id']}", lambda d=d: self.dismiss(d), row=row).config(text="Not now")
            dlg.button(f"Accept {d['id']}", lambda d=d: self.link(d["id"], d["name"]), row=row).config(
                text="Accept", bg=PALETTE["select_bg"])
        for i, did in enumerate(nearby):
            row = asking(f"Device {st.short_id(did)}", "on this network  ·  link it if its code starts the same",
                         4 if i or pending else 0)
            dlg.button(f"Link {did}", lambda did=did: self.link(did), row=row).config(text="Link",
                                                                                      bg=PALETTE["select_bg"])
        if not pending and not nearby:
            dlg.text("None right now. Open File > Sync with other devices on the other device: it shows up here.",
                     parent=self.requests, muted=True)
        if not linked:
            dlg.text("None yet.", parent=self.devices, muted=True)
        for d in linked:
            row = self._row(self.devices, top=4)
            state = "connected" if d["connected"] else "not connected now"
            dlg.text(f"{d['name']} ({st.short_id(d['id'])}): {state}", parent=row, side="left", room=140)
            dlg.button(f"Unlink {d['id']}", lambda d=d: self.unlink(d), row=row).config(text="Unlink")
        dlg.refit()

    # ---- syncing ----------------------------------------------------------------------------------------------
    def toggle_auto(self):
        self.store.set_meta("sync_auto", "1" if self.auto_var.get() else "0")
        self.show_last()

    def sync_now(self):
        sync = getattr(self.app, "autosync", None)
        if sync is None:
            return
        self.last.config(text="Syncing...")
        if self.client is not None:
            self._background(self.client.rescan, lambda ok, v: None)
        if not sync.sync(force=True, then=self.show_last):
            self.show_last()

    def show_last(self):
        if not self.dlg.alive() or not hasattr(self, "last"):
            return
        sync = getattr(self.app, "autosync", None)
        text = (sync.last() if sync else None) or "Not synced yet."
        if not self.auto_var.get():
            text += "\nAutomatic syncing is off: only Sync now exchanges changes."
        self.last.config(text=text)
        self.dlg.refit()
