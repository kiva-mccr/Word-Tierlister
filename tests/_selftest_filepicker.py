import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""UI-42: the app's own Import / Export file choosing (Linux): found files first, a browser behind them."""
import os, tempfile, time
HOME = tempfile.mkdtemp()
os.environ["HOME"] = HOME                                  # (before anything asks where home is)
import tkinter as tk
import tierlist as T
import filepicker as FP
from fonts import init_fonts
from ui_style import apply_ttk_style
from widgets import FileList

# a pretend home: Documents (an export, a sub-folder, a note), Downloads, a hidden folder, another save
for d in ("Documents/old", "Downloads", ".hidden"):
    os.makedirs(os.path.join(HOME, d))
open(os.path.join(HOME, "Documents", "tierlist.csv"), "w").write("word,tier\nox,S\n")
open(os.path.join(HOME, "Documents", "notes.txt"), "w").write("not a tier list")
open(os.path.join(HOME, "Documents", "photo.png"), "w").write("x")
other = T.Store(os.path.join(HOME, "Downloads", "tierlist-old.db"))
other.insert_words([f"w{i}" for i in range(50)]); other.place("w1", 0); other.place("w2", 3); other.close()
mine = T.Store(os.path.join(HOME, "mine.db")); mine.insert_words(["a", "b"]); mine.close()

# ---- the small helpers
assert FP.human_size(512) == "512 B" and FP.human_size(2_100_000) == "2.1 MB" and FP.human_size(41_000_000) == "41 MB"
now = time.mktime((2026, 10, 18, 15, 0, 0, 0, 0, -1))
assert FP.short_date(now - 60, now).startswith("today") and FP.short_date(now - 40 * 86400, now) == "8 Sep"
assert FP.short_date(now - 400 * 86400, now).endswith("2025")
steps = FP.path_steps(os.path.join(HOME, "Documents", "old"))
assert [s[0] for s in steps] == ["Home", "Documents", "old"] and steps[-1][1] == os.path.join(HOME, "Documents", "old")
deep = FP.path_steps("/a/b/c/d/e/f/g")
assert len(deep) == 5 and deep[1][0] == "…" and deep[-1][0] == "g"                  # a long path keeps both ends
rows = FP.list_folder(os.path.join(HOME, "Documents"), FP.IMPORT_EXTS)
assert [r["name"] for r in rows] == ["old/", "notes.txt", "tierlist.csv"]                # folders first; no .png
assert FP.list_folder(HOME, FP.IMPORT_EXTS)[0]["name"] == "Documents/"                   # hidden folders left out
assert all(r["dim"] for r in FP.list_folder(os.path.join(HOME, "Documents"), (".csv",), pick_files=False)
           if r["kind"] == "file")                                                       # choosing a folder: files grey
found = FP.found_files(HOME, os.path.join(HOME, "mine.db"))
names = [r["name"] for r in found]
assert os.path.join("Downloads", "tierlist-old.db") in names and os.path.join("Documents", "tierlist.csv") in names
assert "mine.db" not in names and not any("notes" in n for n in names)                   # not this save; not a note
assert next(r for r in found if r["name"].endswith(".db"))["info"] == "2 placed"
assert [p[1] for p in FP.places(HOME)] == ["Home", "Documents", "Downloads", "Next to your save"]
from smooth import ICONS
assert all(p[0] in ICONS for p in FP.places(HOME)) and all(r["icon"] in ICONS for r in rows + found)  # M-8: drawn

root = tk.Tk(); root.geometry("400x300+0+0"); init_fonts(root); apply_ttk_style(root)
def pump(n=5):
    for _ in range(n):
        root.update(); time.sleep(0.02)
pump()
assert FP.use_themed(root) is (root.tk.call("tk", "windowingsystem") == "x11")

# ---- FileList: arrow keys skip greyed rows, Enter opens, a long list scrolls
opened = []
win = tk.Toplevel(root)
fl = FileList(win, on_open=opened.append, rows_visible=3); fl.pack(); pump()
fl.set_rows([{"name": "a/", "kind": "dir"}, {"name": "x.png", "dim": True}, {"name": "b.txt", "kind": "file"}])
win.focus_force(); fl.focus_force(); pump(10)
fl.event_generate("<Down>"); pump(1); assert fl.selected["name"] == "a/"
fl.event_generate("<Down>"); pump(1); assert fl.selected["name"] == "b.txt"              # the greyed row is skipped
fl.event_generate("<Return>"); pump(1); assert opened[-1]["name"] == "b.txt"
fl.set_rows([{"name": f"f{i}.txt"} for i in range(30)]); fl.select(20); assert fl.top == 18  # scrolled to show it
assert fl.find_withtag("scrollmark") and len(fl.find_withtag("name")) == 3
win.destroy()

