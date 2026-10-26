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
others. tools/build.py is the command-line way in.

Updates (T-8): latest_release asks GitHub for the newest release, newer says whether it is newer than this
VERSION, fetch_source downloads its source (the repository at its tag) ready to unpack or build from; the
programs a release carries are named in RELEASE_ASSETS. U-1 (File > Check for updates): the program updates itself
(fetch_program downloads this computer's program from the release, replace_program swaps it in for the running one,
which is kept as .old until the new one removes it: remove_old_program); a source that is a git checkout updates with
git_pull. No tkinter.
"""
import ast
import collections
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

import bundle
import deps
from constants import OFFLINE_ENV, REPO, VERSION, plan_line

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


REPO_FILES = ("LICENSE", ".gitignore", ".gitattributes")      # (in every download and clone: left out, a removed
                                                               # source left its folder behind for one hidden file)


def source_files(root=ROOT):
    """The complete source, with its folders: code, docs, tests, the Claude files, the licence and git's own lists
    (REPO_FILES); never saves, logs, caches, exports or a built program (docs/ may hold screenshots; src/icons
    holds the icon, IC-1; src/typefaces the fonts, UI-73)."""
    keep = []
    for f in walk(root):
        top_level = os.sep not in f
        if f.endswith((".py", ".md", ".txt", ".sh", ".yml")) or f in REPO_FILES or \
                (f.startswith("docs" + os.sep) and f.endswith(".png")) or \
                (f.startswith(os.path.join("src", "icons") + os.sep) and f.endswith((".png", ".ico", ".icns"))) or \
                (f.startswith(os.path.join("src", "typefaces") + os.sep) and f.endswith((".ttf", ".json"))):
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
    icons = os.path.join(root, "src", "icons")                     # (the window icon, IC-1: ui_style.set_icon)
    args += ["--add-data", f"{icons}{sep}icons"]
    typefaces = os.path.join(root, "src", "typefaces")             # (the fonts, UI-73: fonts.load_typefaces)
    args += ["--add-data", f"{typefaces}{sep}typefaces"]
    if platform.startswith("win"):                                  # (the .exe file's own icon, in Explorer)
        args += ["--icon", os.path.join(icons, "icon.ico")]
    elif mac:                                                       # (the app bundle's own icon, in Finder and the Dock)
        args += ["--icon", os.path.join(icons, "icon.icns")]
    if source:
        args += ["--add-data", f"{source}{sep}{SOURCE_DIR}"]
    for mod in bundle.EXCLUDE:
        args += ["--exclude-module", mod]
    return args


# what a build imports: a PyInstaller that only half installed passes "import PyInstaller" and then fails the
# build with "No module named 'PyInstaller.utils'" (reported), so the check imports the parts the build uses
PYINSTALLER_CHECK = "import PyInstaller.__main__, PyInstaller.utils.hooks"


def _python_ok(python, code):
    """True if `python -c code` runs, from a neutral folder (the folder the program was started from could hold a
    file that shadows a module: `python -m` and `-c` look there first)."""
    return subprocess.run([python, "-c", code], capture_output=True, cwd=tempfile.gettempdir(),
                          env=clean_env()).returncode == 0


def has_pyinstaller(python=sys.executable):
    return _python_ok(python, PYINSTALLER_CHECK)


def ensure_pyinstaller(python=sys.executable, log=print):
    """Install PyInstaller if this Python lacks it, or reinstall it if it is there but incomplete (pip; with
    --break-system-packages on a Python that refuses plain pip installs, such as Debian's). Returns True when it
    works."""
    if has_pyinstaller(python):
        return True
    broken = _python_ok(python, "import PyInstaller")
    log("Repairing PyInstaller (it is installed but incomplete)..." if broken else
        "Installing PyInstaller (one time, about 15 MB)...")
    repair = ["--force-reinstall", "--upgrade"] if broken else []
    for extra in ([], ["--break-system-packages"]):
        r = subprocess.run([python, "-m", "pip", "install", "--disable-pip-version-check", "pyinstaller", *repair,
                            *extra], capture_output=True, text=True, cwd=tempfile.gettempdir(), env=clean_env())
        if r.returncode == 0 and has_pyinstaller(python):
            return True
        if "externally-managed" not in (r.stderr + r.stdout):
            break
    log("Could not install PyInstaller:\n" + (r.stderr or r.stdout)[-1500:])
    return False


def _write_manifest(root, folder, files=None, version=VERSION):
    """Write `root`'s manifest (with when it was made and its VERSION) into `folder`; returns it."""
    m = manifest(root, files)
    m["made"], m["version"] = time.time(), version
    with open(os.path.join(folder, MANIFEST), "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=1, sort_keys=True)
    return m


def _stage_source(root, folder):
    """Copy the source into `folder` (with its folders) and write its manifest there; returns the manifest."""
    files = source_files(root)
    for f in files:
        os.makedirs(os.path.join(folder, os.path.dirname(f)), exist_ok=True)
        shutil.copy2(os.path.join(root, f), os.path.join(folder, f))
    return _write_manifest(root, folder, files, read_version(root))


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
                           capture_output=True, text=True, cwd=work,      # (a neutral folder: see _python_ok;
                           env=clean_env())                               # no built program's Tk paths)
        if r.returncode != 0:
            log("The build failed:\n" + r.stderr[-3000:])
            return None
        out = output_path(dist)
        size = os.path.getsize(out) if os.path.isfile(out) else sum(
            os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(out) for f in fs)
        log(f"  built {os.path.basename(out)} ({size / 1e6:.0f} MB)")
        if size > BIG_MB * 1e6:                   # (bigger than it should be: say what made it so)
            parts = biggest_parts(os.path.join(work, os.path.splitext(os.path.basename(out))[0]))
            if parts:
                log("  its biggest parts: " + ", ".join(f"{name} ({mb:.0f} MB)" for name, mb in parts))
        if source:
            shutil.copy2(os.path.join(source, MANIFEST), os.path.join(dist, SIDE_FILE))   # (beside it: up_to_date)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out


BIG_MB = 40                # a build is about 22 MB (Linux); past this its log names its biggest parts


def biggest_parts(folder, n=5):
    """[(package or file, MB before compression)] of the n biggest things PyInstaller packed, from the tables it
    leaves in its work `folder` (PKG-00.toc: files and libraries; PYZ-00.toc: Python modules, by package). A build
    of 99 MB was reported where 22 MB is usual: whatever else is installed on the computer can be pulled in."""
    sizes = collections.Counter()
    for table, sep in (("PKG-00.toc", "/"), ("PYZ-00.toc", ".")):
        try:
            with open(os.path.join(folder, table), encoding="utf-8") as fh:
                toc = ast.literal_eval(fh.read())
        except (OSError, ValueError, SyntaxError):
            continue
        entries = next((t for t in toc if isinstance(t, list)), [])
        for entry in entries:
            name, src, kind = (list(entry) + [None, None])[:3]
            if kind == "PYZ" or not isinstance(src, str) or not os.path.isfile(src):
                continue
            sizes[str(name).replace("\\", "/").split(sep)[0]] += os.path.getsize(src)
    return [(name, size / 1e6) for name, size in sizes.most_common(n)]


def make_program(root=ROOT, log=print, release=None, place=None):
    """File > Source & Updates, from source (T-6): build the program from the source as it is now and put it next
    to tierlist.py (replacing an older one), with its manifest beside it; `place`: in that folder instead (T-12:
    beside an unpacked source that is then cleaned up). `release` (latest_release): download that version's source
    first and build from it instead (T-8: "Update to the newest version first"). Returns its path, or None if it
    could not be built (the reason is logged). Run on a worker thread: it takes a minute or two."""
    log(plan_line(([f"Downloading version {release['version']}"] if release else [])
                  + (["Installing PyInstaller"] if not has_pyinstaller() else []) + ["Building", "Putting it in place"]))
    dist = tempfile.mkdtemp(prefix="wtl-dist-")
    try:
        source = fetch_source(release, os.path.join(dist, "release"), log) if release else root
        out = build(dist, source, log)
        if out is None:
            return None
        log("Putting it in place...")
        target = program_path(place or root)
        if os.path.isdir(target):
            shutil.rmtree(target)
        elif os.path.exists(target):
            os.remove(target)
        shutil.move(out, target)
        shutil.move(os.path.join(dist, SIDE_FILE), os.path.join(place or root, SIDE_FILE))   # (not os.replace: the
                                                  # temporary folder can be on another disk, reported: Errno 18)
        log(f"  {target}")
        if give_icon(target):
            log("  with its icon (in the file manager)")
        return target
    finally:
        shutil.rmtree(dist, ignore_errors=True)


def give_icon(program, platform=None, which=shutil.which, run=subprocess.run, home=None):
    """Linux: show the program's icon on its file in the file manager (reported: none on Fedora). A Linux program
    cannot carry one inside it as a Windows one does; GNOME Files (and others that read gvfs's metadata) show a
    file's custom icon, set with gio. Done when it is built and again whenever it starts (a copy moved or
    downloaded gets it too). True if it was set; never raises."""
    if not (platform or sys.platform).startswith("linux") or not which("gio"):
        return False
    icon = deps.kept_icon(home)
    if not icon:
        return False
    try:
        return run(["gio", "set", program, "metadata::custom-icon", "file://" + icon], capture_output=True,
                   timeout=5, env=clean_env()).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


TK_PATHS = ("TCL_LIBRARY", "TK_LIBRARY", "TCLLIBPATH", "TIX_LIBRARY")


def clean_env(env=None, frozen=None):
    """A copy of the environment fit for starting the other form, Python or the builder: without what a built
    program sets for itself, which outlives it and points into its temporary folder, gone once it closes
    (PyInstaller: Tcl / Tk's folders, its own library path, its _PYI_ variables; reported: "Tk data/library
    directory ('/tmp/_MEI.../_tk_data') could not be collected!" when the source it unpacked and started built a
    program). A Tcl / Tk path is also dropped when it is a built program's or no longer exists, whoever runs this:
    a source started by an older program still carries them. `frozen`: running as the built program (default:
    this one)."""
    env = dict(os.environ if env is None else env)
    frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    for key in TK_PATHS:
        val = env.get(key)
        if val is not None and (frozen or "_MEI" in val or not os.path.exists(val)):
            del env[key]
    for key in [k for k in env if k.startswith("_PYI_") or k == "_MEIPASS2"]:
        del env[key]
    for key in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "LIBPATH"):
        orig = env.pop(key + "_ORIG", None)     # (PyInstaller keeps the computer's own as NAME_ORIG)
        if orig is not None:
            env[key] = orig
        elif frozen:
            env.pop(key, None)
    if frozen:
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"   # (a built program it starts unpacks afresh, not into ours)
    return env


