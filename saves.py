"""Finding, choosing, remembering and exporting save files.

Why this exists: replacing tierlist.py (even in another folder) must never lose progress. At start-up
choose_save() looks at a pointer file in your home folder (~/.word_tierlist_path) and at the usual
places for .db files, opens each read-only to count placed words, and picks the best one. Anything
else with progress is offered for merging (Store.merge does the actual merge, in store.py).
"""
import os
from pathlib import Path
import sqlite3

from constants import TIERS


# --------------------------------------------------------------------------
# Finding your earlier save file (so replacing tierlist.py never loses progress)
# --------------------------------------------------------------------------
def _pointer_file():
    """Path of the small file that remembers which save was used last."""
    return os.path.join(os.path.expanduser("~"), ".word_tierlist_path")


def default_save_path(script_dir):
    """tierlist.db next to the script, or in your home folder if that folder is read-only."""
    if os.access(script_dir, os.W_OK):
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
    roots = [script_dir, os.path.dirname(script_dir), os.getcwd(), home]
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
    try:
        with open(_pointer_file(), encoding="utf-8") as f:
            pointer = f.read().strip() or None
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
    except OSError:
        pass


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
