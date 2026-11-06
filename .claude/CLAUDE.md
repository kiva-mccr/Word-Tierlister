# Word Tierlister: project notes for Claude Code

A tkinter app that tier-lists (S/A/B/C/D/F) every English word. Words come from English Wiktionary
(~1M, ranked by wordfreq). Progress autosaves to SQLite and is resumable. Entry point: `tierlist.py`
(at the top, next to the user's save); modules in `src/`, self-tests in `tests/`, `tools/check_release.py`,
and this file plus CHECKLIST.md in `.claude/` (R-1). Never move tierlist.py into a sub-folder.
README.md is the user-facing introduction (screenshots in docs/images); DEVELOPERS.md is the developer
guide (code graphs, the file map, options, tests, builds); the roadmap (steps, status, decisions) is the big comment block at the
top of `tierlist.py`. Tick `[x]` there as steps land and keep the IDs stable.

## Run and test
- Install: `pip install -r requirements.txt` (wordfreq required; nltk optional). tkinter ships with Python
  (Debian/Ubuntu: `sudo apt install python3-tk`). The program needs internet only for the first-run
  Wiktionary download (~3 GB) and for online definitions.
- Run: `python tierlist.py` (`--db test.db` for a throwaway save, `--crash-test` shows the error dialog).
- This container: `python3.12` is the one for tkinter (`PY=python3.12 sh tests/run_tests.sh`; if `import tkinter` fails: `apt-get install -y python3.12-tk xvfb openbox xdotool`); packages for it
  need `pip install --break-system-packages`. Xvfb is available for screenshots.
- Tests: `sh tests/run_tests.sh` (stops at the first failure and checks every exit status; `KEEP_GOING=1` lists every failure, `SHARD=k/n` runs one part (tests/_shard.py weights; re-measure if parts drift), `TEST_TIMEOUT` stops a stuck test and dumps its stacks first). If the default
  Python has no tkinter: `TK_PYTHON=/usr/bin/python3.12 sh tests/run_tests.sh`. Window tests need a display;
  on a headless Linux box they run under `xvfb-run` automatically.
- Run pyflakes before finishing (re-exports in tierlist.py and a few test imports are known noise).
- GitHub's test workflows (tests.yml, macos.yml) skip a push that changes only `.md` files, docs or images (asked for:
  a waste of time there); anything touching code still runs them. Pull requests get Linux + Windows (with a quick
  check job: check_release static + pyflakes src tools); macOS runs on pushes to main, nightly and by hand only (F-51).
  Locally, for a text-only or removal change, run just the tests that cover it.
- Every new widget or behaviour gets a `tests/_selftest_*.py` (first line `import _paths`) and a line in
  `tests/run_tests.sh`.

## Notes beside the code
Every code file in the top folder, `src/` and `tools/` has a note beside it (`src/app.md`): read it before editing
the file. Its facts (uses, used by, tests, public API) come from `python tools/notes.py`; its purpose and "Rules and
pitfalls" are written by hand: add the rule or the bug there when you fix one. check_release fails on a stale note.

## Layering (a file only imports from files earlier in this list; check_release.LAYERS enforces it)
constants, obscene, rudeness, problems, deps, syncthing_api, keymap, bundle, standalone -> store -> wordsource / saves / definitions -> syncfiles -> theme, fonts, sizing, ui_style,
ui_motion, smooth, framesync, widgets, errors, startup -> ui_chart, fullscreen, browser, filepicker, shortcuts, tiercolours, syncdialog, review, dealing, sources -> devtools -> app -> tierlist.
- Only UI files import tkinter. `problems.py` is deliberately tkinter-free.
- Every public Store mutator commits before returning. No animation frame may touch the database.
- Worker threads (startup) never touch tkinter.

## Conventions worth keeping
- Light look by default, a dark mode to choose (UI-62; theme.DARK) and tier colours to choose (UI-61). Pastel and
  cutesy, short tasteful animations, no badges, streaks or goals. Read colours from theme when drawing, never copy
  one at import; text on a pastel is the dark ink (theme.ink_on). A new look rebuilds the window in place (App.reopen, take_over).
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
  height, reset it to height=0 and pack_propagate(True), or Tk flips between sizes forever (the definitions
  pane is the exception: its contents are placed for good and its height always set, F-27; never repack them).
