"""Finding, choosing, remembering and exporting save files.

Why this exists: replacing tierlist.py (even in another folder) must never lose progress. At start-up
choose_save() looks at a pointer file in your home folder (~/.word_tierlister_path) and at the usual
places for .db files, opens each read-only to count placed words, and picks the best one. Anything
else with progress is offered for merging (Store.merge does the actual merge, in store.py).
"""
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

from constants import TIERS


# --------------------------------------------------------------------------
# Where the program keeps its things (T-1): the save, tierlist.log, the export, the Wiktionary download
# --------------------------------------------------------------------------
APP_NAME = "Word Tierlister"
OLD_APP_NAME = "Word Tier List"     # the program's name until 1.0.2: its folders and pointer file are still found
SOURCE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # (tierlist.py's folder, above src/)


def is_frozen():
    """True when running as a built program (PyInstaller), not as tierlist.py."""
    return bool(getattr(sys, "frozen", False))


def _writable(folder):
    """True if a file can really be made in `folder` (os.access alone is wrong on Windows for Program Files)."""
    try:
        with tempfile.TemporaryFile(dir=folder):
            return True
    except OSError:
        return False


def user_data_dir(platform=None, env=None, home=None):
    """The per-user folder for programs' data: %APPDATA% on Windows, ~/Library/Application Support on macOS,
    $XDG_DATA_HOME (~/.local/share) elsewhere; with this program's own folder in it (the one under its old name,
    OLD_APP_NAME, while only that one is there)."""
    platform, env = platform or sys.platform, os.environ if env is None else env
    home = home or os.path.expanduser("~")
    if platform.startswith("win"):
        base, names = env.get("APPDATA") or os.path.join(home, "AppData", "Roaming"), (APP_NAME, OLD_APP_NAME)
    elif platform == "darwin":
        base, names = os.path.join(home, "Library", "Application Support"), (APP_NAME, OLD_APP_NAME)
    else:
        base, names = env.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share"), ("word-tierlister",
                                                                                          "word-tierlist")
    new, old = (os.path.join(base, n) for n in names)
    return old if os.path.isdir(old) and not os.path.exists(new) else new    # (the save in the old one stays)


def program_dir(executable=None):
    """The folder a built program sits in: the executable's own, or on macOS the folder holding the .app (its
    executable is inside, Word Tierlister.app/Contents/MacOS/, which is replaced with every new version)."""
    folder = os.path.dirname(os.path.realpath(executable or sys.executable))
    parts = Path(folder).parts
    if len(parts) >= 3 and parts[-1] == "MacOS" and parts[-2] == "Contents" and parts[-3].endswith(".app"):
        return str(Path(*parts[:-3]))
    return folder


def app_dir(frozen=None, executable=None, writable=_writable, **where):
    """Where the save, its log and exports live. From source: tierlist.py's folder, as always. As a built program
    (T-1): the folder the program sits in, never the folder it unpacks itself into each time it starts (a
    one-file build's temporary folder is deleted when it exits, and the save with it); if that folder is
    read-only (Program Files, a disk image), the per-user data folder (user_data_dir), made if needed."""
    if not (is_frozen() if frozen is None else frozen):
        return SOURCE_DIR
    folder = program_dir(executable)
    if writable(folder):
        return folder
    data = user_data_dir(**where)
    os.makedirs(data, exist_ok=True)
    return data


def restart_args(argv=None, script=None, frozen=None):
    """The arguments to start this program again with sys.executable: the script and its options, or just the
    options for a built program (its executable is the program; there is no script to name)."""
    argv = sys.argv[1:] if argv is None else list(argv)
    if is_frozen() if frozen is None else frozen:
        return argv
    return [os.path.abspath(script or os.path.join(SOURCE_DIR, "tierlist.py")), *argv]


# --------------------------------------------------------------------------
# Finding your earlier save file (so replacing tierlist.py never loses progress)
# --------------------------------------------------------------------------
def _pointer_file():
    """Path of the small file that remembers which save was used last."""
    return os.path.join(os.path.expanduser("~"), ".word_tierlister_path")


def _old_pointer_file():
    """The same file under the program's old name (1.0.2 and older), read while there is no new one."""
    return os.path.join(os.path.expanduser("~"), ".word_tierlist_path")


def default_save_path(script_dir):
    """tierlist.db next to the script, or in your home folder if that folder is read-only."""
    if _writable(script_dir):
        return os.path.join(script_dir, "tierlist.db")
    return os.path.join(os.path.expanduser("~"), "tierlist.db")


def save_progress(path):
    """How far along a tier-list save file is, or None if `path` is not one (opened read-only)."""
    try:
        if os.path.getsize(path) < 8192:
            return None
        con = sqlite3.connect(Path(os.path.abspath(path)).as_uri() + "?mode=ro", uri=True, timeout=3)
        try:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"words", "meta", "comparisons"} <= tables:
                return None
            cols = {r[1] for r in con.execute("PRAGMA table_info(words)")}
            if not {"word", "tier", "skips"} <= cols:
                return None
            placed = con.execute("SELECT COUNT(*) FROM words WHERE tier IS NOT NULL").fetchone()[0]
            skipped = con.execute("SELECT COUNT(*) FROM words WHERE tier IS NULL AND skips > 0").fetchone()[0]
            total = con.execute("SELECT COUNT(*) FROM words").fetchone()[0]
        finally:
            con.close()
        return {"placed": placed, "skipped": skipped, "total": total, "progress": placed + skipped,
                "mtime": os.path.getmtime(path)}
    except (sqlite3.Error, OSError, ValueError):
        return None


