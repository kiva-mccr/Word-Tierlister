# Word Tier List: project notes for Claude Code

A tkinter app that tier-lists (S/A/B/C/D/F) every English word. Words come from English Wiktionary
(~1M, ranked by wordfreq). Progress autosaves to SQLite and is resumable. Entry point: `tierlist.py`
(at the top, next to the user's save); modules in `src/`, self-tests in `tests/`, `tools/check_release.py`,
and this file plus CHECKLIST.md in `.claude/` (R-1). Never move tierlist.py into a sub-folder.
The README has the file map; the roadmap (steps, status, decisions) is the big comment block at the
top of `tierlist.py`. Tick `[x]` there as steps land and keep the IDs stable.

## Run and test
- Install: `pip install -r requirements.txt` (wordfreq required; nltk optional). tkinter ships with Python
  (Debian/Ubuntu: `sudo apt install python3-tk`). The program needs internet only for the first-run
  Wiktionary download (~3 GB) and for online definitions.
- Run: `python tierlist.py` (`--db test.db` for a throwaway save, `--crash-test` shows the error dialog).
- This container: `python3.12` is the one with tkinter (`PY=python3.12 sh tests/run_tests.sh`); packages for it
  need `pip install --break-system-packages`. Xvfb is available for screenshots.
- Tests: `sh tests/run_tests.sh` (stops at the first failure and checks every exit status). If the default
  Python has no tkinter: `TK_PYTHON=/usr/bin/python3.12 sh tests/run_tests.sh`. Window tests need a display;
  on a headless Linux box they run under `xvfb-run` automatically.
- Run pyflakes before finishing (re-exports in tierlist.py and a few test imports are known noise).
- Every new widget or behaviour gets a `tests/_selftest_*.py` (first line `import _paths`) and a line in
  `tests/run_tests.sh`.

## Layering (a file only imports from files earlier in this list)
constants, problems, deps -> store -> wordsource / saves / definitions -> theme, fonts, sizing, ui_style,
errors, ui_motion, widgets, startup -> ui_chart, browser -> app -> tierlist.
- Only UI files import tkinter. `problems.py` is deliberately tkinter-free.
- Every public Store mutator commits before returning. No animation frame may touch the database.
- Worker threads (startup) never touch tkinter.

## Conventions worth keeping
- Light theme only. Pastel and cutesy, short tasteful animations, no badges, streaks or goals.
- A key press makes running animations speed out of the way (Animator.hurry_all), never jump; each message
  is its own Toast with the newest on top.
- Keep the pastel look over colour-blind colour tuning wherever labels (letters, counts) already carry the
  meaning; the user chose this for the tier chart.
- New widgets go in widgets.py and are tested in _selftest_widgets2.py. After animating a frame's
  height, reset it to height=0 and pack_propagate(True), or Tk flips between sizes forever.
- The bottom-right hint lists only keys no on-screen button already shows.
- Placing uses the number keys 1-6, not tier letters (the user dropped UI-29).
- No ttk.Combobox or tk.Menu popups: they grab input and float over other programs on Linux. Use
  ChoiceButton / DropMenu. To test focus behaviour for real: Xvfb + openbox + xdotool (installed here).
- Colours come from `theme.PALETTE` / `TIER_COLORS`; fonts from `fonts.font(role)` (shared Font objects;
  after resizing them call `widgets.refresh_widgets(window)`).
- Window sizes come from `sizing.py` (screen- and content-aware). Measure text instead of assuming dpi.
- Keep `deps.PACKAGES` in step with `requirements.txt` (a test checks it).
- Errors: raise `problems.SetupError` for fixable problems; plain-language text lives in
  `problems.describe`; the dialog and safety net are in `errors.py` (everything runs inside `run_guarded`).
- Any progress bar with a real percentage must also show an ETA (`startup.EtaTracker` / `format_eta`).
- Screenshots for review: run the app under `xvfb-run`, grab with PIL `ImageGrab` (see git history or
  recreate); show the user pictures for each UI step. Check colours by reading pixel values: the image
  preview can wash out pale pastels.
- Package sizes shown in the install dialog (deps.SIZE) were measured with pip; re-measure if requirements change.

## Before handing a round over
Run through `.claude/CHECKLIST.md` and `python tools/check_release.py --tests`; build the zip with
`python tools/check_release.py --zip word-tierlist.zip` (never copy files by hand, that is how files get
missed). Keep the README current in the same commit as the change (the user asked for this explicitly).

## How the user likes to work
- Go step by step through the roadmap; show screenshots for UI steps; do not build unapproved steps.
- Finish a step with: tests passing, roadmap ticked, README updated, a short summary.
- Every prompt, before finishing: tidy what was touched (dead code, stale comments and names, leftover
  debug lines, unused imports via pyflakes, scratch files out of the repo), then:
- Last thing on every prompt, after the work itself: update this CLAUDE.md if anything important
  changed (Status, Known gaps, new files, commands, conventions or user preferences), then commit and
  push it with the rest. Keep it short; skip it when nothing worth recording changed.
- The repo on GitHub is the source of truth for this file; a copy inside an uploaded zip may be older.
- UI styling: keep the bottom bar (Undo, Browse / edit, Definition and the key-hint line) roughly as it
  looks now; modernize the top (the File / Edit / View / Settings menus and the mode switch such as
  "Place new words"). UI-10 does the top; UI-24 restyles dialogs only.
- Ask before changing decisions already settled (see "Decisions" in the roadmap): light theme only,
  "+N today" with the "/hr" rate only on hover, progress bar (UI-14): equal segments by commonness (rank
  decades) with a "covers 99.4%" tag to its right, packaging: T-6..T-8 (make a program / back to source as a sync / one command for Linux +
  Windows builds via GitHub Actions) are planned after the UI steps, after ST-5.

## Status
Done: UI-0..UI-13, UI-15..UI-19, UI-35, UI-36, UI-43..45 (fixes, zoom), ST-1..ST-4 (terminal: tkinter only; window: a tick box per package), SZ-1, R-1 (folders). Next: UI-20 (empty states), UI-21, UI-23..27, then
ST-5, ST-6 (how words are dealt: order, kinds of words, hide obscene), T-1..T-3, T-6..T-9, W-1 (the very last). Also UI-28, UI-30 (anchor dialog, a web link per package in the install dialog), UI-47 (Tab between tabs), UI-48 (keyboard shortcuts menu), UI-33
(pace timeout + hover-note polish), UI-46 (hide Refine / Boundary / Conflicts tabs until they have work), UI-34..42 (a round of edits; the "Window by window" list in the
roadmap shows which steps touch which window), UI-32
(moving pastel background: needs the user's OK to relax the no-motion-while-idle guardrail). UI-14 is planned (measure decided).
Decided: binaries go in GitHub Releases (T-8), not a folder; the placement toast ends in its chart bar (UI-17).

## Known gaps
- The Windows console detach (`startup.detach_console`) was only simulated here; confirm on real Windows.
- Tk's own file dialog (Import / Export) still uses tk menus that grab input (can float over other
  programs on Linux); UI-42's themed file picker replaces it.
- On absurdly small effective screens (for example 1366x768 at 2.0 scaling with the definitions pane
  open) the centre area can still clip.
- Dialog buttons are still square until UI-24 (the bottom bar keeps its square look on purpose).
- A read-only save file's dialog could not be verified (the test machine ran as root).
- "+N today" counts from the undo history, which keeps the last ~5,000 actions: past that in one day it
  undercounts.