def start(path, popen=subprocess.Popen, args=()):
    """Start the program at `path` on its own, not as a child of this window (which then closes); `args`: its
    command-line options."""
    exe = executable(path)
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        return popen([exe, *args], creationflags=flags, close_fds=True, cwd=os.path.dirname(exe), env=clean_env())
    if sys.platform == "darwin" and path.endswith(".app"):
        return popen(["open", path, *(["--args", *args] if args else [])], env=clean_env())
    return popen([exe, *args], start_new_session=True, close_fds=True, cwd=os.path.dirname(exe), env=clean_env(),
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


def unpack(source, target, plan=None, from_program=True):
    """Unpack (or sync) `source` into `target` as plan_unpack says, then record what was unpacked (UNPACKED).
    Returns the plan carried out. `from_program` False: an update of a source folder from GitHub (not from the
    program): the record then says so, unless the folder was unpacked from the program before, and only a folder
    that came from the program is ever offered to be cleaned up behind (cleanup_place, remove_source)."""
    before = read_manifest(target, UNPACKED)
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
    record = read_manifest(source) or {}
    record[FROM_PROGRAM] = from_program or bool(before and came_from_program(before))
    with open(os.path.join(target, UNPACKED), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1, sort_keys=True)
    return plan


FROM_PROGRAM = "from_program"      # in UNPACKED: unpacked from the program (a record without it is from before: yes)


def came_from_program(record):
    """True if an unpack record (UNPACKED) is of a folder unpacked from the program, not only updated from GitHub."""
    return bool(record) and record.get(FROM_PROGRAM, True) is not False


# ---- cleaning up behind (T-12): a program made from an unpacked source, the source then removed --------------------
def cleanup_place(root=ROOT, platform=None):
    """Where a program made from `root` goes when the source is to be cleaned up behind it (asked for: offered
    whenever the program is made, however the source came here; T-12 offered it only for one unpacked from the
    program): where the source was, `root` itself (asked for: it went to the folder holding `root`, outside the one
    it was made in); only a folder unpacked from a program that sits beside it puts the new one there instead,
    replacing the old (T-12). None when it cannot be written to."""
    root = os.path.abspath(root)
    parent = os.path.dirname(root)
    if parent and parent != root and came_from_program(read_manifest(root, UNPACKED)) \
            and os.path.exists(program_path(parent, platform)) and os.access(parent, os.W_OK):
        return parent
    return root if os.access(root, os.W_OK) else None


REMOVE_RECORD = ".word-tierlist-remove.json"   # in a source folder to be removed: the files that may go (T-14)


def mark_for_removal(root=ROOT):
    """Before the program made from `root` removes it (remove_source): write down the files it may remove there,
    the source's own (source_files), so a folder that was not unpacked from the program (a download, a clone) loses
    only those and keeps anything else (a .git, a file of yours)."""
    with open(os.path.join(root, REMOVE_RECORD), "w", encoding="utf-8") as fh:
        json.dump({"files": [f.replace(os.sep, "/") for f in source_files(root)]}, fh)


def zip_source(root, folder):
    """Pack the source in `root` (source_files, with its folders, under one folder named like `root`) into a zip in
    `folder`, never over a file there ("name (2).zip", ...). Returns the zip's path."""
    name = os.path.basename(os.path.abspath(root))
    dest, n = os.path.join(folder, name + ".zip"), 2
    while os.path.exists(dest):
        dest, n = os.path.join(folder, f"{name} ({n}).zip"), n + 1
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for f in source_files(root):
            z.write(os.path.join(root, f), os.path.join(name, f))
    return dest


def move_save(save, folder):
    """Move a save file (with its -wal / -shm, its .bak backups and the log beside it) into `folder`, never over a
    file already there (then it is saved as tierlist-2.db, ...). Returns the save's new path. The save must be
    closed."""
    base, ext = os.path.splitext(os.path.basename(save))
    dest, n = os.path.join(folder, base + ext), 2
    while os.path.exists(dest):
        dest, n = os.path.join(folder, f"{base}-{n}{ext}"), n + 1
    here = os.path.dirname(os.path.abspath(save))
    for name in sorted(os.listdir(here)):
        p = os.path.join(here, name)
        if name in (os.path.basename(save) + "-wal", os.path.basename(save) + "-shm"):
            shutil.move(p, dest + name[len(os.path.basename(save)):])
        elif name.startswith(os.path.basename(save) + ".") and name.endswith(".bak"):
            shutil.move(p, dest + name[len(os.path.basename(save)):])
        elif name == "tierlist.log" and not os.path.exists(os.path.join(folder, name)):
            shutil.move(p, os.path.join(folder, name))
    shutil.move(save, dest)
    return dest


OURS = ("__pycache__", ".venv", "tierlist.log", UNPACKED, SIDE_FILE, ".pytest_cache", REMOVE_RECORD)


def remove_source(folder, tries=120, wait=0.25):
    """Remove an unpacked source folder (T-12), run by the new program as it starts (the old one may still be
    closing: on Windows a folder in use cannot be removed, so it tries again for a while). Only the program's own
    files go: those its unpack record lists (UNPACKED) or the old window wrote down for it (REMOVE_RECORD, T-14:
    a source that came from anywhere), OURS and any __pycache__; anything else (a save, a file of yours, a .git)
    stays, and so does the folder then. A program in the folder (it went where its source was) stays with its build
    record and the log. Never touches a folder with neither record. Returns the paths left behind, or None."""
    record = read_manifest(folder, UNPACKED)
    marked = read_manifest(folder, REMOVE_RECORD)
    if not came_from_program(record) and not marked:
        return None
    listed = set((record or {}).get("files", {})) | set((marked or {}).get("files", []))
    kept = (SIDE_FILE, "tierlist.log") if os.path.exists(program_path(folder)) else ()

    def ours(rel):
        parts = rel.split("/")
        return rel not in kept and (rel in listed or parts[0] in OURS or "__pycache__" in parts)

    left = []
    for _ in range(max(1, tries)):
        left, stuck = [], False
        for d, dirs, files in os.walk(folder, topdown=False):
            for name in files + dirs:
                p = os.path.join(d, name)
                rel = os.path.relpath(p, folder).replace(os.sep, "/")
                try:
                    if os.path.isdir(p) and not os.path.islink(p):
                        if not os.listdir(p):
                            os.rmdir(p)
                    elif ours(rel):
                        os.remove(p)
                    else:
                        left.append(p)
                except OSError:
                    stuck = True                # (still in use: the old window is closing)
        if not stuck:
            break
        time.sleep(wait)
    try:
        os.rmdir(folder)
    except OSError:
        pass
    return left


def default_source_folder(program=None):
    """Where the source goes unless you pick another folder: beside the program, in "Word Tier List source"."""
    program = program or (sys.executable if getattr(sys, "frozen", False) else ROOT)
    where = os.path.dirname(program)
    if where.endswith(os.path.join(".app", "Contents", "MacOS")):        # (beside the .app, not inside it)
        where = os.path.dirname(os.path.dirname(os.path.dirname(where)))
    return os.path.join(where, "Word Tier List source")


def existing_source(program=None):
    """A copy of the source the program sits beside already, or None: tierlist.py right there (it was built from
    that source: T-6 puts it next to tierlist.py), or a folder beside it holding one (unpacked before, or made by
    hand, whatever its name). The first start unpacks the source only where none is (T-10)."""
    where = os.path.dirname(default_source_folder(program))
    if os.path.isfile(os.path.join(where, "tierlist.py")):
        return where
    try:
        names = sorted(os.listdir(where))
    except OSError:
        return None
    for name in names:
        folder = os.path.join(where, name)
        if os.path.isdir(folder) and (os.path.isfile(os.path.join(folder, "tierlist.py"))
                                      or os.path.isfile(os.path.join(folder, UNPACKED))):
            return folder
    return None


def start_source(folder, python, popen=subprocess.Popen, args=()):
    """Start tierlist.py in `folder` with `python` (and `args`), on its own (not a child of this program, which then
    closes)."""
    cmd = [python, os.path.join(folder, "tierlist.py"), *args]
    if sys.platform.startswith("win"):
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        return popen(cmd, creationflags=flags, close_fds=True, cwd=folder, env=clean_env())
    return popen(cmd, cwd=folder, start_new_session=True, close_fds=True, env=clean_env(),
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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
    return popen(["open" if sys.platform == "darwin" else "xdg-open", path], env=clean_env(),
                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)    # (the program's library path broke it)


# ---- updates (T-8): the newest release on GitHub ---------------------------------------------------------------------
RELEASES = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASE_ASSETS = {"linux": "word-tierlist-linux", "win32": "word-tierlist-windows.exe",   # (the workflow's names;
                  "darwin": "word-tierlist-macos.zip"}                                      # macOS: the zipped .app)


def version_tuple(text):
    """(1, 2, 0) for "v1.2.0" (the numbers in it, three at most)."""
    return tuple(int(n) for n in re.findall(r"\d+", str(text))[:3])


def read_version(root=ROOT):
    """The VERSION in `root`'s src/constants.py (the source being built may be another version than this one)."""
    try:
        with open(os.path.join(root, "src", "constants.py"), encoding="utf-8") as fh:
            m = re.search(r'^VERSION = "([^"]+)"', fh.read(), re.M)
        return m.group(1) if m else VERSION
    except OSError:
        return VERSION


def _download(url, timeout=10):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "word-tierlist/" + VERSION})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


