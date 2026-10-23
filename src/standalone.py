"""Making Word Tier List into a program for this computer (T-6), and what goes into one (T-3, T-7).

    source_files(root)        the complete source: what the zip ships and the program carries inside it
    manifest(root, files)     {"files": {path: sha256}}: what was built from, to tell whether anything changed
    program_path(root)        where the program goes: next to tierlist.py, so it uses the same save (T-1)
    up_to_date(root)          True if the program there was built from the source as it is now
    make_program(root, log)   install PyInstaller if missing, build, put the program in place; its path or None
    start(path)               start the program on its own (this window then closes)

The program carries its complete source (source_files) and the manifest inside it, under SOURCE_DIR, so the built
program can give the source back (T-7: no decompiling): bundled_source, plan_unpack (what would change: added,
updated, removed, backed up), unpack (do it, and record it in the folder: UNPACKED), summary (in a line). A build also leaves the manifest beside the program
(SIDE_FILE), which is how up_to_date knows. PyInstaller builds only for the system it runs on; T-8 covers the
others. tools/build.py is the command-line way in. No tkinter.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

import bundle
from constants import plan_line

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the top of the project (tierlist.py)
NAME = "word-tierlist"
MAC_NAME = "Word Tier List"
SOURCE_DIR = "source"                          # inside the program: the source it was built from, and MANIFEST
MANIFEST = "manifest.json"
SIDE_FILE = ".word-tierlist-build.json"        # beside the program: the manifest of its last build
# what the source is made of (R-1): the folders that ship, and the files in them that do
SHIP_DIRS = ("", "src", "tests", "tools", ".claude", "docs", ".github")
SKIP = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}


# ---- the source --------------------------------------------------------------------------------------------------
def walk(root=ROOT, d=""):
    """Files under `d` (relative to `root`), skipping version control, environments and caches; at the top only the
    folders that ship (SHIP_DIRS)."""
    out = []
    top_dir = os.path.abspath(root)
    for base, dirs, files in os.walk(os.path.join(root, d) if d else root):
        top = os.path.abspath(base) == top_dir
        dirs[:] = sorted(x for x in dirs if x not in SKIP and (d or not top or x in SHIP_DIRS))
        rel = os.path.relpath(base, root)
        out += [f if rel == "." else os.path.join(rel, f) for f in sorted(files)]
    return out


def source_files(root=ROOT):
    """The complete source, with its folders: code, docs, tests, the Claude files and the licence; never saves,
    logs, caches, exports or a built program (docs/ may hold screenshots)."""
    keep = []
    for f in walk(root):
        top_level = os.sep not in f
        if f.endswith((".py", ".md", ".txt", ".sh", ".yml")) or f == "LICENSE" or \
                (f.startswith("docs" + os.sep) and f.endswith(".png")):
            if top_level and f.endswith(".txt") and f != "requirements.txt":
                continue                              # an export (tierlist.txt) next to tierlist.py is yours
            keep.append(f)
    return keep


def manifest(root=ROOT, files=None):
    """{"files": {path ("/" between folders): sha256 of its bytes}} for `files` (default: source_files)."""
    files = source_files(root) if files is None else files
    out = {}
    for f in files:
        with open(os.path.join(root, f), "rb") as fh:
            out[f.replace(os.sep, "/")] = hashlib.sha256(fh.read()).hexdigest()
    return {"files": out}


# ---- the program -------------------------------------------------------------------------------------------------
def output_name(platform=None):
    platform = platform or sys.platform
    if platform.startswith("win"):
        return NAME + ".exe"
    return MAC_NAME + ".app" if platform == "darwin" else NAME


def output_path(dist, platform=None):
    """Where the built program ends up in `dist` for `platform` (sys.platform)."""
    return os.path.join(dist, output_name(platform))


def program_path(root=ROOT, platform=None):
    """Where File > Source & Updates puts the program: next to tierlist.py, so it keeps the same save."""
    return output_path(root, platform)


def executable(out, platform=None):
    """The file to run inside what was built (the .app's own executable on macOS)."""
    if (platform or sys.platform) == "darwin":
        return os.path.join(out, "Contents", "MacOS", MAC_NAME)
    return out


def last_build(root=ROOT):
    """The manifest of the program beside tierlist.py ({"files": ..., "made": time}), or None."""
    try:
        with open(os.path.join(root, SIDE_FILE), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def up_to_date(root=ROOT, platform=None):
    """True if the program beside tierlist.py exists and was built from the source exactly as it is now (every file
    the same, none added or removed)."""
    built = last_build(root)
    return bool(built) and os.path.exists(program_path(root, platform)) and \
        built.get("files") == manifest(root)["files"]


def pyinstaller_args(dist, work, root=ROOT, platform=None, source=None):
    """The PyInstaller command line (after "python -m PyInstaller") for this system. `source`: a folder to carry
    inside the program as SOURCE_DIR (the source and its manifest, for T-7), or None."""
    platform = platform or sys.platform
    sep = ";" if platform.startswith("win") else ":"
    mac = platform == "darwin"
    args = [os.path.join(root, "tierlist.py"), "--noconfirm", "--clean",
            "--name", MAC_NAME if mac else NAME,
            "--distpath", dist, "--workpath", work, "--specpath", work,
            "--paths", os.path.join(root, "src"),                        # (tierlist.py adds src/ itself at run time)
            "--additional-hooks-dir", os.path.join(root, "tools", "hooks"),
            "--windowed",                                               # no console window (ST-1, ST-2)
            "--onedir" if mac else "--onefile"]
    for src, dest in bundle.datas():
        args += ["--add-data", f"{src}{sep}{dest}"]
    if source:
        args += ["--add-data", f"{source}{sep}{SOURCE_DIR}"]
    for mod in bundle.EXCLUDE:
        args += ["--exclude-module", mod]
    return args


def has_pyinstaller(python=sys.executable):
    return subprocess.run([python, "-c", "import PyInstaller"], capture_output=True).returncode == 0


def ensure_pyinstaller(python=sys.executable, log=print):
    """Install PyInstaller if this Python lacks it (pip; with --break-system-packages on a Python that refuses
    plain pip installs, such as Debian's). Returns True when it is there."""
    if has_pyinstaller(python):
        return True
    log("Installing PyInstaller (one time, about 15 MB)...")
    for extra in ([], ["--break-system-packages"]):
        r = subprocess.run([python, "-m", "pip", "install", "--disable-pip-version-check", "pyinstaller", *extra],
                           capture_output=True, text=True)
        if r.returncode == 0 and has_pyinstaller(python):
            return True
        if "externally-managed" not in (r.stderr + r.stdout):
            break
    log("Could not install PyInstaller:\n" + (r.stderr or r.stdout)[-1500:])
    return False


def _stage_source(root, folder):
    """Copy the source into `folder` (with its folders) and write its manifest there; returns the manifest."""
    files = source_files(root)
    for f in files:
        os.makedirs(os.path.join(folder, os.path.dirname(f)), exist_ok=True)
        shutil.copy2(os.path.join(root, f), os.path.join(folder, f))
    m = manifest(root, files)
    m["made"] = time.time()
    with open(os.path.join(folder, MANIFEST), "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=1, sort_keys=True)
    return m


def build(dist, root=ROOT, log=print, carry_source=True):
    """Build the program into `dist` (installing PyInstaller first if needed): its path, or None if it failed.
    `carry_source`: put the source and its manifest inside it (T-7)."""
    if not ensure_pyinstaller(log=log):
        return None
    work = tempfile.mkdtemp(prefix="wtl-build-")
    try:
        source = None
        if carry_source:
            source = os.path.join(work, SOURCE_DIR)
            _stage_source(root, source)
        log(f"Building {output_name()} for this computer (a minute or two)...")
        log("  PyInstaller is putting Python, the program and its word lists into one file")
        r = subprocess.run([sys.executable, "-m", "PyInstaller", *pyinstaller_args(dist, work, root, source=source)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            log("The build failed:\n" + r.stderr[-3000:])
            return None
        out = output_path(dist)
        if source:
            shutil.copy2(os.path.join(source, MANIFEST), os.path.join(dist, SIDE_FILE))   # (beside it: up_to_date)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    size = os.path.getsize(out) if os.path.isfile(out) else sum(
        os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs)
    log(f"  built {os.path.basename(out)} ({size / 1e6:.0f} MB)")
    return out


def make_program(root=ROOT, log=print):
    """File > Source & Updates, from source (T-6): build the program from the source as it is now and put it next
    to tierlist.py (replacing an older one), with its manifest beside it. Returns its path, or None if it could
    not be built (the reason is logged). Run on a worker thread: it takes a minute or two."""
    log(plan_line((["Installing PyInstaller"] if not has_pyinstaller() else []) + ["Building", "Putting it in place"]))
    dist = tempfile.mkdtemp(prefix="wtl-dist-")
    try:
        out = build(dist, root, log)
        if out is None:
            return None
        log("Putting it in place...")
        target = program_path(root)
        if os.path.isdir(target):
            shutil.rmtree(target)
        elif os.path.exists(target):
            os.remove(target)
        shutil.move(out, target)
        os.replace(os.path.join(dist, SIDE_FILE), os.path.join(root, SIDE_FILE))
        log(f"  {target}")
        return target
    finally:
        shutil.rmtree(dist, ignore_errors=True)


def start(path, popen=subprocess.Popen):
    """Start the program at `path` on its own, not as a child of this window (which then closes)."""
    exe = executable(path)
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        return popen([exe], creationflags=flags, close_fds=True, cwd=os.path.dirname(exe))
    if sys.platform == "darwin" and path.endswith(".app"):
        return popen(["open", path])
    return popen([exe], start_new_session=True, close_fds=True, cwd=os.path.dirname(exe),
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---- back to source (T-7): the built program gives its source back ---------------------------------------------------
UNPACKED = ".word-tierlist-source.json"     # in an unpacked folder: the manifest of what was last unpacked there


def bundled_source():
    """The source carried inside this program (SOURCE_DIR), or None when running from source or built without it."""
    base = getattr(sys, "_MEIPASS", None)
    folder = os.path.join(base, SOURCE_DIR) if getattr(sys, "frozen", False) and base else None
    return folder if folder and os.path.isfile(os.path.join(folder, MANIFEST)) else None


def _sha(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def read_manifest(folder, name=MANIFEST):
    try:
        with open(os.path.join(folder, name), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def plan_unpack(source, target):
    """What unpacking `source` (a folder with MANIFEST) into `target` would do, without doing it:
    {"add": [...], "update": [...], "remove": [...], "backup": [...], "same": n} (paths with "/").

    Only files the program owns are ever touched: those in its manifest, and those the last unpack there put in
    (UNPACKED) that it no longer has (they are removed). A file you edited since the last unpack, or that was
    there before any unpack and differs, is backed up (name.bak) before it is replaced or removed. Anything else
    in the folder (your save, its log, a .venv) is never looked at."""
    new = (read_manifest(source) or {}).get("files", {})
    last = (read_manifest(target, UNPACKED) or {}).get("files", {})
    plan = {"add": [], "update": [], "remove": [], "backup": [], "same": 0}
    for f, digest in sorted(new.items()):
        have = _sha(os.path.join(target, f))
        if have is None:
            plan["add"].append(f)
        elif have == digest:
            plan["same"] += 1
        else:
            plan["update"].append(f)
            if last.get(f) != have:                 # edited since the last unpack (or never unpacked here)
                plan["backup"].append(f)
    for f, digest in sorted(last.items()):
        if f not in new:
            have = _sha(os.path.join(target, f))
            if have is not None:
                plan["remove"].append(f)
                if have != digest:
                    plan["backup"].append(f)
    return plan


def summary(plan):
    """"3 updated, 1 added, 1 removed (1 edited file kept as .bak first).", or that it is all the same already."""
    parts = [f"{len(plan[k]):,} {word}" for k, word in (("update", "updated"), ("add", "added"), ("remove", "removed"))
             if plan[k]]
    if not parts:
        return "Everything there is already the same."
    text = ", ".join(parts)
    if plan["backup"]:
        n = len(plan["backup"])
        text += f" ({n:,} edited file{'s' if n != 1 else ''} kept as .bak first)"
    return text[0].upper() + text[1:] + "."


def unpack(source, target, plan=None):
    """Unpack (or sync) `source` into `target` as plan_unpack says, then record what was unpacked (UNPACKED).
    Returns the plan carried out."""
    plan = plan or plan_unpack(source, target)
    os.makedirs(target, exist_ok=True)
    for f in plan["backup"]:
        p = os.path.join(target, f)
        if os.path.exists(p):
            shutil.copy2(p, p + ".bak")
    for f in plan["add"] + plan["update"]:
        dest = os.path.join(target, f)
        os.makedirs(os.path.dirname(dest) or target, exist_ok=True)
        shutil.copy2(os.path.join(source, f), dest)
    for f in plan["remove"]:
        try:
            os.remove(os.path.join(target, f))
        except OSError:
            pass
    shutil.copy2(os.path.join(source, MANIFEST), os.path.join(target, UNPACKED))
    return plan


def default_source_folder(program=None):
    """Where the source goes unless you pick another folder: beside the program, in "Word Tier List source"."""
    program = program or (sys.executable if getattr(sys, "frozen", False) else ROOT)
    where = os.path.dirname(program)
    if where.endswith(os.path.join(".app", "Contents", "MacOS")):        # (beside the .app, not inside it)
        where = os.path.dirname(os.path.dirname(os.path.dirname(where)))
    return os.path.join(where, "Word Tier List source")


def python_for_source():
    """A Python on this computer to start the unpacked tierlist.py with, or None (a built program has its own
    Python inside, which cannot run loose source files)."""
    for name in (("py", "python") if sys.platform.startswith("win") else ("python3", "python")):
        path = shutil.which(name)
        if path:
            return path
    return None


def open_folder(path, popen=subprocess.Popen):
    """Show a folder in the system's file manager."""
    if sys.platform.startswith("win"):
        os.startfile(path)                          # noqa: S606  (Windows only)
        return None
    return popen(["open" if sys.platform == "darwin" else "xdg-open", path],
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
