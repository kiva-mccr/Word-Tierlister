"""Choosing files for Import and Export (UI-42), in the app's own style.

Why: on Linux Tk draws its own file dialog, whose file-type drop-down flickers open and shut when its label
is clicked and whose menus grab the input and float over other programs. Windows and macOS keep their
system dialogs (use_themed() says which).

    path = ask_import(app_root, store_path, script_dir)          # None if cancelled
    path = ask_export(app_root, folder, name="tierlist", kind="txt")

Shortcuts first (C), a full browser behind them (A):
    * ImportDialog lists what it can find on this computer: other saves (with how many words they have
      placed) and exports named like a tier list, newest first; "Look somewhere else..." opens the browser.
    * ExportDialog asks only for a name, a format (Text / CSV / Markdown) and shows the folder;
      "Change folder..." opens the browser to pick another. An existing file is only replaced after asking.
    * FolderBrowser: places (Home, Desktop, Documents, Downloads, next to your save), the path as steps you
      can click, and a list of folders and the files that fit. Double-click or Enter opens a folder or picks a
      file; Backspace goes up a folder.
Each dialog is a class with .result (None until chosen) so tests can drive it; the ask_* helpers wait.
"""
import os
import time
import tkinter as tk
from tkinter import ttk

from errors import ask_yes_no
from fonts import font
from saves import find_saves, save_progress
from theme import PALETTE
from widgets import FileList, RoundButton, StyledDialog

EXPORT_KINDS = [("txt", "Text", "easy to read"), ("csv", "CSV", "for spreadsheets"), ("md", "Markdown", "for notes")]
IMPORT_EXTS = (".db", ".csv", ".txt", ".md")
FOLDER_ICON, FILE_ICON, SAVE_ICON = "folder", "file", "book"     # (smooth.ICONS: drawn, one style)


def use_themed(root):
    """True where this module's dialogs are used: X11 (Linux). Windows and macOS keep their own."""
    try:
        return root.tk.call("tk", "windowingsystem") == "x11"
    except tk.TclError:
        return False


# ---------------------------------------------------------------- small helpers
def human_size(n):
    for unit, size in (("GB", 1e9), ("MB", 1e6), ("kB", 1e3)):
        if n >= size:
            v = n / size
            return f"{v:.1f} {unit}" if v < 10 else f"{v:.0f} {unit}"
    return f"{n} B"


def short_date(t, now=None):
    """'today 14:02', '12 Oct', or '12 Oct 2023' for another year."""
    now = now or time.time()
    lt, ln = time.localtime(t), time.localtime(now)
    if lt[:3] == ln[:3]:
        return time.strftime("today %H:%M", lt)
    if lt.tm_year == ln.tm_year:
        return f"{lt.tm_mday} {time.strftime('%b', lt)}"
    return f"{lt.tm_mday} {time.strftime('%b %Y', lt)}"


def places(save_dir=None):
    """[(icon, label, folder)] that exist: Home, Desktop, Documents, Downloads, and the save's own folder."""
    home = os.path.expanduser("~")
    out = [("home", "Home", home)]
    for name in ("Desktop", "Documents", "Downloads"):
        p = os.path.join(home, name)
        if os.path.isdir(p):
            out.append((name.lower(), name, p))
    if save_dir and os.path.isdir(save_dir):
        out.append(("book", "Next to your save", save_dir))
    return out


def list_folder(folder, exts, pick_files=True):
    """Rows for a FileList: the folders (not hidden) and the files with these extensions, each sorted by name.
    With pick_files=False (choosing a folder) the files show greyed, so you can see what is already there."""
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return []
    dirs, files = [], []
    for e in entries:
        if e.name.startswith("."):
            continue
        try:
            if e.is_dir():
                dirs.append({"icon": FOLDER_ICON, "name": e.name + "/", "value": e.path, "kind": "dir"})
            elif e.name.lower().endswith(exts):
                st = e.stat()
                files.append({"icon": FILE_ICON, "name": e.name, "value": e.path, "kind": "file",
                              "info": human_size(st.st_size), "date": short_date(st.st_mtime),
                              "dim": not pick_files})
        except OSError:
            continue
    key = lambda r: r["name"].lower()
    return sorted(dirs, key=key) + sorted(files, key=key)


def path_steps(folder):
    """[(label, path)] from the top down: '/' (or the drive), then each folder. Long paths keep the start
    and the last three steps, with a step that just says '...' (it opens the folder it stands for)."""
    folder = os.path.abspath(folder)
    parts = []
    while True:
        head, tail = os.path.split(folder)
        if not tail:
            parts.append((head, head))
            break
        parts.append((tail, folder))
        folder = head
    parts.reverse()
    home = os.path.expanduser("~")
    for i, (_label, p) in enumerate(parts):          # start from "home" when inside it
        if p == home:
            parts = [("Home", home)] + parts[i + 1:]
            break
    if len(parts) > 5:
        parts = parts[:1] + [("…", parts[-4][1])] + parts[-3:]
    return parts