last_error = None                  # why the last latest_release found nothing, when it failed (U-3)


def latest_release(fetch=_download):
    """The newest release on GitHub, {"version", "tag", "source" (its source as a zip), "page"}, or None when
    offline, GitHub cannot be reached or there is none yet. `fetch(url) -> bytes` (tests pass their own)."""
    global last_error
    last_error = None
    if os.environ.get(OFFLINE_ENV):
        return None
    try:
        data = json.loads(fetch(RELEASES))
    except Exception as exc:                # offline, no release yet (404), rate-limited, an odd answer
        last_error = str(getattr(exc, "reason", None) or exc)       # (U-3: the dialog says why)
        return None
    tag = data.get("tag_name") if isinstance(data, dict) else None
    if not tag or not data.get("zipball_url") or not version_tuple(tag):
        return None
    assets = {a["name"]: {"url": a["browser_download_url"], "size": a.get("size") or 0}
              for a in data.get("assets") or () if isinstance(a, dict) and a.get("name") and a.get("browser_download_url")}
    return {"version": tag.lstrip("vV"), "tag": tag, "source": data["zipball_url"], "page": data.get("html_url", ""),
            "assets": assets}


def newer(release, version=VERSION):
    """True if `release` (latest_release) is a newer version than `version`."""
    return bool(release) and version_tuple(release["version"]) > version_tuple(version)


