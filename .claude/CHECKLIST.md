# Checklist for every round of progress

Run through this before handing a round over (and again before a zip is sent). Items marked (auto) are
done by `python tools/check_release.py`; the rest need a person or Claude to look.

## 1. Code
- [ ] New code lives in the right layer (README, "Layers") and folder (modules in src/, tests in tests/,
      tierlist.py stays at the top); only UI files import tkinter (auto: check_release.LAYERS).
- [ ] Each code file touched: its note (`name.md`) still true. `python tools/notes.py` refreshes the generated
      parts (auto: --check); a rule changed or a bug fixed goes in its "Rules and pitfalls" by hand.
- [ ] Nothing written twice: a third copy of the same few lines becomes a helper (as `Store.meta_number`,
      `App.flash(kind=...)`, `StyledDialog.text`, `keymap.spec_of`).
- [ ] Every new third-party import is in `requirements.txt` AND `deps.PACKAGES` (auto). Optional ones are
      listed in requirements.txt too (commented), and the code works without them. Packages only tests or
      tools import (pillow, anthropic) go in requirements.txt commented, never in deps.PACKAGES.
- [ ] Every new module is in the README file map and the code map in `tierlist.py` (auto for the README).
- [ ] Anything that can fail for a user raises `SetupError` or uses `errors.show_exception`, with a
      plain-language message (no bare `sys.exit("...")`, no raw tracebacks).
- [ ] Any bar with a real percentage shows an ETA; animations respect Reduce motion and never block input.
- [ ] No animation frame touches the database; every Store mutator still commits before it returns.

## 2. Tests
- [ ] The new behaviour has a `_selftest_*.py`, and the file is in `tests/run_tests.sh` (auto).
- [ ] `sh tests/run_tests.sh` passes (`TK_PYTHON=...` if the default Python has no tkinter). Do not hand over
      anything with a red test; if a test had to change, say why.
- [ ] pyflakes is clean apart from the known re-export noise (auto).
- [ ] The tests that start the program use `--no-install` so no prompt blocks them.

## 3. Looks (UI rounds)
- [ ] Screenshots taken of every changed screen: place view, duel view, Browse, dialogs; plus the odd
      states (hover, pressed, disabled, long word, empty state).
- [ ] Looked at in at least a small screen (1366x768 at 1.333) and a large one (3840x2160 at 2.0).
- [ ] Nothing clipped; dropdowns, columns and buttons fit their text.

## 4. Packages and first run
- [ ] `python tools/check_release.py` passes (imports vs requirements, docs, tests listed, no strays).
- [ ] A clean environment test when dependencies changed: make a fresh venv, start with `--db test.db`,
      and confirm the install prompt appears, installs, and the program carries on.
- [ ] Errors still read well: bad `--db` path, missing wordfreq, disconnected internet during download.

## 5. Docs and hand-over
- [ ] Roadmap (comment block in `tierlist.py`): step ticked `[x]` with what was actually built, notes for
      later steps updated, no stale names (renamed functions, test files).
- [ ] README: file map, layers, any new command-line option or behaviour.
- [ ] `.claude/CLAUDE.md`: Status line (done / next) and Known gaps are current.
- [ ] Zip built with `python tools/check_release.py --zip word-tierlist.zip` (not copied by hand), then the
      file list looked at: every module, `requirements.txt`, `CLAUDE.md`, `CHECKLIST.md`, the tests,
      and no `.db`, `.log` or caches.
- [ ] Summary to the user: what changed, what was verified and how, what was NOT verified (and why),
      and the next step. Say plainly when something was only simulated (Windows behaviour, real disconnects).

## 6. On the user's machine (ask them; Claude cannot check these)
- [ ] Windows: no console window behind the app, closing it does not end the app.
- [ ] A real read-only save, a real full disk, a real `externally-managed` Python.
