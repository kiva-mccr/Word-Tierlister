#!/usr/bin/env python3
"""Pre-hand-off checks for the project. Run after every round of work, from the top of the project:

    python tools/check_release.py            # static checks only (fast)
    python tools/check_release.py --tests    # also run tests/run_tests.sh
    python tools/check_release.py --zip out.zip   # also build the zip (only if the checks pass)

Checks: every third-party import is in requirements.txt (and the runtime ones in deps.PACKAGES), every
module is in the README file map, every self-test is in run_tests.sh, every code file has its notes beside it
(name.md, up to date: tools/notes.py), the modules import only from the layers
below them (LAYERS, as .claude/CLAUDE.md lists them), pyflakes is clean (apart from the known re-export noise),
and no stray logs, saves or caches would end up in the zip.
Exit status is 0 only if everything passed. See .claude/CHECKLIST.md for the checks a script cannot do.

Layout (R-1): tierlist.py at the top (next to your save), the modules in src/, the self-tests in tests/,
this script in tools/, the Claude files in .claude/.
"""
import ast
import os
import re
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the top of the project
sys.path.insert(0, os.path.join(HERE, "src"))
import standalone  # noqa: E402  (what ships: standalone.SHIP_DIRS / source_files)
CODE_DIRS = ("", "src", "tests", "tools")         # where .py files live ("" = the top: tierlist.py)
KNOWN_OPTIONAL_DEV = {"PIL": "pillow", "PyInstaller": "pyinstaller"}   # only tests import these (screenshots, builds)
NOISE = ("imported but unused",)                  # tierlist.py re-exports and a few test imports
STRAY = (".db", ".db-wal", ".db-shm", ".log", ".pyc", ".part", ".png")


def _files_in(d):
    full = os.path.join(HERE, d)
    if not os.path.isdir(full):
        return []
    return sorted(os.path.join(d, f) if d else f for f in os.listdir(full) if os.path.isfile(os.path.join(full, f)))


def py_files():
    """Every .py file, as a path relative to the top ("tierlist.py", "src/app.py", "tests/_selftest.py")."""
    return [f for d in CODE_DIRS for f in _files_in(d) if f.endswith(".py")]


def _name(path):
    return os.path.basename(path)


def imports_of(path):
    """Top-level module names imported anywhere in the file (including inside functions)."""
    return {mod for mod, _line in _module_imports(path)}


def requirement_names():
    """Package names in requirements.txt, including commented-out optional ones ('# pillow')."""
    out = set()
    for line in open(os.path.join(HERE, "requirements.txt"), encoding="utf-8"):
        m = re.match(r"^#?\s*([A-Za-z][A-Za-z0-9_.-]*)\s*(?:[<>=!~].*)?$", line.strip())
        if m and not line.lstrip("# ").startswith(("Needed", "Optional", "Pillow", "tkinter")):
            out.add(m.group(1).lower())
    return out


def check_imports(problems):
    """Every import is our own module, the standard library, or in requirements.txt (with deps.PACKAGES)."""
    local = {_name(f)[:-3] for f in py_files()}
    stdlib = set(sys.stdlib_module_names)
    reqs = requirement_names()
    import importlib
    deps = importlib.import_module("deps")
    runtime, dev = {}, {}
    for f in py_files():
        for name in imports_of(f) - local - stdlib:
            (dev if f.startswith(("tests", "tools")) else runtime).setdefault(name, []).append(f)
    for name, files in sorted(runtime.items()):
        if name == "tkinter":
            continue
        if name.lower() not in reqs:
            problems.append(f"'{name}' is imported by {', '.join(files)} but is not in requirements.txt")
        if name not in deps.PACKAGES and name not in KNOWN_OPTIONAL_DEV:
            problems.append(f"'{name}' is imported by {', '.join(files)} but is not in deps.PACKAGES "
                            f"(so the install offer will never cover it)")
    for name, files in sorted(dev.items()):
        if name == "tkinter":
            continue
        if name not in runtime and name.lower() not in reqs and KNOWN_OPTIONAL_DEV.get(name, name).lower() not in reqs:
            problems.append(f"'{name}' is imported by tests ({', '.join(files)}) but is not mentioned in requirements.txt")
    for spec_name, spec in deps.PACKAGES.items():
        if spec_name.lower() not in reqs and spec.split(">=")[0].lower() not in reqs:
            problems.append(f"deps.PACKAGES lists '{spec_name}' but requirements.txt does not")
    return sorted(runtime)


def check_docs(problems):
    """Every module is in the README's file map, every self-test in run_tests.sh, the notes present, no module at
    the top but tierlist.py (R-1)."""
    readme = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    for f in py_files():
        if not f.startswith("tests") and f"`{f.replace(os.sep, '/')}`" not in readme and f"`{_name(f)}`" not in readme:
            problems.append(f"{f} is not in the README file map")
    runner = open(os.path.join(HERE, "tests", "run_tests.sh"), encoding="utf-8").read()
    for f in py_files():
        if _name(f).startswith("_selftest") and _name(f)[:-3] not in runner:
            problems.append(f"{f} is not run by tests/run_tests.sh")
    for need in (".claude/CLAUDE.md", ".claude/CHECKLIST.md", "tierlist.py", "requirements.txt"):
        if not os.path.exists(os.path.join(HERE, need)):
            problems.append(f"{need} is missing")
    for f in _files_in(""):
        if f.endswith(".py") and f != "tierlist.py":
            problems.append(f"{f} is at the top of the project: modules go in src/, tests in tests/ (R-1)")