def fetch_source(release, folder, log=print, fetch=_download):
    """Download `release`'s source (GitHub's zip of the repository at its tag) into `folder`, with its manifest,
    ready to unpack (plan_unpack) or build from; returns `folder`. Raises OSError if it cannot."""
    log(f"Downloading version {release['version']}...")
    try:
        data = fetch(release["source"], timeout=60)
    except Exception as exc:
        raise OSError(f"could not download version {release['version']}: {exc}") from exc
    log(f"  {len(data) / 1e6:.1f} MB")
    os.makedirs(folder, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            parts = name.split("/")[1:]              # (GitHub's zip has one folder at the top: owner-repo-commit)
            if not parts or not parts[-1] or ".." in parts or name.startswith("/"):
                continue
            dest = os.path.join(folder, *parts)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(name) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)
    if not os.path.isfile(os.path.join(folder, "tierlist.py")):
        raise OSError(f"version {release['version']} on GitHub has no tierlist.py")
    _write_manifest(folder, folder, version=release["version"])
    return folder


# ---- U-1: the program updates itself; a git checkout updates with git pull ------------------------------------------
OLD_SUFFIX = ".old"                    # the program replaced by an update, until the new one removes it
UPDATE_DIR = ".word-tierlist-update-"  # beside the program while the new one downloads (the same disk: one move)


