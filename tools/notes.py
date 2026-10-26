#!/usr/bin/env python3
"""Every code file's notes (name.md beside name.py): a map of the file for people and agents editing it.

    python tools/notes.py            bring the generated parts of every note up to date
    python tools/notes.py --check    say which notes are missing or out of date (check_release runs this)

A note has a hand-written part and a generated one. Written by hand: the title line's paragraph (what the file is
for) and the sections from "## Rules and pitfalls" on (what must stay true, the bugs fixed before, where to change
things). Generated from the code, so they cannot drift: which project modules the file uses and which use it, the
self-tests that import it, and its public functions and classes with the first sentence of each docstring. A new
code file gets a note with a placeholder purpose to fill in.
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTED = ("", "src", "tools")                    # the folders whose code files have notes ("": tierlist.py)
HAND = "## Rules and pitfalls"                  # where the hand-written sections start
TODO = "(What this file is for: write it here.)"


def code_files():
    out = []
    for d in NOTED:
        folder = os.path.join(ROOT, d)
        out += sorted(os.path.join(d, f) if d else f for f in os.listdir(folder)
                      if f.endswith(".py") and os.path.isfile(os.path.join(folder, f)))
    return [f.replace(os.sep, "/") for f in out]


def _imports(path):
    names = set()
    for n in ast.walk(ast.parse(open(os.path.join(ROOT, path), encoding="utf-8").read())):
        if isinstance(n, ast.Import):
            names |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            names.add(n.module.split(".")[0])
    return names


def _first_sentence(doc):
    text = " ".join((doc or "").split("\n\n")[0].split())
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    text = m.group(1) if m else text
    return text if len(text) <= 170 else text[:167].rsplit(" ", 1)[0] + "..."


def _split(text):
    """(purpose paragraph, hand-written sections) of an existing note."""
    body = text.split("\n", 1)[1] if "\n" in text else ""
    purpose = body.strip().split("\n\n")[0].strip() if body.strip() else TODO
    hand = text[text.index(HAND):].rstrip() if HAND in text else ""
    return purpose, hand


def render(path, files, imports, tests, old=""):
    """The note for `path`: its hand-written parts kept from `old`, the rest generated."""
    purpose, hand = _split(old) if old else (TODO, "")
    me = os.path.basename(path)[:-3]
    mods = {os.path.basename(f)[:-3] for f in files}
    uses = sorted(m for m in imports[path] if m in mods and m != me)
    users = sorted(os.path.basename(f)[:-3] for f in files if me in imports[f] and f != path)
    tested = sorted(t[:-3] for t, txt in tests.items()
                    if re.search(rf"\b(import {me}\b|from {me} import|{re.escape(me)}\.py)", txt))
    out = [f"# `{path}`", "", purpose, "",
           f"- **Uses:** {', '.join(f'`{u}`' for u in uses) or 'the standard library only'}",
           f"- **Used by:** {', '.join(f'`{u}`' for u in users) or 'nothing (run directly)'}",
           f"- **Tests:** {', '.join(f'`{t}`' for t in tested) or 'none of its own'}",
           "", "The module docstring has the details; this page is the map.", "", "## Public API", ""]
    tree = ast.parse(open(os.path.join(ROOT, path), encoding="utf-8").read())
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_"):
            out.append(f"- `{n.name}`: {_first_sentence(ast.get_docstring(n)) or '(no docstring)'}")
            methods = [b.name for b in n.body if isinstance(b, ast.FunctionDef) and not b.name.startswith("_")] \
                if isinstance(n, ast.ClassDef) else []
            if methods:
                out.append(f"  - methods: {', '.join(methods)}")
    if out[-1] == "":
        out.append("Nothing public: run it directly.")
    if hand:
        out += ["", hand]
    return "\n".join(out) + "\n"


def notes(check=False):
    """Bring every note up to date (or, with `check`, only list the ones missing, out of date or without their
    purpose written). Returns the list of problems."""
    files = code_files()
    imports = {f: _imports(f) for f in files}
    tdir = os.path.join(ROOT, "tests")
    tests = {f: open(os.path.join(tdir, f), encoding="utf-8").read() for f in os.listdir(tdir) if f.endswith(".py")}
    problems = []
    for f in files:
        md = os.path.join(ROOT, f[:-3] + ".md")
        old = open(md, encoding="utf-8").read() if os.path.exists(md) else ""
        new = render(f, files, imports, tests, old)
        if TODO in new:
            problems.append(f"{f[:-3]}.md: write what {f} is for")
        if new != old:
            if check:
                problems.append(f"{f[:-3]}.md is {'missing' if not old else 'out of date'} "
                                "(run: python tools/notes.py)")
            else:
                with open(md, "w", encoding="utf-8") as fh:
                    fh.write(new)
    return problems


if __name__ == "__main__":
    found = notes(check="--check" in sys.argv[1:])
    for p in found:
        print(p)
    sys.exit(1 if found and "--check" in sys.argv[1:] else 0)
