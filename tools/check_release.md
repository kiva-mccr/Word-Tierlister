# `tools/check_release.py`

The checks before handing a round over: requirements, the README file map, the test runner, every code file's notes, the import layers, pyflakes, stray files; `--tests` runs the suite, `--zip` builds the zip.

- **Uses:** `notes`, `standalone`
- **Used by:** nothing (run directly)
- **Tests:** `_selftest_release`

The module docstring has the details; this page is the map.

## Public API

- `py_files`: Every .py file, as a path relative to the top ("tierlist.py", "src/app.py", "tests/_selftest.py").
- `imports_of`: Top-level module names imported anywhere in the file (including inside functions).
- `requirement_names`: Package names in requirements.txt, including commented-out optional ones ('# pillow').
- `check_imports`: Every import is our own module, the standard library, or in requirements.txt (with deps.PACKAGES).
- `check_docs`: Every module is in the README's file map, every self-test in run_tests.sh, the notes present, no module at the top but tierlist.py (R-1).
- `check_layers`: Every src/ module is in LAYERS and imports only from the layers below its own; tkinter only from "theme" on (workers and the logic stay testable without a window).
- `check_code_notes`: Every code file has its notes beside it (src/app.py: src/app.md), with its purpose written and its generated parts (uses, used by, tests, public API) up to date...
- `check_pyflakes`: pyflakes finds nothing (when it is installed).
- `shippable_files`: Files that belong in the zip, with their folders (standalone.source_files: also what a built program carries).
- `check_stray`: No scratch files in the project (databases, logs, .pyc, .part, screenshots outside docs/); the save and its log next to tierlist.py are allowed.
- `build_zip`: Zip the shippable files into `target`, under one word-tierlist/ folder.
- `main`: The checks, then --tests (run them) and --zip (build the zip).

## Rules and pitfalls (fixed before: keep them fixed)

- `LAYERS` mirrors `.claude/CLAUDE.md`'s layer list; change both together.
- Build the zip only with `--zip` (never by hand: that is how files went missing).