def _platform_key(platform=None):
    platform = platform or sys.platform
    return "win32" if platform.startswith("win") else "linux" if platform.startswith("linux") else platform


def running_program(platform=None, exe=None, frozen=None):
    """The program now running (the .exe or the Linux file; on macOS its .app), or None when running from source."""
    if not (getattr(sys, "frozen", False) if frozen is None else frozen):
        return None
    exe = os.path.abspath(exe or sys.executable)
    if _platform_key(platform) == "darwin":
        app = os.path.dirname(os.path.dirname(os.path.dirname(exe)))
        if app.endswith(".app"):
            return app
    return exe


def program_download(release, platform=None):
    """{"url", "size"} of the program in `release` (latest_release) for this computer, or None (none built for it)."""
    return ((release or {}).get("assets") or {}).get(RELEASE_ASSETS.get(_platform_key(platform)))


def _download_to(url, dest, log=print, timeout=60):
    """Download `url` into the file `dest` in pieces, saying how far it got ("  3.2 of 25.0 MB (12%)")."""
    req = urllib.request.Request(url, headers={"Accept": "application/octet-stream",
                                               "User-Agent": "word-tierlist/" + VERSION})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as out:
        total, got, shown = int(r.headers.get("Content-Length") or 0), 0, -1
        while True:
            piece = r.read(1 << 16)
            if not piece:
                break
            out.write(piece)
            got += len(piece)
            pct = int(got * 100 / total) if total else None
            if pct != shown and pct is not None:
                shown = pct
                log(f"  {got / 1e6:.1f} of {total / 1e6:.1f} MB ({pct}%)")
    return got