# ---- the browser (A): into a folder, up again, pick a file; or choose a folder
fb = FP.FolderBrowser(root, "Import", HOME, "file", FP.IMPORT_EXTS, save_dir=HOME); pump()
assert fb.folder == HOME and fb.list.rows[0]["name"] == "Documents/" and fb.places.selected["name"] == "Home"
fb.places.select(1); pump(); assert fb.folder == os.path.join(HOME, "Documents")              # a place opens it
assert fb.places.selected["name"] == "Documents"
fb.go(os.path.join(HOME, "Documents", "old")); assert fb.places.selected is None              # not one of the places
fb.go(HOME)
fb.list.select(0); fb._choose(); pump()                                                  # "Open folder"
assert fb.folder == os.path.join(HOME, "Documents") and fb.result is None
fb.dlg.win.focus_force(); fb.list.focus_force(); pump(10); fb.list.event_generate("<BackSpace>"); pump(); assert fb.folder == HOME   # up a folder
fb.go(os.path.join(HOME, "Documents")); pump()
i = [r["name"] for r in fb.list.rows].index("tierlist.csv"); fb.list.select(i)
assert fb.ok.cget("text") == "Open"
fb._choose(); pump()
assert fb.result == os.path.join(HOME, "Documents", "tierlist.csv") and not fb.dlg.alive()
fb = FP.FolderBrowser(root, "Save in", os.path.join(HOME, "Documents"), "folder", (".txt",)); pump()
fb._choose(); assert fb.result == os.path.join(HOME, "Documents")                         # this folder
fb = FP.FolderBrowser(root, "Save in", os.path.join(HOME, "Documents"), "folder", (".txt",)); pump()
fb.list.select(0); fb._choose(); assert fb.result == os.path.join(HOME, "Documents", "old")  # the selected folder

# ---- Import (C): what it found, newest first; or look somewhere else
imp = FP.ImportDialog(root, os.path.join(HOME, "mine.db"), HOME); pump()
assert imp.list and imp.list.selected is not None and imp.ok.enabled
imp.ok.invoke(); pump(); assert imp.result in [r["value"] for r in found] and not imp.dlg.alive()
asked = []
imp = FP.ImportDialog(root, os.path.join(HOME, "mine.db"), HOME,
                      browse_fn=lambda *a, **k: (asked.append(a[2]), "/elsewhere/file.db")[1]); pump()
imp.look_elsewhere(); assert imp.result == "/elsewhere/file.db" and asked == [os.path.join(HOME, "Documents")]
empty_home = tempfile.mkdtemp()
imp = FP.ImportDialog(root, None, empty_home, browse_fn=lambda *a, **k: None); pump()
if not imp.rows:
    assert imp.list is None and not imp.ok.enabled                                       # nothing found: browse
imp.look_elsewhere(); assert imp.result is None and imp.dlg.alive()                      # cancelled: still open
imp.dlg.close()

# ---- Export (C): a name, a format, a folder; replacing a file asks first
answers = []
ex = FP.ExportDialog(root, os.path.join(HOME, "Documents"), "tierlist", "csv",
                     confirm=lambda *a, **k: answers.pop(0)); pump()
assert ex.path() == os.path.join(HOME, "Documents", "tierlist.csv")
assert ex.kind_btns["csv"].cget("bg") == T.PALETTE["select_bg"] != ex.kind_btns["txt"].cget("bg")
answers.append(False); ex.export(); assert ex.result is None and ex.dlg.alive()           # kept the old file
ex.name_var.set("my list.md"); ex.set_kind("txt")
assert ex.name_var.get() == "my list" and ex.path().endswith("my list.txt")               # the typed extension follows
ex.name_var.set("  "); ex.export(); assert ex.result is None and "name" in ex.problem.cget("text")
ex._browse = lambda *a, **k: os.path.join(HOME, "Downloads")
ex.change_folder(ex.folder); assert ex.folder == os.path.join(HOME, "Downloads")
ex.name_var.set("fresh"); ex.export()
assert ex.result == os.path.join(HOME, "Downloads", "fresh.txt") and not ex.dlg.alive()
root.destroy()

# ---- the app: on Linux Import and Export go through these dialogs; Export remembers folder and format
import app as A
store = T.Store(os.path.join(HOME, "mine.db"))
root = tk.Tk(); app = T.App(root, store, T.Definitions(store)); pump(10)
A.use_themed = lambda r: True
out = os.path.join(HOME, "Downloads", "export.md")
A.ask_export = lambda *a, **k: (out, "md", os.path.join(HOME, "Downloads"))
app.export(); pump()
assert os.path.exists(out) and store.get_meta("export_dir") == os.path.join(HOME, "Downloads")
assert store.get_meta("export_kind") == "md"
seen = {}
A.ask_export = lambda parent, folder, **k: (seen.update(folder=folder, kind=k.get("kind")), (None, "md", folder))[1]
app.export(); assert seen == {"folder": os.path.join(HOME, "Downloads"), "kind": "md"}   # remembered

A.ask_import = lambda *a, **k: None
app.import_progress(); pump()                                                           # cancelled: nothing happens
app.on_close()
print("FILEPICKER OK")