def found_files(script_dir, current_save, now=None):
    """What Import offers straight away: other saves with progress, and exports named like a tier list, in
    the usual places; newest first. Rows for a FileList."""
    home = os.path.expanduser("~")
    rows, seen = [], {os.path.realpath(current_save)} if current_save else set()

    def show(p):
        rel = os.path.relpath(p, home)
        return p if rel.startswith("..") else rel

    for p in find_saves(script_dir):
        if os.path.realpath(p) in seen:
            continue
        seen.add(os.path.realpath(p))
        info = save_progress(p)
        if info and info["placed"]:
            rows.append({"icon": SAVE_ICON, "name": show(p), "value": p, "kind": "file", "mtime": info["mtime"],
                         "info": f"{info['placed']:,} placed", "date": short_date(info["mtime"], now)})
    roots = [script_dir, os.path.dirname(os.path.abspath(current_save)) if current_save else None, home] + \
        [os.path.join(home, d) for d in ("Desktop", "Documents", "Downloads")]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            names = os.listdir(root)
        except OSError:
            continue
        for n in names:
            low = n.lower()
            p = os.path.join(root, n)
            if "tier" in low and low.endswith((".csv", ".txt", ".md")) and os.path.realpath(p) not in seen \
                    and os.path.isfile(p):
                seen.add(os.path.realpath(p))
                st = os.stat(p)
                rows.append({"icon": FILE_ICON, "name": show(p), "value": p, "kind": "file", "mtime": st.st_mtime,
                             "info": human_size(st.st_size), "date": short_date(st.st_mtime, now)})
    rows.sort(key=lambda r: -r["mtime"])
    return rows[:20]


# ---------------------------------------------------------------- the browser (A)
class FolderBrowser:
    """Browse folders to pick a file (mode "file": one with `exts`) or a folder (mode "folder")."""

    def __init__(self, parent, title, start, mode="file", exts=IMPORT_EXTS, save_dir=None, animator=None,
                 note=None):
        self.mode, self.exts, self.result = mode, exts, None
        self.dlg = dlg = StyledDialog(parent, title, title, note, animator=animator, wrap_chars=70)
        b = dlg.body
        side = tk.Frame(b, bg=PALETTE["bg"])
        side.grid(row=0, column=0, rowspan=3, sticky="n", padx=(0, 14))
        tk.Label(side, text="Places", bg=PALETTE["bg"], fg=PALETTE["muted"], font=font("body")).pack(anchor="w",
                                                                                                  pady=(0, 4))
        spots = places(save_dir)
        self.places = FileList(side, on_select=lambda row: self.go(row["value"]), rows_visible=len(spots),
                               width_chars=max(len(label) for _i, label, _f in spots) + 6)
        self.places.set_rows([{"icon": icon, "name": label, "value": folder, "kind": "place"}
                              for icon, label, folder in spots])
        self.places.pack(anchor="w")
        self.steps = tk.Frame(b, bg=PALETTE["bg"])
        self.steps.grid(row=0, column=1, sticky="w", pady=(0, 8))
        self.list = FileList(b, on_open=self._open, on_select=lambda row: self._sync_button())
        self.list.grid(row=1, column=1, sticky="w")
        self.list.bind("<BackSpace>", lambda e: (self.up(), "break")[1])
        shows = ", ".join(e.lstrip(".") for e in exts)
        tk.Label(b, text=(f"Shows folders and {shows} files" if mode == "file" else
                          "Pick the folder to save in (files already there are greyed)"),
                 bg=PALETTE["bg"], fg=PALETTE["muted"], font=font("body")).grid(row=2, column=1, sticky="w",
                                                                                 pady=(10, 0))
        dlg.button("Cancel", dlg.close)
        self.ok = dlg.button("Open" if mode == "file" else "Choose this folder", self._choose, default=True)
        self.folder = None
        self.go(start if start and os.path.isdir(start) else os.path.expanduser("~"))

    def go(self, folder):
        self.folder = os.path.abspath(folder)
        for w in self.steps.winfo_children():
            w.destroy()
        steps = path_steps(self.folder)
        for i, (label, p) in enumerate(steps):
            last = i == len(steps) - 1
            RoundButton(self.steps, label, lambda p=p: self.go(p), font=font("body"), padx=10, pady=2, radius=10,
                        bg=PALETTE["select_bg"] if last else PALETTE["surface"]).pack(side="left")
            if not last:
                tk.Label(self.steps, text="›", bg=PALETTE["bg"], fg=PALETTE["muted"],
                         font=font("body")).pack(side="left", padx=3)
        here = [i for i, row in enumerate(self.places.rows) if os.path.abspath(row["value"]) == self.folder]
        self.places.index = here[0] if here else None          # the place you are in is marked (quietly: no go())
        self.places.refresh()
        self.list.set_rows(list_folder(self.folder, self.exts, pick_files=self.mode == "file"))
        self.list.focus_set()
        self._sync_button()

    def up(self):
        parent = os.path.dirname(self.folder)
        if parent and parent != self.folder:
            self.go(parent)

    def _open(self, row):
        if row["kind"] == "dir":
            self.go(row["value"])
        elif self.mode == "file":
            self.result = row["value"]
            self.dlg.close()

    def _sync_button(self):
        row = self.list.selected
        if self.mode == "file":
            self.ok.set_enabled(row is not None)
            self.ok.config(text="Open folder" if row and row["kind"] == "dir" else "Open")

    def _choose(self):
        row = self.list.selected
        if self.mode == "folder":
            self.result = row["value"] if row and row["kind"] == "dir" else self.folder
            self.dlg.close()
        elif row is not None:
            self._open(row)