def fetch_program(release, folder, log=print, platform=None, download=_download_to):
    """Download this computer's program from `release` into `folder` (macOS: the .app out of its zip) and return its
    path, ready for replace_program. Raises OSError if the release has none for this computer or it cannot."""
    asset = program_download(release, platform)
    if not asset:
        raise OSError(f"version {release['version']} has no program for this computer")
    name = RELEASE_ASSETS[_platform_key(platform)]
    dest = os.path.join(folder, name)
    log(f"Downloading version {release['version']}...")
    try:
        got = download(asset["url"], dest, log)
    except Exception as exc:
        raise OSError(f"could not download version {release['version']}: {exc}") from exc
    if not got or (asset.get("size") and got != asset["size"]):
        raise OSError(f"the download of version {release['version']} was cut short: try again")
    if _platform_key(platform) != "darwin":
        os.chmod(dest, 0o755)
        return dest
    log("Unpacking it...")
    if shutil.which("ditto"):              # (keeps the app's links, permissions and signature)
        subprocess.run(["ditto", "-x", "-k", dest, folder], check=True, env=clean_env())
    else:
        with zipfile.ZipFile(dest) as z:
            for info in z.infolist():
                if ".." in info.filename.split("/") or info.filename.startswith("/"):
                    continue
                path = z.extract(info, folder)
                mode = info.external_attr >> 16
                if mode & 0o111:
                    os.chmod(path, 0o755)
    os.remove(dest)
    apps = [n for n in os.listdir(folder) if n.endswith(".app")]
    if not apps:
        raise OSError(f"version {release['version']}'s download holds no program")
    return os.path.join(folder, apps[0])


