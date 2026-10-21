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
constants, obscene, problems, deps, keymap -> store -> wordsource / saves / definitions -> theme, fonts, sizing, ui_style,
ui_motion, smooth, widgets, errors, startup -> ui_chart, browser, filepicker, shortcuts, dealing -> app -> tierlist.
- Only UI files import tkinter. `problems.py` is deliberately tkinter-free.
- Every public Store mutator commits before returning. No animation frame may touch the database.
- Worker threads (startup) never touch tkinter.

## Conventions worth keeping
- Light theme only. Pastel and cutesy, short tasteful animations, no badges, streaks or goals.
- A key press makes running animations speed out of the way (Animator.hurry_all), never jump; each message
  is its own Toast with the newest on top.
- Keep the pastel look over colour-blind colour tuning wherever labels (letters, counts) already carry the
  meaning; the user chose this for the tier chart.
- The word card has a fixed size (fonts + room, never the word) and fits each word in its own font copy; keep
  per-word work free of geometry changes. Check layout jitter with `tools/layout_trace.py` (under xvfb-run).
- Rounded shapes are drawn with `SmoothCanvas.round_rect` (smooth.py: soft-edged images over an invisible
  polygon; Tk's own canvas shapes are jagged, worst on Windows). Never `create_polygon(..., smooth=True)` for
  them (small icons: `SmoothCanvas.icon_image` with `smooth.ICONS`, never text symbols). Use `round_rect_coords` to resize; a shape on the plain canvas colour is pre-blended (cheap), over
  other shapes its edge stays see-through. Pop-ups are kept on their monitor with `sizing.clamp_to_monitor`.
- New widgets go in widgets.py and are tested in _selftest_widgets2.py. After animating a frame's
  height, reset it to height=0 and pack_propagate(True), or Tk flips between sizes forever.
- The bottom-right hint lists only keys no on-screen button already shows. Every key comes from `keymap.py`
  (App.keys; UI-48): never hard-code a key or its name in a hint, button or menu; App.apply_keys refreshes them.
- Placing uses the number keys 1-6, not tier letters (the user dropped UI-29). A held key repeats after
  500 ms, then every 250 ms (App._repeat_allowed); tests' key() helper sends a press and a release.
- No ttk.Combobox or tk.Menu popups: they grab input and float over other programs on Linux. Use
  ChoiceButton / DropMenu. To test focus behaviour for real: Xvfb + openbox + xdotool (installed here).
- Colours come from `theme.PALETTE` / `TIER_COLORS`; fonts from `fonts.font(role)` (shared Font objects;
  after resizing them call `widgets.refresh_widgets(window)`).
- Window sizes come from `sizing.py` (screen- and content-aware). Measure text instead of assuming dpi.
  Main window: what shows = min(zoom, biggest size that fits the screen, in 0.1 steps) x grow (window
  bigger than normal, UI-25); re-fit from the zoom on every layout change, never ratchet down. Measure
  minimum sizes at grow 1. Main and Browse zooms are separate and saved.
- Test speed on a big save (300k-1M words) for anything run per duel or per refresh: a query that sorts a
  whole tier is ~100 ms there, and nothing may build lists that grow with the square of a tier. Read the
  indexes instead (tier+rating, tier+games, partial ones over placed words, ...; check EXPLAIN QUERY PLAN for
  "TEMP B-TREE"). Test both a densely placed save and a sparse one (a few thousand placed of a million): a
  query can be quick on one and slow on the other. Look for orphans
  with vulture (installed here: `python3.12 -m vulture src tierlist.py tools tests`).
- Long work on the save (a reshuffle) runs on a worker thread with App.busy set and a moving bar; nothing
  else may write the save meanwhile.
- Keep `deps.PACKAGES` in step with `requirements.txt` (a test checks it); a new package also needs its
  `deps.SIZE`, `PURPOSE` and `HOMEPAGE` entries.
- Dialogs: build on `widgets.StyledDialog` (or errors.show_message / ask_yes_no / show_error); no tk
  messagebox. The bottom bar's square ttk buttons stay on purpose.
- Errors: raise `problems.SetupError` for fixable problems; plain-language text lives in
  `problems.describe`; the dialog and safety net are in `errors.py` (everything runs inside `run_guarded`).
- Any progress bar with a real percentage must also show an ETA (`startup.EtaTracker` / `format_eta`).
  Long jobs name their main steps first (`constants.plan_line`) for the "Step i of n" corner; keep
  `wordsource.wiktionary_steps` / `queue_steps` in step with the stage lines they predict. pip downloads are
  measured by watching its TMPDIR (`deps.install`); re-measure `deps.DOWNLOAD` if requirements change.
- Screenshots for review: run the app under `xvfb-run`, grab with PIL `ImageGrab` (see git history or
  recreate); show the user pictures for each UI step. Check colours by reading pixel values: the image
  preview can wash out pale pastels.
- Censored (obscene) words: copies of the word side by side over 0.625 letter widths, cut straight at its ends
  (`widgets.smear_items`, `Unsmear`; un-smears under the pointer; the user picked it from many mock-ups), `constants.mask_word` (b•••••d) wherever only text fits (messages, Browse's list);
  route any new on-screen word through `App.shown` / `Store.censored`. Exports keep the real words.
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
  "+N today" with the "/hr" rate only on hover, progress bar (UI-14): a bookshelf of spines (zones page,
  chapter, book, shelf, library; height = share placed; colour = median tier blended round the colour wheel;
  the leaning tier in the hover note) with "95% of text" after it, packaging: T-6..T-8 (make a program / back to source as a sync / one command for Linux +
  Windows builds via GitHub Actions) are planned after the UI steps, after ST-5.

## Status
Done: UI-0..UI-13, UI-15..UI-20, UI-23 (Browse restyle), UI-24 (dialogs), UI-25 (contents grow with the window), UI-27 (focus back after a drop-down), UI-28 (anchor dialog), UI-47 (Tab between tabs), UI-30 (package links), UI-50 (queue Apply: no-change note, moving bar), UI-31 (a view per tab), UI-40 (anchors follow their tier), UI-34 + UI-14 (status line, progress shelf), UI-33 (pace, hover notes), UI-46 (tabs only with work), UI-35, UI-36, UI-43..45 (fixes, zoom), UI-49 (held keys), UI-52 (shelf hover), UI-37 (Space toggles comparing), UI-39 (Delete in Browse), UI-38 (Browse opens complete, like the other windows: no animation of its own; remembers its view), UI-41 (queue shape cards), UI-53 (smooth shapes), UI-54 (Windows scaling, pop-ups on their monitor), UI-55 (shelf marks), UI-42 (themed file picker on Linux), UI-48 (keyboard shortcuts: every key changeable), UI-51 (look up a word from the card), UI-26 (final pass: smoke test, 1M check), ST-1..ST-4 (terminal: tkinter only; window: a tick box per package), ST-5 (Linux / macOS: the terminal handed back; applications-menu launcher), ST-6 (How words are dealt: order, kinds of words, censoring), ST-7 (download speed, Step i of n), T-1 (saves.app_dir: a built program's save beside it), T-2 (tools/bundle.py: English word lists only), M-1..M-11 (the mini-roadmap: fixes, Browse column sort, an orphan / speed sweep), SZ-1, R-1 (folders). Next: T-3, T-6..T-9, W-1, then IC-1 (the program's icon, the very last). UI-32 (moving pastel
background) needs the user's OK to relax the no-motion-while-idle guardrail. The "Window by window" list in the roadmap
shows which steps touch which window.
Shelved ("In consideration" in the roadmap's Decisions): UI-21 next-up peek; Boundary's swap strip (archived,
commit 9b78889; swaps are still counted).
Decided: binaries go in GitHub Releases (T-8), not a folder; the placement toast ends in its chart bar (UI-17).

## Known gaps
- The Windows console detach (`startup.detach_console`) was only simulated here; confirm on real Windows.
  ST-5's terminal hand-back was checked on Linux in a pseudo-terminal, not on a Mac.
- UI-54 (dpi awareness, monitor work areas) was only simulated here; confirm on real Windows 11. Tk 8.6 keeps
  its size when moved to a monitor with a different scaling.
- On absurdly small effective screens (for example 1366x768 at 2.0 scaling with the definitions pane
  open) the centre area can still clip.
- Obscene words (the user's rule): most or the first of a word's meanings rude by Wiktionary's labels
  (`obscene.decide`); any-one-sense rules caught "bureaucracy", "box". Older saves read the rude categories'
  pages from Wiktionary (untested against the real site from here: proxy); offline, `obscene.py`'s
  hand-picked list stands in. Tests never go online (WORD_TIERLIST_OFFLINE in tests/_paths.py).
  The user found it only "kinda worked": "Obscene words" starts unticked for now; to be worked on later.
  Their plan (much later): tier-list the flagged words themselves (S = not obscene, F = obscene) and hand
  over the export; then mark the save's words from that file (no new review UI needed).
- A read-only save file's dialog could not be verified (the test machine ran as root).
- Reported: holding a key in Refine crashed the user's PC; not reproduced here (see UI-49's notes). Two
  hazards fixed (Boundary's pair list could reach gigabytes; held repeats now wait after a slow action).
  Ask what OS / save size / key if it happens again.
- "+N today" counts from the undo history, which keeps the last ~5,000 actions: past that in one day it
  undercounts.