# The layers of src/ (.claude/CLAUDE.md), lowest first: a module imports only from modules before it; the ones in
# one inner list are equals (none imports another). Only UI modules (from "theme" on) import tkinter.
LAYERS = [["constants"], ["obscene"], ["rudeness"], ["problems"], ["deps"], ["keymap"], ["bundle"], ["standalone"],
          ["store"], ["wordsource", "saves", "definitions"], ["theme"], ["fonts"], ["sizing"], ["ui_style"],
          ["ui_motion"], ["smooth"], ["widgets"], ["errors"], ["startup"], ["ui_chart"], ["browser"], ["filepicker"],
          ["shortcuts"], ["dealing"], ["sources"], ["app"]]


def _module_imports(path):
    """(module name, line) for every import in the file, at any depth."""
    for node in ast.walk(ast.parse(open(os.path.join(HERE, path), encoding="utf-8").read())):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0], node.lineno
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0], node.lineno


def check_layers(problems):
    """Every src/ module is in LAYERS and imports only from the layers below its own; tkinter only from "theme"
    on (workers and the logic stay testable without a window)."""
    rank = {m: i for i, group in enumerate(LAYERS) for m in group}
    ui = rank["theme"]
    for f in _files_in("src"):
        if not f.endswith(".py"):
            continue
        me = _name(f)[:-3]
        if me not in rank:
            problems.append(f"{f} is not in check_release.LAYERS (and .claude/CLAUDE.md's layer list)")
            continue
        for mod, line in _module_imports(f):
            if mod in rank and mod != me and rank[mod] >= rank[me]:
                problems.append(f"{f}:{line} imports {mod}, which is not below it in the layers (LAYERS)")
            if mod == "tkinter" and rank[me] < ui:
                problems.append(f"{f}:{line} imports tkinter but is not a UI module (LAYERS: from theme on)")


def check_code_notes(problems):
    """Every code file has its notes beside it (src/app.py: src/app.md), with its purpose written and its
    generated parts (uses, used by, tests, public API) up to date (tools/notes.py)."""
    sys.path.insert(0, os.path.join(HERE, "tools"))
    import notes
    problems += notes.notes(check=True)


def check_pyflakes(problems):
    """pyflakes finds nothing (when it is installed)."""
    try:
        out = subprocess.run([sys.executable, "-m", "pyflakes", *py_files()], cwd=HERE,
                             capture_output=True, text=True).stdout
    except OSError:
        problems.append("pyflakes could not be run (pip install pyflakes)")
        return
    if "No module named pyflakes" in out:
        problems.append("pyflakes is not installed (pip install pyflakes)")
        return
    for line in out.splitlines():
        if line and not any(n in line for n in NOISE):
            problems.append("pyflakes: " + line)


def _walk(d):
    """Files under d (relative to the top), skipping version control, environments and caches."""
    return standalone.walk(HERE, d)


def shippable_files():
    """Files that belong in the zip, with their folders (standalone.source_files: also what a built program carries)."""
    return standalone.source_files(HERE)


def check_stray(problems):
    """No scratch files in the project (databases, logs, .pyc, .part, screenshots outside docs/); the save and its
    log next to tierlist.py are allowed."""
    for f in _walk(""):
        if f.endswith(STRAY) and not (f.startswith("docs" + os.sep) and f.endswith(".png")):
            if os.sep not in f and f.endswith((".db", ".db-wal", ".db-shm", ".log")):
                continue                              # your save and its log live next to tierlist.py: not shipped
            problems.append(f"stray file in the project (delete it or keep it out of the zip): {f}")


def build_zip(target):
    """Zip the shippable files into `target`, under one word-tierlist/ folder."""
    root = "word-tierlist"
    files = shippable_files()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(HERE, f), f"{root}/{f.replace(os.sep, '/')}")
    return len(files)


def main(argv):
    """The checks, then --tests (run them) and --zip (build the zip)."""
    problems = []
    sys.path[:0] = [os.path.join(HERE, "src"), HERE]
    check_imports(problems)
    check_docs(problems)
    check_layers(problems)
    check_code_notes(problems)
    check_pyflakes(problems)
    check_stray(problems)
    if "--tests" in argv:
        env = dict(os.environ)
        r = subprocess.run(["sh", os.path.join("tests", "run_tests.sh")], cwd=HERE, env=env, capture_output=True,
                           text=True)
        tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
        if r.returncode != 0:
            problems.append("tests failed: " + tail[0] + "  (run: sh tests/run_tests.sh)")
        else:
            print("tests:", tail[0])
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print("static checks: OK")
    if "--zip" in argv:
        target = argv[argv.index("--zip") + 1]
        print(f"zip: {build_zip(target)} files -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