def browse(parent, title, start, mode="file", exts=IMPORT_EXTS, save_dir=None, animator=None, note=None):
    """Open a FolderBrowser and wait; the chosen path, or None."""
    fb = FolderBrowser(parent, title, start, mode, exts, save_dir, animator, note)
    fb.dlg.show(wait=True)
    return fb.result


# ---------------------------------------------------------------- Import (C)
class ImportDialog:
    """What can be imported, found in the usual places, with "Look somewhere else..." for anything else."""

    def __init__(self, parent, store_path, script_dir, animator=None, browse_fn=browse):
        self.result, self._browse, self.animator = None, browse_fn, animator
        self.store_path = store_path
        self.dlg = dlg = StyledDialog(parent, "Import earlier progress", "Import earlier progress",
                                      "Bring the placements from another save or an export into this list. "
                                      "Nothing here is overwritten.", animator=animator, wrap_chars=56)
        b = dlg.body
        self.rows = found_files(script_dir, store_path)
        if self.rows:
            tk.Label(b, text="Found on this computer", bg=PALETTE["bg"], fg=PALETTE["muted"],
                     font=font("body")).pack(anchor="w", pady=(0, 4))
            self.list = FileList(b, on_open=self._pick, on_select=lambda row: self.ok.set_enabled(True),
                                 rows_visible=min(6, max(3, len(self.rows))), width_chars=50)
            self.list.pack(anchor="w")
        else:
            self.list = None
            tk.Label(b, text="No other saves or exports were found in the usual places.", bg=PALETTE["bg"],
                     fg=PALETTE["muted"], font=font("body")).pack(anchor="w")
        self.elsewhere = RoundButton(b, "Look somewhere else…", self.look_elsewhere, font=font("body"),
                                     padx=12, pady=3, radius=10, flat=bool(self.rows), animator=animator)
        self.elsewhere.pack(anchor="w", pady=(10, 0))
        dlg.button("Cancel", dlg.close)
        self.ok = dlg.button("Import", lambda: self.list and self.list.selected and self._pick(self.list.selected),
                             default=True)
        if self.list:
            self.list.set_rows(self.rows, select=0)
            self.list.focus_set()
        else:
            self.ok.set_enabled(False)

    def _pick(self, row):
        self.result = row["value"]
        self.dlg.close()

    def look_elsewhere(self):
        start = os.path.join(os.path.expanduser("~"), "Documents")
        path = self._browse(self.dlg.win, "Import earlier progress", start, "file", IMPORT_EXTS,
                            os.path.dirname(os.path.abspath(self.store_path)) if self.store_path else None,
                            self.animator)
        if path:
            self.result = path
            self.dlg.close()
        elif self.dlg.alive():
            _regrab(self.dlg)


def ask_import(parent, store_path, script_dir, animator=None):
    d = ImportDialog(parent, store_path, script_dir, animator)
    d.dlg.show(wait=True)
    return d.result