def find_saves(script_dir):
    """Files that might be tier-list saves, in the places people usually keep them."""
    home = os.path.expanduser("~")
    roots = [script_dir, os.path.dirname(script_dir), os.getcwd(), home, user_data_dir()]   # (a built program's, T-1)
    roots += [os.path.join(home, *sub) for sub in (("Downloads",), ("Documents",), ("Desktop",), ("OneDrive",),
                                                     ("OneDrive", "Documents"), ("OneDrive", "Desktop"))]
    found, seen, seen_roots = [], set(), set()

    def add(p):  # add each real file once, even if two search roots reach it by different paths
        key = os.path.realpath(p)
        if key not in seen and os.path.isfile(p):
            seen.add(key)
            found.append(p)

    for root in roots:
        rkey = os.path.realpath(root)
        if rkey in seen_roots or not os.path.isdir(root):
            continue
        seen_roots.add(rkey)
        try:
            names = sorted(os.listdir(root))
        except OSError:
            continue
        for name in [n for n in names if n.lower().endswith(".db")][:60]:
            add(os.path.join(root, name))
        for name in names[:300]:                      # one level down: only files named tierlist*.db
            full = os.path.join(root, name)
            if name.startswith(".") or not os.path.isdir(full):
                continue
            try:
                inner = os.listdir(full)
            except OSError:
                continue
            for n in inner:
                if n.lower().startswith("tierlist") and n.lower().endswith(".db"):
                    add(os.path.join(full, n))
    return found


def choose_save(script_dir):
    """Pick the save file to open when --db is not given. Returns (path, info, others_with_progress).

    The file used last time wins if it has progress; otherwise the one with the most progress
    anywhere we look (a stray empty tierlist.db from a fresh download never hides your real one).
    """
    default = default_save_path(script_dir)
    pointer = None
    for path in (_pointer_file(), _old_pointer_file()):
        try:
            with open(path, encoding="utf-8") as f:
                pointer = f.read().strip() or None
            break
        except OSError:
            pass
    cands, seen = [], set()
    for p in ([pointer] if pointer else []) + [default] + find_saves(script_dir):
        key = os.path.realpath(p)
        if key in seen or not os.path.isfile(p):
            continue
        seen.add(key)
        info = save_progress(p)
        if info:
            info.update(path=os.path.abspath(p), key=key, default=(key == os.path.realpath(default)),
                        pointer=bool(pointer) and key == os.path.realpath(pointer))
            cands.append(info)
    active = [c for c in cands if c["progress"] > 0]
    if active:
        best = next((c for c in active if c["pointer"]), None) or \
            max(active, key=lambda c: (c["progress"], c["default"], c["mtime"]))
    else:
        best = next((c for c in cands if c["pointer"]), None) or next((c for c in cands if c["default"]), None)
    return (best["path"] if best else default), best, [c for c in active if c is not best]


def remember_save(path):
    """Remember which save file is in use, so a replaced or moved tierlist.py finds it again."""
    try:
        with open(_pointer_file(), "w", encoding="utf-8") as f:
            f.write(os.path.abspath(path))
        if os.path.exists(_old_pointer_file()):
            os.remove(_old_pointer_file())
    except OSError:
        pass


def is_code_note(path):
    """True when `path` is the note beside a code file (tierlist.md beside tierlist.py, R-1's notes), which a
    Markdown export of the same name would overwrite (found in a review: an export saved beside the save could)."""
    base, ext = os.path.splitext(path)
    if ext.lower() != ".md" or not os.path.isfile(base + ".py"):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            return f.readline().startswith("# `" + os.path.basename(base) + ".py`")
    except OSError:
        return False


def write_export(path, rows, skipped):
    """Write the tier list as .csv, .md or .txt (chosen by the extension).

    `rows` come from Store.export_rows(), `skipped` from Store.skipped_words(). Store.parse_export()
    reads these same formats back, so an export can be re-imported later.
    """
    if path.lower().endswith(".csv"):
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f)
            wr.writerow(["word", "tier", "rating", "duels"])
            for r in rows:
                wr.writerow([r["word"], TIERS[r["tier"]], round(r["rating"], 1), r["games"]])
            for w in skipped:
                wr.writerow([w, "?", "", 0])
        return
    md = path.lower().endswith(".md")
    with open(path, "w", encoding="utf-8") as f:
        for t in range(len(TIERS)):
            words = [r["word"] for r in rows if r["tier"] == t]
            f.write(("## " if md else "") + f"{TIERS[t]} tier ({len(words):,} words)\n")
            for i, w in enumerate(words, 1):
                f.write(f"{i}. {w}\n")
            f.write("\n")
        if skipped:
            f.write(("## " if md else "") + f"Skipped / unknown ({len(skipped):,} words)\n")
            f.write(", ".join(skipped) + "\n")
