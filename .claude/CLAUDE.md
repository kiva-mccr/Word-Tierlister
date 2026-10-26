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

## Notes beside the code
Every code file in the top folder, `src/` and `tools/` has a note beside it (`src/app.md`): read it before editing
the file. Its facts (uses, used by, tests, public API) come from `python tools/notes.py`; its purpose and "Rules and
pitfalls" are written by hand: add the rule or the bug there when you fix one. check_release fails on a stale note.

## Layering (a file only imports from files earlier in this list; check_release.LAYERS enforces it)
constants, obscene, rudeness, problems, deps, keymap, bundle, standalone -> store -> wordsource / saves / definitions -> theme, fonts, sizing, ui_style,
ui_motion, smooth, widgets, errors, startup -> ui_chart, browser, filepicker, shortcuts, tiercolours, dealing, sources -> app -> tierlist.
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
  Main window: what shows = min(zoom, biggest size that fits the screen, in 0.1 steps) x grow (window
  bigger than normal, UI-25); re-fit from the zoom on every layout change, never ratchet down. Measure
  minimum sizes at grow 1. Main and Browse zooms are separate and saved; the main window keeps another for when
  it is maximized (UI-57: `zoom_max`, brought back on maximize / restore), never below the usual one (UI-69).
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
- Censored (obscene) words: copies of the word side by side over 0.625 letter widths, each line's end letters smeared
  only inward so nothing reaches past the word (F-33, the user's rules) (`widgets.smear_items`, `Unsmear`; un-smears under the pointer; the user picked it from many mock-ups), `constants.mask_word` (b•••••d) only where nothing can be drawn (messages); definitions panes smear it
  (`widgets.smeared_label`; the word un-smears while the pointer is over the pane) and Browse's list too
  (`widgets.TreeSmears` over a blank cell). Route any new on-screen word through `App.shown` / `Store.censored`. Exports keep the real words.
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
- Ask before changing decisions already settled (see "Decisions" in the roadmap): the light look by default (dark mode lifted "light theme only"),
  "+N today" with the "/hr" rate only on hover, progress bar (UI-14): a bookshelf of spines (zones page,
  chapter, book, shelf, library; height = share placed; colour = median tier blended round the colour wheel;
  the leaning tier in the hover note) with "95% of text" after it, packaging: T-6..T-8 (make a program / back to source as a sync / one command for Linux +
  Windows builds via GitHub Actions) are planned after the UI steps, after ST-5.

## Status
Done: UI-0..UI-13, UI-15..UI-20, UI-23 (Browse restyle), UI-24 (dialogs), UI-25 (contents grow with the window), UI-27 (focus back after a drop-down), UI-28 (anchor dialog), UI-47 (Tab between tabs), UI-30 (package links), UI-50 (queue Apply: no-change note, moving bar), UI-31 (a view per tab), UI-40 (anchors follow their tier), UI-34 + UI-14 (status line, progress shelf), UI-33 (pace, hover notes), UI-46 (tabs only with work), UI-35, UI-36, UI-43..45 (fixes, zoom), UI-49 (held keys), UI-52 (shelf hover), UI-37 (Space toggles comparing), UI-39 (Delete in Browse), UI-38 (Browse opens complete, like the other windows: no animation of its own; remembers its view), UI-41 (queue shape cards), UI-53 (smooth shapes), UI-54 (Windows scaling, pop-ups on their monitor), UI-55 (shelf marks), UI-42 (themed file picker on Linux), UI-48 (keyboard shortcuts: every key changeable), UI-51 (look up a word from the card), UI-26 (final pass: smoke test, 1M check), UI-56 (definitions pane fits its senses; grows only, back to 9 lines when closed), UI-57 (a zoom of its own for the maximized window), UI-58 (View > Censor obscene words), UI-59 (a rude word's kind faintly above it on the card), W-1 (click a word in a definition: it shows there and waits in Browse to be placed), UI-60 (a duel's definitions side by side), UI-61 (tier colours), UI-62 (dark mode, not the default), UI-63 (the card's label: parts of speech, then the rude kind: "noun · sexual"), UI-64 (turning censoring on says it may not be fully accurate: a note once a save, then a toast), UI-65 ("compound word" in the card's label), UI-66 (a new look rebuilds the window in place: no gap, same spot, Browse kept), UI-67 (a Wiktionary link on each definition, only while online), ST-8 (pip, venv and Python offered like tkinter; git never needed), F-19 (the log: sessions, hard crashes, freezes), IC-2 (Linux: the program file's icon via gio), IC-3 (Linux taskbar icon: WM_CLASS + a hidden launcher), ST-1..ST-4 (terminal: tkinter only; window: a tick box per package), ST-5 (Linux / macOS: the terminal handed back; applications-menu launcher), ST-9 (Windows: restarts with pythonw.exe so the console closes; never a .pyw), ST-6 (How words are dealt: order, kinds of words, censoring), ST-7 (download speed, Step i of n), OB-2 (rude senses smeared in definitions), OB-5 (kinds of rude meaning in How words are dealt), OB-6 (src/rudeness.py: rules from Wiktionary, WordNet when installed, links between words; 78% agreement with Claude's sorting; wired in), T-1 (saves.app_dir: a built program's save beside it), T-2 (tools/bundle.py: English word lists only), T-3 (tools/build.py: Linux build about 25 MB), M-1..M-11 (the mini-roadmap: fixes, Browse column sort, an orphan / speed sweep), SZ-1, R-1 (folders), T-6 (File > Source & Updates: make a program; src/standalone.py), T-7 (unpack the source from the program; a sync), F-1 (main window shown complete: App.open_window), F-2 (definitions pane opens full), F-3 (a form shows its word's meaning), T-8 (.github/workflows/build.yml: Linux + Windows builds on GitHub; a v<VERSION> tag publishes a Release; tools/build.py --all; the update tick), F-4..F-7 (Windows zoom keys, PyInstaller repair, smeared words in panes and Browse, notes beside the code), T-9 (first start offers the other form once), T-10 (the program's first start unpacks its source unless a copy is beside it; starting the other form closes this one), T-11 (clean environment between the forms and for builds; GTK / Qt excluded), T-12 (Clean up behind: a program made from an unpacked source replaces it), T-13 (from source: Update the source only, no build), T-14 (Clean up behind? at every build: keep / zip / remove; only the source's own files go), F-8 (a definition arriving mid-slide), F-9 (review: screens, speed on 1M words, censoring in messages), F-10 (start-up speed: bulk writes, frequencies kept from the ranking, shelf totals kept), F-11 (build: unused packages never packed, missing ones offered before a build), F-12 (smooth un-smear in panes; rudeness v10: forms, slurs that are not the usual meaning, hyphenated parts), F-13 (moving the build across disks; a big build names its biggest parts), T-4 dropped, T-5 (.github/release-notes.md: a short note atop every release on unsigned programs), F-14 (review since F-9: rudeness v12, a meaning refers back to its word only by a whole form), F-15 (a censored word appearing under a still pointer un-smears at once; the kind has its own row: the word under it 85%, the card a little taller), F-16 (the card's search tested: lower-case new words, tidied typing, undo of a looked-up word, the label after typing), F-17 (Browse's search tested; a broad search in a million words 1 s -> under 0.2 s), F-18 (an open dialog re-wraps and resizes when the zoom changes: maximizing cut its text off), F-20 (the definitions pane's opening flicker, back with the Wiktionary link: fixed, tested under openbox), F-21 (a freeze: hovering the card's magnifier looped in Tk; never remake an item from its own Enter/Leave), F-22 (the definitions pane's flicker tracked frame by frame: a growing window hands its room to the pane at <Configure>, animations never leap after a stall, closing leaves the layout first, the opening fit starts from the shown size), T-15 (clean up behind puts the program where the source was, in its folder), F-23 (late window growth added on top of the pane's height), UI-70 (the card's search caret blinks), UI-71 (the censoring note in the window it was turned on in), F-24 (clean up tried for real; .gitignore counts as source), IC-4 (the icon's darker border), W-2 (smeared meanings clickable; a smeared word's meanings un-smear with the pane), F-25 (the form offer's timer never reads a closed save), F-26 (the pane's italics follow a zoom), F-27 (the pane's contents never unmapped: placed for good, height always set), F-28 (a longer definition eases the pane taller, the same way as opening; the user confirmed F-27 worked), F-29 (comparing re-fits when it would not fit; the pane eases shorter), F-30 (zoom limits found while the window is hidden, kept per screen; a refusal only shakes), UI-72 (room for a message under the page), ST-10 (File > Add to Start menu on Windows: a shortcut via PowerShell, pythonw.exe from source), F-31 (tierlist.md, tierlist.py's note, tracked at last; an export never overwrites it), UI-68 (Browse's sort arrow points the way values grow; "Tier" not "Default"), UI-69 (the usual and maximized zooms stay compatible: the usual window never shows more than maximized), IC-1 (the icon: tools/make_icon.py
draws src/icons; ui_style.set_icon on every window; .ico for the Windows program; the Linux launcher's copy),
UI-79 (the shelf's spines one width), UI-73 (typefaces), UI-75 (GitHub link), UI-76 (contrast), UI-77 (Dusk dark mode): the user picked these from two
rounds of mock-ups (a Design canvas artifact, each board beside the real window) and kept buttons, card and labels.
UI-78 (borders: of six slight changes, only softer button and pill edges, widgets.EDGE; the user is attached to the
current style), F-32 (letters reaching past their boxes: smeared and repainted whole), F-33 (smears never reach past
the word: line ends smear inward, the user's rules), F-34 (the definitions pane's scroll bar), F-35 / F-37 (no bar under a smear: its band only between the end letters), F-38 (short letters smear further), F-39 (second letters never over the end letters; the user checked 194 smeared
words covering the commonest start / end letter pairs and found them all good: add a per-pair spot fix only if one is reported), F-40 (the letters' holes filled, gone at
the very start of un-smearing), F-43 (the end letters smear inward twice as far: their holes showed),
F-36 (smear frames cheap again: layout once, one item a copy, one guard). F-41 (switching tabs with the pane open: the fit never draws the line counts it tries (pane pinned, lines worked out from one measurement), the duel tabs share one text size, and their cards fade over to the new pair). Docs reviewed for the first release
(README: Using it, Licence; release notes; code map). T-16 (a macOS program in the release: Apple Silicon, zipped
.app, icon.icns). T-17 (Run workflow > "Publish as a release" makes the tag and the release: a session cannot push tags). F-42 (the Windows build's check hung on the one-file program's inner process holding its pipe: output to files, the whole tree stopped, jobs time out after 30 min). U-1 (File > Check
for updates: the program replaces itself with the release's program, kept as .old until the new one starts; a git
checkout updates with git pull, other source folders sync; a quiet check at start once a day). U-2 (the censoring
toast is the How words are dealt line). U-3 (a built program trusts this computer's certificates: SSL_CERT_FILE from
deps.CA_BUNDLES; the update dialog says what went wrong).
Next: the release (merge this, then Actions > Build programs > Run workflow on main, ticked). Dropped: UI-21 (next-up peek), UI-74 (film grain)
and UI-32 (moving background): Tk has no see-through widgets, and the user ruled out rewriting the page as a canvas.
Boundary's swap strip: the user will come back to it. The "Window by window" list in the roadmap
shows which steps touch which window.
Shelved ("In consideration" in the roadmap's Decisions): Boundary's swap strip (archived,
commit 9b78889; swaps are still counted).
Decided: binaries go in GitHub Releases (T-8), not a folder; the placement toast ends in its chart bar (UI-17).

## Known gaps
- UI-73's private font loading was only tried on Linux (fontconfig); the Windows (AddFontResourceEx, FR_PRIVATE)
  and macOS (CoreText) loaders are written but never run; if they fail the old installed fonts stand in.
- The pane's dip (F-23, F-27) is fixed (the user confirmed). A window that must grow for the pane can still show
  GNOME's compositor resizing it a frame late, and the window's own resize is one step (F-28).
- The Windows console hand-off (ST-9: pythonw.exe) works on real Windows (confirmed by the user); the FreeConsole
  fallback (`startup.detach_console`, no pythonw.exe) was only simulated. ST-5's terminal hand-back was checked on Linux in a pseudo-terminal, not on a Mac.
- UI-54 (dpi awareness, monitor work areas) was only simulated here; confirm on real Windows 11. Tk 8.6 keeps
  its size when moved to a monitor with a different scaling.
- On absurdly small effective screens (for example 1366x768 at 2.0 scaling with the definitions pane
  open) the centre area can still clip.
- Obscene words (OB-6, wired in): rules only (src/rudeness.py), never Claude's list or a review (archived, commit
  233d6ca; old saves keep unused tables obscene_review / kinds). The Wiktionary build keeps the meanings the rules
  read (table rude); prepare_queue scores them ("Scoring rude meanings"); words.rude = kinds of its meanings
  (rudeness.KIND_BITS), words.obscene = smeared whole. A save without the meanings reads them in the background
  (App._start_rude_read: a 3 GB download; never tried against the real site from here, nor on a real old save).
  Censoring smears Crude, Swear, Sexual, Slur only (obscene.CENSORED). "Obscene words" still starts unticked.
  Only words smeared whole get rude kinds ("Obscene words" = censored words; the user chose it); a group's own
  name is never a slur (SLUR_MARKS). Bump rudeness.RUDENESS_VERSION whenever the rules change (now 12; words.rude_main keeps the main kind). Measure with tools/measure_rudeness.py (79.0%, 81.3% of
  the commonest, 0.4% false alarms; forms count as their word's first meaning (F-12); hyphenated parts count on slang meanings; word families replaced the hand list's roots; Wiktionary's examples were tried
  and did not help; forms follow their word's first meaning; common words (COMMON_ZIPF) count only strongly
  labelled rude meanings; borrowed ideas and voting checked on random and held-out lists judged by subagents
  (scratch only): see OB-6). Never name a module like a PyPI package (src/ is first on the path: "packaging").
  Ask the user's examples of false matches.
  Tests never go online (WORD_TIERLIST_OFFLINE in tests/_paths.py).
- IC-2 (gio custom icon) works on Fedora (the user saw it); IC-3 (taskbar) could not be seen here (no GNOME Shell). Earlier:
  IC-2 could not be seen here (no desktop metadata service); confirm on Fedora's GNOME Files.
  ST-8's pkexec / winget installs were only faked in tests.
- ST-10's Start menu shortcut (PowerShell's WScript.Shell) was only faked here: confirm on real Windows that it
  appears in the Start menu, starts with no console window and shows the icon.
- IC-1 on Windows (the .exe's icon, the taskbar group via SetCurrentProcessExplicitAppUserModelID) was never seen on
  real Windows; on Linux it was seen in openbox's title bar.
- The Windows zoom keys are now read by keycode with Ctrl held (keymap.WIN_CTRL_KEYS); not tried on real Windows.
  The PyInstaller.utils error was not reproduced here: the build now checks the parts it uses and repairs an
  incomplete PyInstaller.
- U-3's certificate fix was reproduced from source with the certificates hidden, not in a real built program on
  Fedora or a Mac.
- U-1's self-update never ran against a real release or on Windows / macOS (renaming the running .exe, ditto):
  the first test is updating a 1.0.0 program to the next release.
- T-8's workflow and the update tick never ran against the real GitHub (no gh login here; no release published
  yet). A release needs constants.VERSION bumped and the tag v<VERSION> pushed; the workflow button needs it on main.
- The user's Linux build is about 25 MB now (it was 99 MB before T-11 excluded GTK and Qt).
- T-16's macOS job (macos-latest, ditto zip, icon.icns) never ran: the first release is its first build; Intel Macs
  get no program.
- T-3's Windows (.exe) and macOS (.app) builds were never tried (PyInstaller builds only for the system it runs
  on; this container is Linux). The macOS build is an app bundle (--onedir).
- A read-only save file's dialog could not be verified (the test machine ran as root).
- Holding a key in Refine once crashed the user's PC; after the two fixes (Boundary's pair list, held repeats wait
  after a slow action) the user no longer sees it.
- "+N today" counts from the undo history, which keeps the last ~5,000 actions: past that in one day it
  undercounts.
