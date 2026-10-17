#!/usr/bin/env python3
"""Pre-hand-off checks for the project. Run after every round of work:

    python check_release.py            # static checks only (fast)
    python check_release.py --tests    # also run run_tests.sh
    python check_release.py --zip out.zip   # also build the zip from the project folder (only if checks pass)

Checks: every third-party import is in requirements.txt (and the runtime ones in deps.PACKAGES), every
module is in the README file map, every self-test is in run_tests.sh, pyflakes is clean (apart from the
known re-export noise), and no stray logs, saves or caches would end up in the zip.
Exit status is 0 only if everything passed. See CHECKLIST.md for the checks a script cannot do.
"""
import ast
import os
import re
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
KNOWN_OPTIONAL_DEV = {"PIL": "pillow"}            # only tests may import these (screenshots)
NOISE = ("imported but unused",)                  # tierlist.py re-exports and a few test imports
STRAY = (".db", ".db-wal", ".db-shm", ".log", ".pyc", ".part", ".png")


def py_files():
    return sorted(f for f in os.listdir(HERE) if f.endswith(".py"))


def imports_of(path):
    """Top-level module names imported anywhere in the file (including inside functions)."""
    names = set()
    for node in ast.walk(ast.parse(open(os.path.join(HERE, path), encoding="utf-8").read())):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def requirement_names():
    """Package names in requirements.txt, including commented-out optional ones ('# pillow')."""
    out = set()
    for line in open(os.path.join(HERE, "requirements.txt"), encoding="utf-8"):
        m = re.match(r"^#?\s*([A-Za-z][A-Za-z0-9_.-]*)\s*(?:[<>=!~].*)?$", line.strip())
        if m and not line.lstrip("# ").startswith(("Needed", "Optional", "Pillow", "tkinter")):
            out.add(m.group(1).lower())
    return out


def check_imports(problems):
    local = {f[:-3] for f in py_files()}
    stdlib = set(sys.stdlib_module_names)
    reqs = requirement_names()
    import importlib
    deps = importlib.import_module("deps")
    runtime, dev = {}, {}
    for f in py_files():
        for name in imports_of(f) - local - stdlib:
            (dev if f.startswith("_selftest") else runtime).setdefault(name, []).append(f)
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
    readme = open(os.path.join(HERE, "README.md"), encoding="utf-8").read()
    for f in py_files():
        if not f.startswith("_selftest") and f != "check_release.py" and f"`{f}`" not in readme:
            problems.append(f"{f} is not in the README file map")
    runner = open(os.path.join(HERE, "run_tests.sh"), encoding="utf-8").read()
    for f in py_files():
        if f.startswith("_selftest") and f[:-3] not in runner:
            problems.append(f"{f} is not run by run_tests.sh")
    claude = os.path.join(HERE, "CLAUDE.md")
    if not os.path.exists(claude):
        problems.append("CLAUDE.md is missing")


def check_pyflakes(problems):
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


def shippable_files():
    """Files that belong in the zip: code, docs and the test runner; never saves, logs or caches."""
    keep = []
    for f in sorted(os.listdir(HERE)):
        p = os.path.join(HERE, f)
        if os.path.isfile(p) and (f.endswith((".py", ".md", ".txt", ".sh"))):
            keep.append(f)
    return keep


def check_stray(problems):
    for f in sorted(os.listdir(HERE)):
        if f.endswith(STRAY):
            problems.append(f"stray file in the project folder (delete it or keep it out of the zip): {f}")


def build_zip(target):
    root = "word-tierlist"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for f in shippable_files():
            z.write(os.path.join(HERE, f), f"{root}/{f}")
    return len(shippable_files())


def main(argv):
    problems = []
    sys.path.insert(0, HERE)
    check_imports(problems)
    check_docs(problems)
    check_pyflakes(problems)
    check_stray(problems)
    if "--tests" in argv:
        env = dict(os.environ)
        r = subprocess.run(["sh", "run_tests.sh"], cwd=HERE, env=env, capture_output=True, text=True)
        tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
        if r.returncode != 0:
            problems.append("tests failed: " + tail[0] + "  (run: sh run_tests.sh)")
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