def update_folder(program):
    """A new, empty folder beside `program` to download the new one into (the same disk, so swapping it in is one
    move); raises OSError when the program's folder cannot be written to (then the update cannot replace it)."""
    return tempfile.mkdtemp(prefix=UPDATE_DIR, dir=os.path.dirname(os.path.abspath(program)))


def _remove(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    elif os.path.lexists(path):
        os.remove(path)


def replace_program(new, current):
    """Put the program `new` where `current` is (the running one: Windows lets a running .exe be renamed, never
    overwritten), keeping the old one as current + OLD_SUFFIX until the new one starts and removes it
    (remove_old_program). If the new one cannot go in, the old one is put back. Returns the old one's new path."""
    old = current + OLD_SUFFIX
    if os.path.lexists(old):
        try:
            _remove(old)
        except OSError:                    # (still in use by one that has not closed yet: another name)
            old = f"{current}.{int(time.time())}{OLD_SUFFIX}"
    os.rename(current, old)
    try:
        shutil.move(new, current)
    except OSError:
        if os.path.lexists(current):
            _remove(current)
        os.rename(old, current)
        raise
    return old


def remove_old_program(current=None, tries=20, wait=0.5):
    """As an updated program starts: remove the program it replaced (OLD_SUFFIX) and any download folder left beside
    it (UPDATE_DIR). The old one may still be closing (on Windows it cannot be removed until then): tried `tries`
    times. Returns how many were removed."""
    current = current or running_program()
    if not current:
        return 0
    where, base = os.path.dirname(current), os.path.basename(current)
    try:
        names = os.listdir(where)
    except OSError:
        return 0
    left = [os.path.join(where, n) for n in names
            if (n.startswith(base + ".") and n.endswith(OLD_SUFFIX)) or n.startswith(UPDATE_DIR)]
    removed = 0
    for _ in range(tries):
        for path in list(left):
            try:
                _remove(path)
                left.remove(path)
                removed += 1
            except OSError:
                pass
        if not left:
            break
        time.sleep(wait)
    return removed


def git_checkout(root=ROOT):
    """True if `root` is a git checkout and git is installed: then an update is a git pull."""
    return os.path.isdir(os.path.join(root, ".git")) and bool(shutil.which("git"))


def git_pull(root=ROOT, run=subprocess.run):
    """`git pull --ff-only` in `root`: (True, what git said) if it worked, else (False, why). It never merges or
    overwrites your own changes: git refuses instead, and says why."""
    try:
        r = run(["git", "pull", "--ff-only"], cwd=root, capture_output=True, text=True, timeout=180, env=clean_env(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    return r.returncode == 0, ((r.stdout or "") + (r.stderr or "")).strip()