# ---------------------------------------------------------------- Export (C)
class ExportDialog:
    """A name, a format and a folder; "Change folder..." to pick another folder."""

    def __init__(self, parent, folder, name="tierlist", kind="txt", save_dir=None, animator=None,
                 browse_fn=browse, confirm=ask_yes_no):
        self.result, self.kind, self.folder = None, kind if kind in dict((k, 1) for k, *_ in EXPORT_KINDS) else "txt", folder
        self._browse, self._confirm, self.save_dir, self.animator = browse_fn, confirm, save_dir, animator
        self.dlg = dlg = StyledDialog(parent, "Export tier list", "Export tier list",
                                      "Your placed words, by tier, as a file you can open anywhere.",
                                      animator=animator, wrap_chars=56)
        g = tk.Frame(dlg.body, bg=PALETTE["bg"])
        g.pack(anchor="w")
        gap = max(5, round(font("body").metrics("linespace") * 0.4))   # room between the rows (M-9), with the text
        lab = lambda text, row: tk.Label(g, text=text, bg=PALETTE["bg"], fg=PALETTE["text"], font=font("body")).grid(
            row=row, column=0, sticky="e", padx=(0, 10), pady=gap)
        lab("Name:", 0)
        self.name_var = tk.StringVar(value=name)
        self.entry = ttk.Entry(g, textvariable=self.name_var, width=26)
        self.entry.grid(row=0, column=1, sticky="w", pady=gap)
        lab("As:", 1)
        pills = tk.Frame(g, bg=PALETTE["bg"])
        pills.grid(row=1, column=1, sticky="w", pady=gap)
        self.kind_btns = {}
        for k, label, what in EXPORT_KINDS:
            btn = RoundButton(pills, label, lambda k=k: self.set_kind(k), font=font("body"), padx=12, pady=2,
                              radius=12, hint=what, animator=animator)
            btn.pack(side="left", padx=(0, 6))
            self.kind_btns[k] = btn
        lab("In:", 2)
        self.where = tk.Frame(g, bg=PALETTE["bg"])
        self.where.grid(row=2, column=1, sticky="w", pady=gap)
        self.problem = tk.Label(dlg.body, text="", bg=PALETTE["bg"], fg=PALETTE["bad"][1], font=font("body"))
        dlg.button("Cancel", dlg.close)
        dlg.button("Export", self.export, default=True)
        self.set_kind(self.kind)
        self._show_folder()
        self.entry.focus_set()
        self.entry.icursor("end")

    def set_kind(self, k):
        self.kind = k
        for key, btn in self.kind_btns.items():
            btn.config(bg=PALETTE["select_bg"] if key == k else PALETTE["surface"])
        name = self.name_var.get()                      # a typed extension follows the choice
        stem, ext = os.path.splitext(name)
        if ext.lower().lstrip(".") in [e for e, *_ in EXPORT_KINDS]:
            self.name_var.set(stem)

    def _show_folder(self):
        for w in self.where.winfo_children():
            w.destroy()
        steps = path_steps(self.folder)
        for i, (label, p) in enumerate(steps):
            last = i == len(steps) - 1
            RoundButton(self.where, label, lambda p=p: self.change_folder(p), font=font("body"), padx=10, pady=2,
                        radius=10, bg=PALETTE["select_bg"] if last else PALETTE["surface"]).pack(side="left")
            if not last:
                tk.Label(self.where, text="›", bg=PALETTE["bg"], fg=PALETTE["muted"],
                         font=font("body")).pack(side="left", padx=3)
        RoundButton(self.where, "Change folder…", lambda: self.change_folder(self.folder), font=font("body"),
                    padx=10, pady=2, radius=10, flat=True, animator=self.animator).pack(side="left", padx=8)

    def change_folder(self, start):
        got = self._browse(self.dlg.win, "Save in which folder?", start, "folder",
                           tuple("." + k for k, *_ in EXPORT_KINDS), self.save_dir, self.animator)
        if got:
            self.folder = got
            self._show_folder()
            self.dlg.refit()
        if self.dlg.alive():
            _regrab(self.dlg)

    def path(self):
        stem = os.path.splitext(self.name_var.get().strip())[0] if os.path.splitext(
            self.name_var.get().strip())[1].lower().lstrip(".") in [k for k, *_ in EXPORT_KINDS] \
            else self.name_var.get().strip()
        return os.path.join(self.folder, f"{stem}.{self.kind}") if stem else None

    def _say(self, text):
        self.problem.config(text=text)
        self.problem.pack(anchor="w", pady=(10, 0))
        self.dlg.refit()

    def export(self):
        p = self.path()
        if not p or any(c in os.path.basename(p) for c in "/\\"):
            self._say("Give the file a name.")
            return
        if not os.path.isdir(self.folder):
            self._say("That folder is not there any more: pick another.")
            return
        if os.path.exists(p) and not self._confirm("Export tier list", "Replace the file that is there?",
                                                   f"{os.path.basename(p)} is already in that folder.",
                                                   yes="Replace", no="Keep it", parent=self.dlg.win):
            return
        self.result = p
        self.dlg.close()


def ask_export(parent, folder, name="tierlist", kind="txt", save_dir=None, animator=None):
    d = ExportDialog(parent, folder, name, kind, save_dir, animator)
    d.dlg.show(wait=True)
    return d.result, d.kind, d.folder


def _regrab(dlg):
    """After a nested dialog closes, take the input back (it had taken the grab)."""
    try:
        dlg.win.grab_set()
        dlg.win.focus_force()
    except tk.TclError:
        pass