- The bottom-right hint lists only keys no on-screen button already shows. Every key comes from `keymap.py`
  (App.keys; UI-48): never hard-code a key or its name in a hint, button or menu; App.apply_keys refreshes them.
- Placing uses the number keys 1-6, not tier letters (the user dropped UI-29). A held key repeats after
  500 ms, then every 250 ms (App._repeat_allowed); tests' key() helper sends a press and a release.
- No ttk.Combobox or tk.Menu popups: they grab input and float over other programs on Linux. Use
  ChoiceButton / DropMenu. To test focus behaviour for real: Xvfb + openbox + xdotool (installed here).
- Colours come from `theme.PALETTE` / `TIER_COLORS`; fonts from `fonts.font(role)` (shared Font objects;
  after resizing them call `widgets.refresh_widgets(window)`). The typefaces ship in src/typefaces (UI-73: Young Serif
  for words, Atkinson Hyperlegible for the rest, loaded for the program only); text keeps to 20 / 12 / 10 pt; their
  line spacing is tightened by tools/make_typefaces.py (the layout is measured in lines). Text contrast about 7:1,
  the ink on any tier colour at least 4.5:1 (UI-76, `theme.contrast`). The dark look is Dusk (UI-77).
- Window sizes come from `sizing.py` (screen- and content-aware). Measure text instead of assuming dpi.
  Main window: what shows = min(zoom, biggest size at which the worst case fits the screen, in 0.1 steps) x grow
  (window bigger than normal, UI-25). Z-1 (asked for): the fit measures every view at once (`App._worst_size`:
  comparing, a duel with its drop-down, the pane at 3 lines open or not) and runs only on a zoom, maximize, another
  monitor or a resize by hand; a tab, the pane, a comparison or a definition only refill the pane
  (`App._fill_pane`). Never re-fit for a layout change. Measure minimum sizes at grow 1. Main and Browse zooms are
  separate and saved; each monitor keeps its own (meta `monitor_zooms`). Maximizing or restoring keeps the text the
  size it shows (F-52, asked for: UI-57's zoom for the maximized window is gone; never re-fit text for it).
- Test speed on a big save (300k-1M words) for anything run per duel or per refresh (`tools/speed_check.py`
  under xvfb-run: a 1M save, dense and sparse; under ~40 ms an action, ~200 ms a Browse sort): a query that sorts a
  whole tier is ~100 ms there, and nothing may build lists that grow with the square of a tier. Read the
  indexes instead (tier+rating, tier+games, partial ones over placed words, ...; check EXPLAIN QUERY PLAN for
  "TEMP B-TREE"). Test both a densely placed save and a sparse one (a few thousand placed of a million): a
  query can be quick on one and slow on the other. Look for orphans
  with vulture (installed here: `python3.12 -m vulture src tierlist.py tools tests`).
- GNOME's window manager can be tried here too: `apt-get install -y mutter`, then under xvfb-run
  `dbus-run-session -- sh -c 'mutter --x11 --replace --sm-disable & ...'` (X11 only; Wayland cannot be recorded).
- New indexes on words go in `store.WORD_INDEXES`; writes of over `BULK_ROWS` rows go through `Store.bulk_write`.
- Tk draws whatever `update_idletasks` lays out: never try sizes on screen one at a time (F-41). Measure once and work
  the rest out, and pin what shows (`DefinitionDrawer.pin`) while measuring.
- After UI changes to layout or fitting, run `tools/stress_ui.py` under xvfb-run (random actions on a small pretend
  screen; fails on errors or a window bigger than the screen).
- Long work on the save (a reshuffle) runs on a worker thread with App.busy set and a moving bar; nothing
  else may write the save meanwhile.
- Keep `deps.PACKAGES` in step with `requirements.txt` (a test checks it); a new package also needs its
  `deps.SIZE`, `PURPOSE` and `HOMEPAGE` entries. The builder (PyInstaller) is in `deps.BUILD_PACKAGES`, not requirements.txt.
- Dialogs: build on `widgets.StyledDialog` (or errors.show_message / ask_yes_no / show_error); no tk
  messagebox. A new window is built withdrawn, placed, then shown with `ui_style.show_drawn` (F-48: drawn
  see-through, so it never appears piece by piece); the main window stays see-through until it settles (App._unveil). The bottom bar's square ttk buttons stay on purpose.
- Errors: raise `problems.SetupError` for fixable problems; plain-language text lives in
  `problems.describe`; the dialog and safety net are in `errors.py` (everything runs inside `run_guarded`).
- Any progress bar with a real percentage must also show an ETA (`startup.EtaTracker` / `format_eta`).
  Long jobs name their main steps first (`constants.plan_line`) for the "Step i of n" corner; keep
  `wordsource.wiktionary_steps` / `queue_steps` in step with the stage lines they predict. pip downloads are
  measured by watching its TMPDIR (`deps.install`); re-measure `deps.DOWNLOAD` if requirements change.
- Screenshots for review: run the app under `xvfb-run`, grab with PIL `ImageGrab` (see git history or
  recreate); show the user pictures for each UI step. Check colours by reading pixel values: the image
  preview can wash out pale pastels.
- Censored (obscene) words: copies of the word side by side over 0.625 letter widths, each line's end letters smeared
  only inward so nothing reaches past the word (F-33, the user's rules) (`widgets.smear_items`, `Unsmear`; un-smears under the pointer; the user picked it from many mock-ups), `constants.mask_word` (b•••••d) only where nothing can be drawn (messages); definitions panes smear it
  (`widgets.smeared_label`; the word un-smears while the pointer is over the pane) and Browse's list too
  (`widgets.TreeSmears` over a blank cell). Route any new on-screen word through `App.shown` / `Store.censored`. Exports keep the real words.
- Package sizes shown in the install dialog (deps.SIZE) were measured with pip; re-measure if requirements change.

## Before handing a round over
Run through `.claude/CHECKLIST.md` and `python tools/check_release.py --tests`; build the zip with
`python tools/check_release.py --zip word-tierlister.zip` (never copy files by hand, that is how files get
missed). Keep README.md and DEVELOPERS.md current in the same commit as the change (the user asked for this explicitly).

## How the user likes to work
- Go step by step through the roadmap; show screenshots for UI steps; do not build unapproved steps.
- Ask questions and show mock-ups of a design or a fix before building it fully (asked for after SY-1 was built
  before its look was agreed): agree the look and the open choices first, then build.
- Finish a step with: tests passing, roadmap ticked, README updated, a short summary.
- Every prompt, before finishing: tidy what was touched (dead code, stale comments and names, leftover
  debug lines, unused imports via pyflakes, scratch files out of the repo), then:
- Last thing on every prompt, after the work itself: update this CLAUDE.md if anything important
  changed (Next, a rule learnt, Known gaps, new files, commands, conventions or user preferences), then commit and
  push it with the rest. A finished step goes in the roadmap, not here. Keep it short; skip it when nothing changed.
- The repo on GitHub is the source of truth for this file; a copy inside an uploaded zip may be older.
- UI styling: keep the bottom bar (Undo, Browse / edit, Definition and the key-hint line) roughly as it
  looks now; modernize the top (the File / Edit / View / Settings menus and the mode switch such as
  "Place new words"). UI-10 does the top; UI-24 restyles dialogs only.
- Ask before changing decisions already settled (see "Decisions" in the roadmap): the light look by default (dark mode lifted "light theme only"),
  "+N today" with the "/hr" rate only on hover, progress bar (UI-14): a bookshelf of spines (zones page,
  chapter, book, shelf, library; height = share placed; colour = median tier blended round the colour wheel;
  the leaning tier in the hover note) with "95% of text" after it, packaging: T-6..T-8 (make a program / back to source as a sync / one command for Linux +
  Windows builds via GitHub Actions) are planned after the UI steps, after ST-5.

## Status
Every step's story (what was asked, what was built, what the user picked) is in the roadmap at the top of
`tierlist.py`: search it for the ID (UI-, F-, T-, OB-, DT-, ST-, U-, SY-, Z-, W-, FS-, S-, IC-). Do not repeat it here.
- Next: the release (Actions > Build programs > Run workflow on main, "Publish as a release" ticked; a session cannot
  push tags, T-17).
- Dropped: UI-21 (next-up peek), UI-74 (film grain), UI-32 (moving background): Tk has no see-through widgets and the
  user ruled out rewriting the page as a canvas. FS-1 (going back from a pop-up means full screen's menu). T-4.
- Shelved ("In consideration" in the roadmap's Decisions): Boundary's swap strip (archived, commit 9b78889; swaps are
  still counted); the user will come back to it.
- Decided: binaries go in GitHub Releases (T-8), not a folder; the placement toast ends in its chart bar (UI-17).
- The "Window by window" list in the roadmap shows which steps touch which window.

## Rules learnt from earlier steps
- A new top-level file must be added to `standalone.TOP_FILES` (F-47: Remove it keeps what the user added).
- Never name a module like a PyPI package (src/ is first on the path: "packaging" broke it).
- Bump `rudeness.RUDENESS_VERSION` whenever the rules change (now 16). The program reads rules only, never the
  review's answers (OB-9); tests never go online (WORD_TIERLISTER_OFFLINE in tests/_paths.py).
- Smears: the user checked 194 words over the commonest end-letter pairs (F-39); add a per-pair spot fix only if one is
  reported.
- Developer tools are bubbles at a dialog's top right, shown only with Settings > Developer tools on (DT-1); a new
  dev tool gets a bubble there and keeps its command. They run tools/ from the source, never from a built program.
- Never remake a canvas item from its own Enter/Leave (F-21: Tk looped and froze).
- Windows lessons from CI (T-20): backslash paths, home from USERPROFILE, no os.geteuid, a hidden window gets no
  <Configure>, Segoe UI wraps differently (check a smear's runs from its layout, not fixed strings).
- macOS is tried only by .github/workflows/macos.yml (T-18): read its failures and screenshots before trusting a macOS
  change. Its runners are slow: hold the animator's clock (`anim.clock`, `_real=False`) or background work (an Event).
- The repository must stay public (updates read its releases; private answers 404). Never change its visibility;
  keep secrets out of it.
- Obscene words: rules only (src/rudeness.py). words.rude = kinds of its meanings (rudeness.KIND_BITS), words.obscene
  = smeared whole. Three kinds are shown (Expletive, Sexual, Slur: obscene.RUDE_KINDS, all smeared to start with);
  the rules score six (obscene.RULE_KINDS) and rudeness.fold turns them into three. A group's own name is never a slur.
  Measure with tools/measure_rudeness.py; ask before building the drafted tighter Clinical rule.

## Known gaps (never seen for real; confirm when the user can)
- Windows, never run on a real machine: the private font loader (UI-73), dpi awareness and monitor work areas (UI-54,
  F-45), the Start menu shortcut (ST-10), the .exe's icon and taskbar group (IC-1), the zoom keys by keycode, the
  FreeConsole fallback (ST-9; pythonw.exe itself is confirmed), renaming the running .exe on update (U-1).
- macOS, never on a real Mac: the .app build (T-16, Apple Silicon only), the terminal hand-back (ST-5), update by
  ditto. README and release notes say so (asked for): drop that once it is tried.
- Linux / GNOME: framesync (F-53) seen under openbox only; IC-3's taskbar icon not seen (no GNOME Shell here); a window
  growing for the pane can show GNOME resizing a frame late (F-28).
- Two monitors: Z-1's monitor check was only faked (one Xvfb screen); Tk 8.6 keeps its size on a monitor with other
  scaling. Absurdly small screens (1366x768 at 2.0 with the pane open) can still clip.
- Releases: the first real update from 1.0.0 (U-1), the nightly rebuild end to end (U-9, try Linux first) and U-3's
  certificate fix in a built program were never run for real. A release needs constants.VERSION bumped.
- Sync (SY-1): tried between two Syncthing 1.27 instances on one Linux machine only; the later change wins by each
  device's clock. Tests never start the real Syncthing.
- Rude meanings read in the background for an old save (App._start_rude_read, a 3 GB download): never tried against
  the real site. The tuner (OB-10) was only run on stand-in answers here (a round: about a minute on 4 cores).
- ST-8's pkexec / winget installs were only faked; a read-only save's dialog could not be checked (tests run as root).
- "+N today" counts from the undo history (~5,000 actions): past that in a day it undercounts.
