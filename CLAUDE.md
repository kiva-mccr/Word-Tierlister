# Word Tier List: project notes for Claude Code

A tkinter app that tier-lists (S/A/B/C/D/F) every English word. Words come from English Wiktionary
(~1M, ranked by wordfreq). Progress autosaves to SQLite and is resumable. Entry point: `tierlist.py`.
The README has the file map; the roadmap (steps, status, decisions) is the big comment block at the
top of `tierlist.py`. Tick `[x]` there as steps land and keep the IDs stable.

## Run and test
- Install: `pip install -r requirements.txt` (wordfreq required; nltk optional). tkinter ships with Python
  (Debian/Ubuntu: `sudo apt install python3-tk`). The program needs internet only for the first-run
  Wiktionary download (~3 GB) and for online definitions.
- Run: `python tierlist.py` (`--db test.db` for a throwaway save, `--crash-test` shows the error dialog).
- This container: `python3.12` is the one with tkinter (`PY=python3.12 sh run_tests.sh`); packages for it
  need `pip install --break-system-packages`. Xvfb is available for screenshots.
- Tests: `sh run_tests.sh` (stops at the first failure and checks every exit status). If the default
  Python has no tkinter: `TK_PYTHON=/usr/bin/python3.12 sh run_tests.sh`. Window tests need a display;
  on a headless Linux box they run under `xvfb-run` automatically.
- Run pyflakes before finishing (re-exports in tierlist.py and a few test imports are known noise).
- Every new widget or behaviour gets a `_selftest_*.py` and a line in `run_tests.sh`.

## Layering (a file only imports from files earlier in this list)
constants, problems, deps -> store -> wordsource / saves / definitions -> theme, fonts, sizing, ui_style,
errors, ui_motion, widgets, startup -> browser -> app -> tierlist.
- Only UI files import tkinter. `problems.py` is deliberately tkinter-free.
- Every public Store mutator commits before returning. No animation frame may touch the database.
- Worker threads (startup) never touch tkinter.

## Conventions worth keeping
- Light theme only. Pastel and cutesy, short tasteful animations, no badges, streaks or goals.
- Colours come from `theme.PALETTE` / `TIER_COLORS`; fonts from `fonts.font(role)` (shared Font objects;
  after resizing them call `widgets.refresh_widgets(window)`).
- Window sizes come from `sizing.py` (screen- and content-aware). Measure text instead of assuming dpi.
- Keep `deps.PACKAGES` in step with `requirements.txt` (a test checks it).
- Errors: raise `problems.SetupError` for fixable problems; plain-language text lives in
  `problems.describe`; the dialog and safety net are in `errors.py` (everything runs inside `run_guarded`).
- Any progress bar with a real percentage must also show an ETA (`startup.EtaTracker` / `format_eta`).
- Screenshots for review: run the app under `xvfb-run`, grab with PIL `ImageGrab` (see git history or
  recreate); show the user pictures for each UI step.

## Before handing a round over
Run through `CHECKLIST.md` and `python check_release.py --tests`; build the zip with
`python check_release.py --zip word-tierlist.zip` (never copy files by hand, that is how files get missed).

## How the user likes to work
- Go step by step through the roadmap; show screenshots for UI steps; do not build unapproved steps.
- Finish a step with: tests passing, roadmap ticked, README updated, a short summary.
- Last thing on every prompt, after the work itself: update this CLAUDE.md if anything important
  changed (Status, Known gaps, new files, commands, conventions or user preferences), then commit and
  push it with the rest. Keep it short; skip it when nothing worth recording changed.
- The repo on GitHub is the source of truth for this file; a copy inside an uploaded zip may be older.
- UI styling: keep the bottom bar (Undo, Browse / edit, Definition and the key-hint line) roughly as it
  looks now; modernize the top (the File / Edit / View / Settings menus and the mode switch such as
  "Place new words"). UI-10 does the top; UI-24 restyles dialogs only.
- Ask before changing decisions already settled (see "Decisions" in the roadmap): light theme only,
  "+N today" with the "/hr" rate only on hover, progress bar (UI-14) on hold, packaging: T-6 / T-7 (make a program / back to source buttons) are planned after the UI steps.

## Status
Done: UI-0..UI-6, ST-1..ST-4 (ST-4: required packages + tkinter asked/installed in the terminal first,
optional ones in the window), SZ-1 (sizing). Next: UI-7 (TierRow), UI-8 (DuelCards), then UI-9, UI-13,
UI-16/17. UI-18 wires every hotkey to its button's pressed look via `RoundButton.flash`.

## Known gaps
- The Windows console detach (`startup.detach_console`) was only simulated here; confirm on real Windows.
- On absurdly small effective screens (for example 1366x768 at 2.0 scaling with the definitions pane
  open) the centre area can still clip.
- Dialog buttons are still square until UI-24 (the bottom bar keeps its square look on purpose).
- A read-only save file's dialog could not be verified (the test machine ran as root).
