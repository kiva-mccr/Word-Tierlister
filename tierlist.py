#!/usr/bin/env python3
"""
Word Tier List
==============
Tier-list every word in the English dictionary (S / A / B / C / D / F).

Setup (once; the first start also offers to do it):
    pip install -r requirements.txt
Run:
    python tierlist.py
    python tierlist.py --db mylist.db            # use a different save file
    python tierlist.py --wordlist words.txt      # custom word list (first run only)

How it works
------------
* Words come from English Wiktionary (every lowercase word, inflections included,
  roughly a million) and ranked by how common they are (wordfreq).
* The queue is a seeded random order, not a strict frequency order: a word's odds
  of coming up early fall off exponentially (or gaussianly) with its frequency
  rank, and compound words ("bookshelf", "well-known") are pushed further back.
  Same seed = same order. Change it under Settings > How words are dealt (or
  --seed N), where "Most common first" is a strict frequency order instead, and
  kinds of words (nouns, verbs, ..., obscene words and each kind of rude meaning) can be
  left out of the queue. Censor obscene words there smears them sideways until the pointer
  is over them, and their rude meanings in the definitions.
  The first start asks these in three short steps. (--source wordnet gives a
  smaller ~77k list instead.)
* Your progress lives in a save file (tierlist.db) that is written after every action.
  When you replace tierlist.py with a newer version, even in a different folder, the
  new one finds your earlier save automatically (the one used last time, or the one with
  the most progress), so words you've already done stay done. If progress got split
  across several saves it offers to merge them; File > Import earlier progress merges
  another save file or an exported list (.csv/.txt/.md) any time.
* The main window's contents grow with it: make it bigger (or maximise it) and the
  word card, pills, buttons and text grow too (up to 1.75x); View > Zoom sets the
  size you start from.
* Browse window (View menu): text and rows scale with the window; Ctrl +/-/0 or
  Ctrl+mouse-wheel zoom; rows load as you scroll, so there is no row limit. Click a column
  heading to sort by it (again: the other way round); Delete unplaces the selected word.
* Tab / Shift+Tab move to the next / previous tab.
* PLACE mode: type 1-6 to drop a word straight into a tier, or press Space to
  place it by comparing against one anchor word per tier (about 3 questions);
  Space again stops comparing, Backspace steps back one answer.
  "Don't know / later" (U) sends a word to the back of the queue; skipped
  words come back after every fresh word has been handled. The magnifier on the
  word card (or /) looks up any word to sort it now, and adds one the list lacks.
* REFINE mode: head-to-head duels between words in the same tier (Elo ratings,
  fewest-duels-first, nearest-rating opponents) to order words within a tier.
* BOUNDARY mode: duels between the weakest word of one tier and the strongest of
  the next; if the lower-tier word wins, the two swap tiers.
* CONFLICTS: if a new answer contradicts earlier ones (A>B, B>C, then C>A) the
  pair is flagged; re-judge them in "Resolve conflicts".
* Under the status line, the progress shelf: book spines from the commonest words
  to the rarest (zones page, chapter, book, shelf, library), each filled by the
  share of its words placed and coloured by their median tier, then how much of
  everyday text the placed words cover ("95% of text").
* Tabs have their own little view at the top right: the tier chart (Place), how
  settled each tier's order is (Refine), and the number of conflicts (Conflicts).
* A mode's tab only shows once it has work (Refine: a tier with two words;
  Boundary: two neighbouring tiers with words; Resolve conflicts: a conflict).
* Every action is committed to SQLite immediately: close the window or lose
  power and nothing is lost. Undo (Ctrl+Z) survives restarts too.
* Press D any time to show the dictionary definition next to the word(s).
* Every key can be changed under Settings > Keyboard shortcuts (the keys above are the defaults).

Code map (run tierlist.py; it stays at the top of the folder, next to your save. The modules below
live in src/, the self-tests in tests/, the developer's tools in tools/ (check_release, layout_trace, build,
measure_rudeness, notes), the Claude notes in .claude/; each code file has a note beside it (name.md: read it
before editing the file); the README has the same map with more detail)
----------------------------------------------------------------------------------------------
    tierlist.py     entry point: command-line options, start-up sequence, main(). Re-exports
                    the pieces below so `import tierlist` keeps working for the self-tests.
    constants.py    tier names, modes, ranking defaults, the queue's curve.   (no dependencies)
    obscene.py      the kinds of rude meaning, Wiktionary's rude labels, a short hand-picked list (no tkinter).
    rudeness.py     how rude each meaning is, by rules: points from labels, topics, wording, WordNet, links
                    between words; what a word's scores lead to (OB-6; no tkinter).
    keymap.py       the keyboard shortcuts: every action's keys, the user's changes on top (UI-48; no tkinter).
    problems.py     plain-language error text, SetupError, log helpers (ST-2; no tkinter).
    deps.py         required packages: detect and install them; the terminal stage (ST-3, ST-4; no tkinter).
    bundle.py       the data a built program carries (T-2: English word lists only; no tkinter).
    standalone.py   the program and its source: manifest, PyInstaller build, unpack / sync (T-3, T-6, T-7; no tkinter).
    store.py        Store: the SQLite save file. Tiers, Elo duels, undo history, queue order,
                    conflicts, merging. Every change is committed immediately.
    wordsource.py   building the word list: WordNet, Wiktionary download/parse, compound
                    detection, queue preparation.
    saves.py        where the save lives (app_dir, T-1), finding your earlier save, remembering it, exporting.
    definitions.py  Definitions: WordNet offline, dictionaryapi.dev online, cached.
    theme.py        colour palette (UI-1).            fonts.py     typography (UI-2).
    sizing.py       window sizes from the screen and the contents; monitors; Windows display scaling.
    ui_style.py     ttk / tk styling (UI-3).          ui_motion.py easing, colour blend, Animator (UI-4).
    smooth.py       soft-edged rounded shapes, curves and icons drawn as images (UI-53).
    widgets.py      RoundButton, the word card, tabs, messages, dialogs and the other small widgets.
    errors.py       friendly error / message / question dialogs, error handlers, run_guarded (ST-2).
    startup.py      first-run progress window; runs set-up on a worker thread (ST-1).
    ui_chart.py     each tab's view at the top right (the tier chart...) and the progress shelf.
    browser.py      Browser: the Browse / edit window.
    filepicker.py   the app's own Import / Export file choosing on Linux (UI-42).
    shortcuts.py    Settings > Keyboard shortcuts... (UI-48).
    dealing.py      Settings > How words are dealt... and the first start's three steps (ST-6).
    sources.py      File > Source & Updates...: make a standalone program; in the program, unpack its source (T-6, T-7).
    app.py          App: the main window and all modes.

Layers: constants, obscene, rudeness, problems, deps, keymap, bundle, standalone -> store -> wordsource / saves / definitions -> (UI) theme, fonts,
sizing, ui_style, ui_motion, smooth, widgets, errors, startup -> ui_chart, browser, filepicker, shortcuts, dealing, sources ->
app -> tierlist. Nothing lower imports anything higher, and
only the UI layer imports tkinter, so the core runs and is tested without it.
"""
# ==========================================================================================
# UI OVERHAUL ROADMAP  ([x] built, [ ] planned, [-] on hold, [?] tentative idea, not planned)
# ==========================================================================================
# Goal: a modern, minimalist UI with a soft pastel charm, where sorting feels good to do so the
#       list actually gets finished. Tasteful motion, zero pressure.
#
# Guardrails (promises, not suggestions)
#   - NO badges, streaks, levels/XP, daily goals, leaderboards, reminders/notifications,
#     "don't break the chain" copy, surprise rewards or guilt messages.
#   - No pace pressure: the session count stays but is small and muted, and the "/hr" rate only
#     appears in a hover tooltip on the count (UI-15). Nothing on screen tells you to hurry or
#     compares you to yesterday.
#   - Satisfaction comes from speed, clarity and smooth feedback, not from psychological hooks.
#   - Motion: every animation <= 250 ms with ease-out; it never blocks input (pressing the next
#     key makes running animations speed out of the way within 90 ms while the new one starts on
#     top; changed by request from "finishes instantly"); nothing loops or moves while idle; and
#     View > Reduce motion turns all of it off (UI-4).
#   - No sound by default.
#
# tkinter constraints that shape the plan
#   - No real transparency or anti-aliasing: "fades" are colour blends toward the background,
#     rounded corners are smoothed Canvas polygons, shadows are a slightly darker offset shape.
#   - Animation = root.after() at ~60 fps with easing. Per-frame work must be tiny and must never
#     query the database (the list can hold ~1M words).
#   - Fonts cannot be bundled in one file: pick the nicest installed family, fall back gracefully.
#
# How we work: one step at a time. Each step adds one small function or class, can be checked
# on its own, leaves the app working, and updates the tests that read the widgets it replaces.
# Tick [x] as steps land. IDs are stable; the order is a suggestion.
#
# Suggested order: the start-up phase (ST-1..ST-4; all done) came first by request, then the new look
# + chart + the satisfying drop:
#   ST-1, ST-2 -> UI-5..7 -> UI-13 -> UI-16, UI-17 (UI-0..4 are already built)
# Added later, in this order after the UI steps: ST-5 (Linux terminal, done), ST-6 (how words are dealt, done), then
# T-1..T-3 -> T-6, T-7, T-8. First of all: the mini-roadmap M-1..M-11 below. Last of all: IC-1 (the icon, done).
#
# --- Now: mini-roadmap (asked for: finish these before anything else, in this order) ----------------
# [x] M-1  Zoomed all the way in, thin lines show along the top and bottom of the tier pills (Linux and
#           Windows). Cause: the pills' corner radius is more than half their width, so in Tk's outline recipe
#           the top's two tangent points pass each other and the outline ran back and forth along the top,
#           past where the corners' curves leave it: no fill, but its hairline showed, longer the bigger the
#           zoom. Fixed: smooth._straighten cuts each straight stretch of the outline down to its two ends
#           (the fill is unchanged, so the rounded-square look stays).
# [x] M-2  The word flying into the chart leaves what looks like a little white square on top of its bar
#           (Linux and Windows). Cause: the flying drop is a tiny opaque window (tk has no transparency), and it
#           landed centred on the bar's top edge, crossing bars on its way in a straight line, so its page-
#           coloured corners covered them. Also its landing point was measured while the bar was still
#           growing, so a bar grew up into it. Fixed: the drop rises just above the tallest bar
#           (DistributionChart.bars_top), crosses, and drops onto its own bar from above, stopping just above
#           it; the landing point is the bar's final height. Checked frame by frame: no overlap with any bar
#           for every tier at 100% and 200% in two window sizes.
# [x] M-3  Shelf marks (UI-55): on hover the triangle rises with its spine and gets clipped at the top. It
#           should move only a hair (or not at all), never past the band (any zoom, Linux and Windows).
#           Fixed: a mark sat 2 px under the shelf's top and rose the spine's whole lift (~6 px); now it rises a
#           quarter of it, at most the 2 px of room above it (Bookshelf.MARK_LIFT / MARK_ROOM).
# [x] M-4  Shelf marks take the tier colour of their word (a deeper shade so they show on the pale
#           background). Two words in one spine with different tiers: one triangle, split in two halves.
#           Built: Bookshelf.mark(spines, tiers); ui_chart.mark_color (the tier pastel 30% toward the text
#           colour); SmoothCanvas.triangle_image(w, h, fill, right) draws the split one (left word on the left).
# [x] M-5  Browse / edit opening (UI-38) bounces as the rows load in (Linux only): the rows' arrival must
#           not change the window's size or position during or after the ease.
#           Cause: on X11 every step of the size ease re-lays out the whole window while the window manager
#           redraws its frame a beat behind, and the rows popped in after it. Fixed: on X11 Browse loads its
#           rows before it is first drawn and opens complete and still (Browser.EASE_OPEN, automatic); Windows
#           and macOS keep the ease. Checked under openbox: the first frame is the full window, ~100 ms.
#           Then (reported on Windows too: "it bounces weird"): no size ease anywhere. Browse stays hidden while
#           it is built, placed and filled, then appears complete in its place and only fades in (150 ms, where
#           the system can fade a window; at once with Reduce motion). Browser._open; the window never resizes.
#           Then (reported: it opened unlike the other windows, really fast): no fade of its own either. A
#           see-through window gets no system opening animation (Windows 11 has one for every window), so Browse
#           now simply appears, complete and placed, the way the dialogs do.
#           Then (reported: it showed while its text was still settling to the right size): the text size is
#           worked out from the size it is about to open at (Tk reports 1x1 until a window is shown, so the
#           standard size was used), the first size after it appears is taken at once instead of 80 ms later,
#           and every pending layout and redraw finishes while it is still hidden.
# [x] M-6  Ctrl+0 always says "Zoom 100%", even when the zoom is already 100% (the main window and Browse).
#           Built: App._say_zoom also when nothing changed (any zoom key: zoom out at the smallest says 60%);
#           Ctrl 0 is paced like Ctrl + / - (App._zoom_key). Browse had no zoom message at all: it now shows
#           "Zoom N%" (its own zoom against the 12 pt text) at the bottom of the definition pane (Browser._say_zoom),
#           and gained Ctrl + keypad 0.
# [x] M-7  Browse: click a column heading (Word, Tier, Duels...) to sort by it, the Sort drop-down following;
#           click the same heading again to flip between top-to-bottom and bottom-to-top (a small arrow
#           on the heading shows which).
#           Built: Tier = Default (S..F, by rating), Word = A-Z, Rating, Duels (new Sorts: highest first),
#           Freq # = Frequency (Browser.COLUMNS, sort_by); Store.list_words(reverse=) turns the whole order round;
#           the arrow points up when the values rise down the list; the direction is kept with the view (UI-38).
#           Then (asked for): the Word heading also says "(A-Z)" or "(Z-A)" beside its arrow; and the arrow fills
#           like a loading bar the moment a heading (or the Sort drop-down) is clicked, top down for a down arrow,
#           bottom up for an up arrow, over 260 ms while the rows load (whole at once with Reduce motion). It is a
#           soft image now (smooth.arrow_image), set just after the heading's text (Browser._show_sort; the
#           heading style uses a Label element, as the theme's own put an image at the far right of the column).
#           Fixed (reported: the Word one went pale to full after a pause, no slide): on a save with a few
#           thousand placed out of a million, A-Z / Z-A walked every word in order to find the placed ones (~200
#           ms), freezing the fill. Two small indexes over the placed words only (idx_placed_word / _rank) make
#           every sort < 5 ms there; and the arrow now shows pale at once, the rows load, then it fills, so a slow
#           load can never make it jump.
#           300k words: Rating / Duels ~50 ms a page (Default is ~85 ms).
# [x] M-8  Import / Export dialogs (UI-42, Linux): the Places icons (Home, Documents, Downloads, Next to your
#           save) sit too close to their words and are mixed styles. Drawn icons in one style, with room.
#           Cause: they were text characters, each from whichever font had it. Now smooth.ICONS (house, monitor,
#           page, arrow into a tray, folder, book), drawn soft-edged and see-through by SmoothCanvas.icon_image;
#           in FileList the icon and the room after it grow with the text. The path's first step reads "Home".
# [x] M-9  Export dialog (UI-42): the Name / As / In rows are too close together; more room between them.
#           Done: ~0.4 of a line above and below each row (it grows with the text).
# [x] M-10 Import dialog (UI-42): check the spacing of the first two lines of text (the intro and "Found on
#           this computer"); change it only if it is off.
#           Checked: the two lines are one intro paragraph wrapped at the dialogs' usual width, normal line
#           spacing, the break between its two sentences; the gap under the title matches every dialog. Left.
# [x] M-11 Check and verify (asked for, last of the mini-roadmap): look through the whole program for orphaned
#           code (functions, methods, constants, tags, options and test helpers nothing uses any more, stale
#           comments) and substantial inefficiencies (per-frame or per-duel work that grows with the save, repeated
#           queries, images or fonts rebuilt needlessly); remove or fix what is found, measure on a big save.
#           Orphans (vulture + greps; the layering checked by script: clean): removed App.apply_queue_settings
#           (the dialog has its own; the test now checks parse_queue_settings), theme.contrast / _lum, curve_rows'
#           bg_alpha, and dead test code (an always-false branch that never ran, unused helpers and variables,
#           stale imports). Kept on purpose: the small "(for tests)" helpers (smooth_image, possible, tab_x,
#           show_at, is_running) and Store.swap_counts (the shelved swap strip reads it). The module docstring's
#           code map and layers were out of date (no sizing, smooth, ui_chart, filepicker): brought up to date.
#           Speed, 300k words / 90k placed: a Refine duel 75 -> 35 ms, a Boundary check 92 -> 27 ms, switching tab
#           78 -> 32 ms, opening Browse ~200 -> ~145 ms; placing stays ~25 ms; animation frames median 0.6 ms,
#           worst 7 ms, no queries. How: a (tier, rating) index (idx_words_tr; built once on the next open, ~0.2 s
#           at 300k) so the nearest-rated opponent is read up and down the index (Store._nearest) instead of
#           sorting a whole tier, and the least-dueled seeds tier by tier; tier_counts counted once per change
#           (keyed on the connection's total_changes); the shelf redraws only its marks for a new duel; Browse
#           loads 1,000 rows a page, not 3,000. The one-off test failure did not come back (7 full runs since).
#
# --- Fixes (asked for, after T-7) -------------------------------------------------------------------------------
# [x] F-1  Opening the program, the window stays hidden until it is fully loaded in (no half-drawn or resizing
#           window on the way), then appears complete, as Browse and the dialogs already do. App.open_window:
#           built, sized and filled hidden, then shown and drawn at once while see-through (-alpha, where the
#           system has it), then made visible. It used to show a blank frame for 150+ ms, its widgets popping in.
# [x] F-2  The definitions pane opens as large as it can on the screen (it opened smaller than there was room for).
#           The cause: folded, the pane unmapped its text, which then could not say how many lines it needs, so
#           it opened at its usual 9. Folded, it is now placed (clipped) instead: at 1920x1080, 9 -> 16 lines.
#           Then (reported): in a window made bigger (contents grown, UI-25) it slid open at full height over the
#           word card and tier buttons: the grown window's quick fit counted the folded pane as 1 px. It now counts
#           it at its full height and shortens it until the rest fits, keeping the grown size (_fit_window).
# [x] F-3  A meaning that only names another word ("Alternative spelling of jail", "plural of colour", "Clipping of
#           homosexual") shows that word's own first meaning on a muted line under it, in the main window's pane
#           and Browse's (definitions.form_target / main_sense; looked up like any word; smeared while censoring).
# [x] F-4  Zoom keys on Windows (reported: they did nothing there). With Ctrl held, the key name Windows' Tk reports
#           for =, -, 0 and the keypad's + / - depends on the layout; keymap.event_spec now reads those by their
#           virtual-key code on Windows (WIN_CTRL_KEYS); keymap.spec_of reads every key event the same way (it
#           replaced three copies). Not tried on real Windows.
# [x] F-5  Making the program failed with "No module named PyInstaller.utils" (reported). A half-installed
#           PyInstaller passed the "import PyInstaller" check: the check now imports what a build uses
#           (standalone.PYINSTALLER_CHECK), an incomplete one is reinstalled, and pip and PyInstaller run from a
#           neutral folder (one the program was started from could shadow a module). Not reproduced here.
# [x] F-6  Censored words smeared, not b•••••d, in the definitions panes and Browse's list (asked for): the panes
#           draw the word with widgets.smeared_label and it un-smears while the pointer is anywhere over the pane;
#           Browse leaves the cell blank and lays the smeared word over it (widgets.TreeSmears; clicks, double-
#           clicks and the wheel go on to the list). Messages keep b•••••d (text only).
# [x] F-7  Less to read, less to break (asked for): a note beside every code file (name.md: purpose, uses / used
#           by / tests / public API generated by tools/notes.py, rules and fixed bugs by hand); check_release fails
#           on a stale note and on an import against the layers (LAYERS). Repeated code made into helpers:
#           Store.meta_number (five copies of read-a-number-setting), App.flash(kind=...) (nine colour pairs),
#           StyledDialog.text, Browser._set_size / _row_height, DistributionChart._ease, App._word_to_act_on.
#           The tests' temporary folders now go in one folder per test, removed at its end (tests/_paths: they
#           had filled the disk); tools/layout_trace.py stays offline.
# [x] F-8  A definition arriving while the pane slides open (an online lookup, WordNet) was fitted against the
#           half-open pane and left it taller than fits, over the word card (found as a flaky _selftest_sizing,
#           the same look as the report fixed in F-2's notes). App._fit_defs settles the slide before fitting.
# [x] F-9  A stringent review (asked for: file by file, the UI first; optimised, robust on every screen, bug free).
#           Measured first: the main window on 11 screens x zoom x grown x tab x definitions pane, every dialog and
#           Browse on 7 screens, speed on a 1M-word save (300k and 3k placed), the layout-jitter trace, and a
#           random-action run (keys, tabs, resizes, Browse, dialogs, censoring). Found and fixed:
#           - a big zoom on a small screen clipped the word card (the fit stopped at half the zoom, not half the
#             normal size); Keyboard shortcuts ran off a small screen (its cards now wrap to a second row);
#           - dialogs opened on the pointer's monitor, not their window's, and the main window fitted itself to
#             the pointer's monitor (sizing.monitor_box); a dialog that grew could run off the screen (refit);
#           - speed with a million words: opening 6.2 -> 0.9 s (WordNet is read at the first lookup, not at start),
#             a placement 129 -> 31 ms, a refresh 75 -> 12 ms (tier counts kept up to date, the skipped count
#             from its own index), a Refine duel 93 -> ~40 ms (seeds without sorting a run, settled shares by the
#             smaller side), unplace 75 -> 1 ms, Browse's sorts and filters up to 0.9 s -> under 0.17 s (an index
#             per order, named), How words are dealt's counts 0.5 -> 0.08 s. Nine new indexes: built once on the
#             first open of an existing save (3.7 s for a million words; the file grows ~45%);
#           - censored words shown whole in duel messages, "Finished refining" and two Browse messages;
#           - closing during a reshuffle shut the save under the worker (it now waits); timers left at quit;
#           - an animation whose widget was closed meanwhile raised an error dialog (ui_motion drops it).
# [x] F-18 Reported: maximizing the main window with a dialog open (here "Make this a standalone program?") made the
#           dialog's text grow with the maximized window's zoom (UI-57) inside a dialog that kept its size: cut off,
#           until the window was restored. Chosen (the usual way: apps whose zoom is the whole app's text size, and
#           the systems' own display scaling, resize open dialogs to fit): the dialog follows. After a zoom,
#           refresh_widgets has every open StyledDialog re-wrap its lines in proportion, size itself to its contents
#           again and centre over its window, kept on its monitor (StyledDialog.rescale).
# [x] F-17 Testing Browse's search (asked for): a script typed into the real box (under a window manager) and tried
#           capitals, spaces, accents, apostrophes, % and _, no match, a censored word, every Show and Sort both ways,
#           paging, the selection, closing mid-typing and reopening, and the keys (digits and Delete typed there stay
#           text; the main window does not hear them): all right. One real fault, speed: a broad search in a million
#           words took about 1 s (each pause in typing runs one). The count of matches read the whole table (0.87 s):
#           it now reads the words' own index, as the rows do. And a search matching many words (one letter) reads the
#           sort's own index and stops after a page (Store.SEARCH_WINDOW) instead of sorting every match, where that
#           index leads straight to the rows (All placed, Unplaced, a tier in its Default order). Measured, the
#           query alone: worst 1,043 -> 179 ms dense, 347 -> 110 ms sparse; the same rows as the plain way in 800
#           combinations on both million-word saves (and a test of its own); tools/speed_check.py times searches now.
# [x] F-16 Testing the card's search (asked for: UI-51, the magnifier / "/"), a script drove it through capitals, new
#           words, spaces, odd characters, placed and censored words, undo, tab switches, buttons and menus. Fixed:
#           - a new word typed with capitals was added as typed ("Zorp"), and then "zorp" was added again: new words
#             are lower case, like the list;
#           - runs of spaces did not find a phrase ("ice  cream"), and a "word" of only an emoji or a zero-width space
#             could be added: what is typed is tidied (constants.typed_word; Browse's search box too) and must hold
#             a letter or a number ("Type a word" otherwise);
#           - undoing the placement (or skip) of a looked-up word sent it back into the queue: it comes back onto the
#             card;
#           - Edit > Undo while typing left the card in typing mode with the typed text hidden, and after Escape the
#             card's label (noun · verb) was gone: a word set on the card while typing is kept for afterwards.
#           Not a bug: typing while a reshuffle writes the save cannot happen (its dialog holds the input).
# [x] F-15 Asked for: a censored word that appears under a pointer already resting on it (the word card, a duel
#           card) un-smears at once; before, the pointer had to move a little first (no motion, no event).
#           WordCard.set checks where the pointer is (_pointer_check, after drawing); RoundButton un-smears a new
#           word while it is hovered. The outgoing word still leaves as its smear.
#           Also reported: the smear sometimes covered the kind above the word. The outgoing word's smear (its cut-off
#           strips are the height of its line, in the card's colour) slid up over it on a skip, drawn on top: the
#           kind is now always on top of the card's smears. Then (screenshots: the kind was crammed against the card's
#           edge, the smear of tall letters just under it) the user asked for a little of both: a word with a kind is
#           drawn at KIND_SCALE (85%) of its size and every card has KIND_ROOM (0.9 of a sub-line) more for the
#           kind's row, paid partly from the top and bottom padding (0.28 -> 0.2 of a line) so a 1366 x 768 laptop
#           keeps its 110% zoom step: the card is 1-2 px taller, the kind near the sub-line's size, KIND_GAP clear of
#           the tops of the letters (9 px at 60% zoom, 14 at 100%, 24 at 160%).
# [x] F-14 Review of everything since F-9 (asked for), file by file: one defect, two nits.
#           - rudeness (RUDENESS_VERSION 12): in a word smeared whole, a meaning "naming the word itself" matched any
#             word that merely began with it ("pom: ... pomegranate juice", "jock: a disc jockey", "lav: lavalier
#             microphone", "homo: homogenized milk" were smeared); now only the word with an ending (_refers_to)
#             does; checked over every entry: 11 words change, all for the better;
#           - a missing blank line in widgets.TierChip, an extra one in ui_chart.
# [x] F-13 Reported: making the program stopped at "Putting it in place" with "[Errno 18] Invalid cross-device link"
#           (the temporary folder on another disk than the project): the build record is moved with shutil.move,
#           which copies across disks, like the program itself. The same build was 99 MB (22 MB here): a build over
#           BIG_MB now names its five biggest parts in the log (standalone.biggest_parts), to see what was pulled in.
# [x] F-12 Reported: the definitions' un-smear looked bold before snapping to the word; boys, teeth, boots, stones, nuts,
#           bits, fairy, apples, bum, mayo, hyper, taco, jewels smeared whole; a word that is a slur at all smeared
#           whole; "skull-fuck"'s noun meaning not smeared; asked for: test a hyphenated word's parts.
#           - smear_items: one copy per whole pixel (copies on one pixel stacked up: 46% more ink than the word on
#             small text), and the side copies fade into the paper by half a pixel apart, under a middle copy drawn
#             last: the last frames end on the plain word (measured: 73 -> 74, was 108 -> 74).
#           - rudeness (RUDENESS_VERSION 10): a form or clipping counts as its word's first meaning instead of being
#             left out (that made the slang after "plural of boy" the first meaning); a gloss of over FORM_WORDS words
#             is never a form ("fairy: a mythical being of human form ... of"); a WordNet tie goes to the clean
#             meaning ("taco"); a childish meaning softens what its links bring ("bum"); on a common word a hedged
#             label never smears it whole ("what the hell"); "condom" only as a whole word ("condominium"); words
#             given as examples ("such as ... semen") do not count ("goo"); in a word smeared whole, a meaning naming
#             the word itself is smeared ("an instance of skull-fucking"); a hyphenated word with a rude part makes
#             its slang meanings rude (parts_kind; measured on every hyphenated word: one rude part of two is about
#             as telling as two of two once only slang meanings take it; "two of two, one of three" alone caught 4
#             words, any rude part 46, nearly all right: piss-taker, tight-arsed, short-arse).
#           Measured: 78.7 -> 79.0% the same outcome as Claude's sorting (commonest 80.7 -> 81.3%), words wrongly
#           smeared whole that should show 127 -> 76, false alarms 0.4% (unchanged). 799 words are no longer
#           smeared whole (ordinary words with a slang meaning, euphemisms: girls, make love, pass water, gosh),
#           120 newly are (forms of rude words, rude compounds: doggy-style, gloryhole, nobhead, piss-taker).
# [x] F-11 Making the program on Windows failed (reported: PyInstaller's matplotlib hook, "No module named 'PIL'").
#           - nltk mentions matplotlib, numpy, scikit-learn and others it uses only for charts and maths; PyInstaller
#             packed whatever of them was on the computer, and a broken one (matplotlib without Pillow) stopped the
#             build. They are never packed now (bundle.UNUSED, a test runs the program with them blocked); the
#             Linux build went from 23 to 22 MB.
#           - Before a build, what it needs (PyInstaller, wordfreq; nltk optional) is checked, and anything missing
#             is offered in one dialog, a tick box each, as on the first start (SourceDialog.packages_ready,
#             startup.ensure_packages; deps.BUILD_PACKAGES); a required one left out says why nothing was made.
# [x] F-10 Start-up speed (asked for, after a measured list of what was left). On a million words:
#           - big writes take the words table's indexes away and build them once afterwards (Store.bulk_write,
#             WORD_INDEXES): saving a million new words 19.3 -> 12.6 s; the reshuffle also sets aside the second
#             index holding the queue keys (F-9 had added it), about a quarter faster (16.6 -> 12.3 s averaged; this
#             machine's timings swing +-30%); Browse skips an index name while a reshuffle has it away (_hint);
#           - a Wiktionary build stores each word's frequency as it ranks them: "Looking up how common" (6-11 s)
#             is gone from the first run; its kinds are saved in the same pass, before the indexes come back;
#           - the progress shelf's totals (words per spine, their frequency) are counted once and kept in the save
#             (meta shelf_totals, counted again when words or frequencies change); its placed words come from
#             idx_placed_shelf (replaces idx_placed_rank): 0.3-0.45 s -> 6-8 ms on every start of a sparse save.
#           A first run from a made-up million-entry download, after the download: 89.6 -> 72.1 s.
#
# --- Phase S: start-up experience (first run and errors, in the window instead of the console) ----
# Why: today the first-run progress (the 3 GB Wiktionary download, parsing, compound detection,
# shuffling) and every start-up error are print() / sys.exit() messages in a terminal. Anyone who
# double-clicks the program, or runs it without a console, sees nothing for several minutes, or
# sees it close silently. Both steps are useful even if the program is only ever run as a script.
# [x] ST-1  First-run window. adds startup.py with StartupWindow(title) and run_with_progress(
#           work, title): the long set-up jobs (build_wiktionary, build_word_list, prepare_queue,
#           reshuffle) run on a worker thread while a small window shows the current stage, a
#           progress bar when the size is known (download %, entries parsed) and a plain-language
#           line ("one time only, about 5 to 10 minutes; closing is safe, it resumes"). The
#           existing log=print callbacks feed it through a thread-safe queue, so wordsource.py and
#           store.py need no UI code. Closing the window stops cleanly: downloads already resume
#           from their .part file and parsing restarts from the saved stage. No animation beyond
#           the bar; honours Reduce motion. Console output stays when a console exists.
#           Built: the window appears only if set-up takes longer than 0.4 s (normal launches
#           never flash it); if the window itself cannot be drawn, set-up still completes.
#           Refinements after first real use (Windows): the bar is always visible, starting at 1%
#           with "Initializing download..."; every stage shows a stand-in detail line instead of a
#           blank; parsing reports a real percentage (bytes read / file size) for the plain .jsonl;
#           on Windows the console window behind the app is closed once the program starts
#           (startup.detach_console; --console keeps it), messages go to tierlist.log next to the
#           save, and failures show a dialog (startup.run_guarded: a small first slice of ST-2).
#           Every bar with a real percentage also shows a time-left estimate (startup.EtaTracker /
#           format_eta: "estimating time left..." first, then e.g. "about 6 min left"); sweeping
#           stages have no estimate because their length is unknown. Any future bar (UI-14 if it
#           is built) must use the same two helpers.
# [x] ST-2  Friendly errors. adds problems.py (no tkinter: SetupError, describe(exc) -> plain-language
#           headline + advice for a full disk, no internet, a busy or damaged save file, missing
#           permissions...; log helpers) and errors.py (show_error: a styled dialog with Show details
#           and Copy details; install_handlers: Tk callback, main-thread and worker-thread errors go to
#           tierlist.log and the window's own errors show one dialog, "your progress is saved", with
#           repeats suppressed; run_guarded: the whole program runs inside it, with or without a
#           console, so a SetupError, a sys.exit("message") or a crash ends in a dialog and a log entry,
#           while closing the set-up window stays silent). The sys.exit("...") paths in wordsource.py
#           and main() became SetupError messages that say what to do next; a failed export uses the
#           same dialog. Only "tkinter is not installed" still prints to the terminal: without tkinter
#           there is no way to draw a dialog. startup.py lost its own copies (fatal_dialog etc.).
#           A hidden --crash-test option raises a fake bug 3 s after start so the dialog (and the
#           fact that the program keeps running) can be seen on purpose.
#           Covered by _selftest_errors.py.
# [x] ST-3  Missing packages are offered for install. adds deps.py (no tkinter: PACKAGES table kept in
#           step with requirements.txt, missing(), install() = `python -m pip install` with pip's
#           output streamed as detail lines) and startup.ensure_packages(root, names): only when
#           something is missing it asks "Install now / Not now", then installs behind the usual
#           progress window and carries on without a restart. "Not now" lets the program continue
#           (whatever really needs the package explains itself later); a failed install, no pip, or a
#           system Python that forbids installing (externally-managed) raises a SetupError saying
#           what to do instead (for example make a virtual environment). wordfreq is checked on
#           every start; nltk (offline definitions, optional) is offered in the same question, and a "Not
#           now" to an optional package is remembered in the save (meta declined_packages) so it is not
#           asked again; it is required only when --source wordnet builds a list. The WordNet data
#           itself is downloaded the first time it is needed (definitions.py). --no-install turns
#           the offer off; packaged builds skip it. Pillow is only for the tests' screenshots and is
#           never offered. errors.py gained ask_yes_no. Covered by _selftest_deps.py.
# [x] ST-4  Install in two stages: the terminal first, then the window (asked for after ST-3; reworked).
#           1. Terminal, before any window: only what the window itself needs, which is tkinter (the
#              program starts and asks without wordfreq: that is only imported when the list is built).
#              deps.terminal_setup() explains, asks "Install it now? [Y/n]" (Enter = yes), runs the
#              system package manager (apt-get / dnf / pacman / zypper, Homebrew; sudo may ask for a
#              password) and restarts the program so the window can open.
#           2. Window: every Python package, required (wordfreq) and optional (nltk), in ONE dialog with
#              a tick box each (errors.ask_choices: label "(needed)" / "(optional)" and a muted line on
#              what it is for), "Install selected" / "Not now". An optional one left unticked is
#              remembered (meta declined_packages) and not offered again. If this Python refuses pip
#              installs (externally-managed), the window offers to make a private .venv next to the
#              program, installs there and restarts in it; every later start uses .venv straight away
#              (deps.use_private_env). Without a terminal (pythonw, a shortcut) stage 1 is skipped.
#           Tick boxes are drawn as images now (ui_style._tick_boxes): the clam theme's tiny cross was
#           unreadable. Covered by _selftest_install.py and _selftest_deps.py; tried for real in a fresh
#           venv without wordfreq (the dialog appears; screenshot taken).
# [x] ST-5  Linux: the terminal only when it is really needed (asked for after ST-4). Today a Linux
#           start from a terminal keeps that terminal busy until the window closes, and closing the
#           terminal ends the program. Plan: once the terminal stage (ST-4) has nothing left to ask, the
#           program starts itself again in its own session (setsid; output to tierlist.log, like the
#           Windows console detach in ST-1) and the terminal gets its prompt back at once, so closing it
#           no longer matters. It stays attached only while a question is being asked (ST-4), with
#           --console, or when output is redirected on purpose. Plus File > "Add to applications menu"
#           writes a .desktop launcher (Terminal=false) so the program can start with no terminal at
#           all; anything that must be installed is then asked in the window (ST-3). A program cannot
#           close a terminal window the user opened themselves; giving the prompt back is the most it
#           can do. macOS behaves the same way and gets the same treatment if it is cheap.
#           Built: deps.should_detach (Linux / macOS, a real terminal for input and output, no --console, not
#           already detached, and on Linux a desktop to draw on: without one the window cannot open and the
#           message saying so stays in the terminal) and deps.detach_terminal: the program starts itself again
#           in its own session (start_new_session) and waits up to 1.5 s; if the new copy fails straight away
#           its words are printed here, else "Word Tier List is open in its own window: you can close this
#           terminal". That copy writes to tierlist.log next to the save (DETACHED_ENV). File > Add to
#           applications menu (Linux; App.add_launcher, deps.add_to_menu) writes
#           ~/.local/share/applications/word-tierlist.desktop (Terminal=false; again: "updated"). Checked in a
#           real pseudo-terminal: the prompt is back after ~1.7 s, the program runs on in its own session. macOS
#           gets the terminal hand-back the same way (not tried on a Mac here); no launcher there.
# [x] ST-6  How words are dealt (asked for): an extension of the start-up and of the Queue randomness window
#           (UI-41). On the first start (and any time from Settings > How words are dealt...), one friendly
#           page asks how new words should come:
#           - Order: "Most common first" (strictly by frequency, no randomness), or "Mostly common, a little
#             shuffled" with the drop-off shape: exponential (default) or gaussian, and its spread (the
#             UI-41 diagrams show what each does).
#           - Which words: tick boxes per kind: nouns, verbs, adjectives, adverbs, other (all ticked to
#             start with), and "only obscene / offensive words" as its own choice. Unticked kinds are
#             left out of the queue (not deleted: ticking them again brings them back).
#           - "Hide obscene words" (unticked by default): obscene / offensive words are shown masked
#             (f***), in the card, the duel cards, Browse and exports, and still sorted normally.
#           Data: the Wiktionary parse records each word's parts of speech and whether any sense is tagged
#           vulgar / offensive / derogatory / slur (new columns, migrated like the others). Saves built
#           before this have no such data: they are filled from WordNet (parts of speech; nltk) where
#           possible and from the kept Wiktionary file if there is one, else the page offers a one-time
#           rebuild (which keeps all progress). Applying reshuffles only the unplaced words, as today.
#           Browse (decided): the kinds appear in its Show drop-down only ("Nouns", "Verbs", "Obscene
#           words"...), so Browse lists just those words; no extra sort.
#           Changed on the way (the user's choices from the mock-ups): page A for Settings, and on the first
#           start its three parts one at a time (Order, Which words, Obscene words; Back / Next / Done, "Step 1
#           of 3"); "Obscene words" is one more tick box among the kinds (an obscene word is dealt only while it
#           is ticked, any other word while one of its kinds is: untick the rest to sort only obscene words);
#           "Censor obscene words" is a tick box ("blurred, except on hover": the user's words), and a
#           censored word is not f***ed but smeared sideways (the user tried blurs, offset copies and smudged
#           letters, then a blurred band per letter, and after mock-ups of letter shapes blurred at many
#           distances picked copies of the word itself, side by side over 0.625 letter widths, in one pale tone,
#           cut off straight at the first and last letter, no fade, first and last letters smeared too).
#           widgets.smear_items draws that (Tk cannot blur text: the copies are plain canvas text and two strips in
#           the card's colour; SMEAR_SPREAD, SMEAR_TONE); with the pointer over it, it un-smears (widgets.Unsmear:
#           the copies close in and darken into the word; 260 ms; back again on leaving). On the word card
#           and the duel cards; the outgoing word of a placement leaves as its smear. Everywhere text only can
#           go (messages, the anchor question, the focus line, the definitions drawer, Browse's list) it reads
#           b•••••d (constants.mask_word); Browse's definition pane and exports keep the real word.
#           "Other" covers pronouns, prepositions, conjunctions, interjections, numbers, abbreviations,
#           contractions and the like (prefixes and suffixes are not in the list at all).
#           Built: words.kinds (bits), words.obscene and words.out (left out of the queue; index
#           idx_words_q3 on tier, out, skips, qkey, so the next word is instant even with all but a few
#           thousand left out of a million). The Wiktionary parse records each entry's part of speech; a
#           save made before this gets its kinds from the stored definitions' "(noun)" lines (every source
#           writes them; WordNet for the rest, else "other"). Obscene words: obscene.py's list (see the fix
#           below). Both are start-up steps ("Sorting words into kinds", "Finding obscene words"; since OB-6 "Scoring rude meanings"). Order "Most common first" is the queue shape "rank". Browse's Show lists the placed words
#           of a kind. With everything chosen placed, Place says how many are left out. Measured with a
#           million words: re-dealing ~3.5 s (worker thread, moving bar), the dialog's counts ~0.4 s. The
#           first start's steps show once per save (main(): App(ask_dealing=...)). _selftest_dealing.py.
#           Then (asked for): each kind's tick box says what it holds on hover (constants.KIND_NOTES: a
#           definition and examples; Other's list moved there from under the boxes).
#           Fixed (reported): "bureaucracy" came out obscene, and then "most of these bad words are not bad
#           words". Wiktionary's labels (any sense vulgar / offensive / derogatory, or its categories of them)
#           catch every word with one rude sense among many ("box", "screw", "head"), so they are no longer
#           used: obscene.py holds a short list chosen by hand (swear words, vulgar words for sex and the body,
#           slurs; ROOTS also inside longer words, WORDS with the usual endings; words whose usual meaning is
#           innocent left out, NOT_INSIDE / NOT_OBSCENE for "snigger", "spicy", "saltwater"). Checked against
#           wordfreq's 400,000 commonest words. _selftest_obscene.py.
#           Then the user's rule (asked for, "both most and first"; replaced by OB-6's rules, its code removed): a
#           word is obscene if MOST of its meanings
#           are rude or its FIRST one is (vulgar, offensive, derogatory / pejorative, a slur; not "sometimes
#           offensive"); a meaning that is a form of another word ("plural of bitch") is rude when that word is
#           (obscene.decide, tag_marks, page_senses). A Wiktionary build reads each sense's tags as it goes; a save
#           whose download is gone reads the pages of the words in Wiktionary's rude categories (50 a request,
#           with a percentage and time left) and their forms from its own definitions. Until it can (offline),
#           the hand-picked list stands in (obscene_done "list"; asked again after 6 hours). Store.OBSCENE_VERSION
#           4. The self-tests never go online (WORD_TIERLIST_OFFLINE, set by tests/_paths.py).
#           Checked (asked for): every letter first and last, smeared. Wide spaces inside letters (the eye of "e",
#           between the curves of "ss") and a last letter open on its right ("c", "z") left white slivers and
#           notches; a band in the smear's tone now fills the letters' body behind the copies (SMEAR_BODY, about
#           the x-height), fading out early in the hover so no pale box shows behind the letters closing in.
#           For now (asked for: "it kinda worked"): "Obscene words" starts unticked, so the words marked obscene
#           are left out until telling them apart is worked on again (deal_done 2 re-deals older saves).
#           Fixed (reported): no tick boxes showed in the main window: styling the window a second time (main()
#           at start-up, then App) made new tick images, freeing the ones the tick-box element drew.
# [x] OB-1  (archived: replaced by OB-4, then by OB-6's rules) Review the flagged obscene words by hand (asked for: "a dev option booted via the terminal", "a new
#           tab with a simple % progress bar"). Flagging was made loose for it (any meaning rude), then put back
#           ("too loose, go back"): most or the first meaning rude (obscene.decide; Store.OBSCENE_VERSION 7).
#           python tierlist.py --review-obscene opens the "Review obscene words" tab (only then; App(review=True)):
#           the commonest flagged word not yet answered, never censored, its definitions open (not saved as your
#           setting), Not obscene / Obscene / Swear word (keys 1 / 2 / 3, the keymap's "review" group, changeable)
#           and Back (Backspace, also Undo there), a determinate bar "N of M reviewed (P%)", and Save answers to
#           a file (obscene_review.txt next to the save: word<Tab>answer, commonest first). The answers live in
#           the save (table obscene_review) and win over every later finding (Store.set_obscene re-applies them);
#           "swear" counts as obscene until OB-3. _selftest_review.py.
# [x] OB-2  Censor the obscene meanings inside definitions (asked for: "only when Censor obscene words is on, by
#           Wiktionary labels, and the smear"). In the definitions drawer and Browse's pane (both now filled by
#           widgets.fill_definitions, one sense a line: the Wiktionary build's lines used to run together into one
#           paragraph), a sense labelled vulgar / offensive / derogatory / a slur (not "sometimes offensive")
#           shows its label and its text smeared like a censored word (a small canvas in the text, smear_items),
#           un-smearing under the pointer. The review tab never censors. The labels: a new Wiktionary build keeps
#           them in the stored definition ("\u2022 (noun) (vulgar) ...", as "(obsolete)" already was); an older save
#           gets them from the same Wiktionary pages the flagging reads (obscene.page_senses, label_lines: each
#           stored line takes the labels of the page sense sharing most of its words, at least half; a loose
#           match labels nothing). Store.OBSCENE_VERSION 6 looks again. WordNet / dictionaryapi.dev definitions
#           carry no such labels, so they are never smeared. Since OB-6 the rules decide which meanings are
#           smeared (rude.smeared, by each meaning's first GLOSS_KEY characters); the labels are only shown, and
#           the page reading (page_senses, label_lines) is gone.
# [x] OB-3  (archived, asked for: "I only want the rules, I don't want to use Claude's list anymore, or even the
#           review system"; the code is in commit 233d6ca: tools/classify_obscene.py, _selftest_classify.py; its
#           sorting file stays only as the yardstick of tools/measure_rudeness.py) Sort the rude words into kinds
#           with Claude (asked for: "a separate tool that does semantic analysis on
#           the word and definition ... not available through the UI", "take into account individual
#           definitions", then "check the ones with low confidence"). No public list covers it: LDNOOBW (403
#           words, no kinds), HurtLex (8,228 entries in 17 categories, noisy: "idiot" filed under female body
#           parts) and surge-ai/profanity (could not be reached from here) only feed the candidates.
#           tools/classify_obscene.py (estimate / try / run / status): candidates are the words marked obscene,
#           any meaning Wiktionary labels rude, meanings that speak of sex, bodies, excretion or insults
#           (SENSITIVE), the hand list and the two lists' words in the save; a word that is only a form of a
#           candidate takes its answer. Claude (claude-opus-5-5, --model to change; low effort; structured
#           output) judges each meaning (clean, clinical, crude, swear, sexual, insult, slur) and the word (those,
#           or double: innocent main meaning, rude slang one) with a confidence 0-100, 20 words a request, through
#           the Message Batches API (half price). It shows the cost and asks first; resumable (a state file);
#           writes word_categories.tsv next to the save (word, kind, confidence, meaning kinds, note); below 80
#           is for checking by hand. Reads the save only. --recheck (asked for: "run through haiku and then
#           only the low confidence ones through opus") sends only the words answered below --review again,
#           replacing their answers; each answer notes its model (a sixth column; status counts by model).
#           --second (asked for, "using the already processed data"): asks only for the unsure base words'
#           second choice (a seventh column, "insult:30"), the existing answer in the prompt; to_check leaves
#           out a word whose two choices have the same outcome with the defaults (OUTCOME: clean shown, sexual /
#           slur left out, the rest smeared). Fixed: a form of a form kept an out-of-date answer (with_forms). Never run against the real API here (no key):
#           _selftest_classify.py uses a stand-in.
# [x] OB-4  (archived with OB-3; in commit 233d6ca: the review tab in app.py, --review-obscene, the keymap's
#           "review" group, Store's kinds table and methods, obscene.py's meaning rules, _selftest_review.py)
#           Review the low-confidence words by hand with the new kinds (the --review-obscene tab), answers back into
#           the list. Then the list goes inside the program, out of sight (still to do). Asked for (decided): per meaning
#           (each meaning's kind, changeable) plus the whole-word smear (ticked by itself from the first meaning,
#           changeable); only the base words that are unsure (below 80%, and a second choice at least 25% likely
#           that changes the outcome) or where Claude's whole-word answer and the first meaning disagree on
#           smearing the whole word: 2,079 of the user's run (542 among the commonest 5,000), commonest first.
#           Mock-up A chosen. Built: the rules in obscene.py (KINDS, TICKED, word_kinds, smear_whole, outcome,
#           outcome_text, check_reason, read_categories), shared with the tool. Store: table kinds (load_kinds:
#           the words in the list, answered ones kept; kinds_next: commonest unchecked, then "not sure" ones;
#           kinds_progress, answer_kinds, kinds_back, checked_kinds). App.load_sorting reads
#           word_categories.tsv next to the save on a --review-obscene start when it is new or changed (meta
#           kinds_file). The tab: the card and why it is here, the meanings in a fixed-height text (each kind
#           a little button; the selected meaning tinted; a rude use missing from the definitions as one more
#           row), the kind buttons (keymap group review: 1-8, Up / Down, W, Return, BackSpace), the whole-word
#           tick, what it leads to ("With the usual settings: ..."), Back / Next word, the bar, and Save answers
#           to a file (word_categories.checked.tsv). It replaces OB-1's not / obscene / swear review (its
#           answers stay in the save and still count for the obscene column). _selftest_review.py.
# [x] OB-6  Rules instead of a list (asked for: "a point-based model that uses multiple sources", "rather a
#           solution that can run for each word on startup than a list"; "if it has really high points its
#           completely censored, and low points not censored unless a specific definition is contributing a
#           lot"). Built so far: src/rudeness.py: each meaning earns points towards the rude kinds from four
#           sources (TAG_POINTS: Wiktionary's labels, hedges halving them; TOPIC_POINTS: topics and categories;
#           WORDING: the definition's words; GROUP: a group of people named, with a rude label: a slur; the word
#           itself holding a rude root, obscene.on_list). A meaning's kind: its best kind at MEANING_MIN 3+
#           points; the word's points: its first meaning, plus 0.35 x the mean of the rest, over the censored
#           kinds; WHOLE_MIN 3.5+: the whole word smeared, else only the rude meanings. Tuned against Claude's
#           sorting of the user's 20,643 words with tools/measure_rudeness.py (kaikki.org's download streamed,
#           56k entries kept): with Crude / Swear / Sexual / Slur censored, the same outcome for 76.1% of words
#           (78.8% of the commonest 5,000), slurs 89% right when flagged; 99.4% of a control sample of other
#           words stays clean. Learned while tuning: "vulgar" alone is a swear word (the wording decides
#           sexual / crude / insult); a slang label is never the proper (Clinical) word; anatomy alone is not
#           sensitive; group wording counts only with a rude label. WordNet as a sixth source, when installed
#           (asked for; never downloaded by it: rudeness.wordnet()): each meaning matched to one of the word's
#           WordNet meanings by the words their definitions share (not the word itself: "pig: a pinkish colour"),
#           points from that meaning's tree (sexual activity, genitalia, body waste, unpleasant person,
#           simpleton, prostitute) and usage labels (ethnic slur, disparagement, obscenity). It knows only about
#           a fifth of these words (little slang); it changes 58 of 66k meanings, mostly unlabelled plain words
#           ("pee", "puke", "nipple", "genitalia", "jackass"): the same 76.1% overall (78.9% of the commonest),
#           so it fills small gaps rather than raising the score. The links between words (asked for), a second
#           pass (score_words / link_points): Wiktionary's synonym lists (from its thesaurus pages) give points to a
#           meaning whose synonyms are mostly of a kind (outward) and to a word listed by a rude meaning, on its
#           own meaning whose definition matches (inward: "banana: (slang) penis", never the fruit). Measured:
#           letting them make words rude was worse (74.8%): synonyms share a meaning, not its rudeness ("shitty"
#           lists "bad", "fuck" lists "company", thesaurus pages mix informal and rude words). So they count only
#           on meanings marked slang, vulgar, derogatory, offensive, euphemistic or childish (REGISTER): the same
#           76.0% overall, better kinds (Crude found 20% from 17%, Sexual 59% from 57%), as few false alarms.
#           Then fixes from 50 disagreements read by hand (the rules right on ~17, Claude on ~28, 5 either):
#           meanings that only name another word are skipped for the first meaning (is_form); later meanings
#           count up to OTHERS_CAP (one rude later meaning never smears "hoo-ha", "bathroom"); plain sex words are
#           Clinical, only slang / rude ones Sexual ("male", "pin-up"); "euphemistic" adds nothing (euphemisms
#           are the polite word); "offensive" alone is no slur (a group named is: GROUP_POINTS 5, "Welsh person",
#           "a native of"); rude categories count as a rude label; an alternative form takes its word's points;
#           more sex words. Now 78.2% (80.3% of the commonest), words wrongly left out down from ~420 to ~100.
#           Wired in (asked for: "only the rules, not Claude's list or the review system"): the Wiktionary
#           build keeps every meaning of the words with any sign of rudeness, and of their forms
#           (wordsource.RudeCollector: ~150k words, compact, table rude), and prepare_queue scores them once
#           ("Scoring rude meanings", under a minute; again when RUDENESS_VERSION changes: rudeness.score_saved, find_rude).
#           words.rude holds the kinds of a word's meanings (rudeness.KIND_BITS, 1 = a clean one), words.obscene
#           now means "smeared whole while censoring", rude.smeared the meanings smeared in the definitions (by
#           their first GLOSS_KEY characters). A form-only word is smeared whole as its word is. A save without
#           the meanings (older, or a word list) downloads Wiktionary in the background while you sort (App.
#           _start_rude_read: a worker thread with its own read-only connection; the main thread writes the
#           result a few thousand rows a frame); until then its earlier flags and the hand list stand in
#           (rude_done "list"). Removed: obscene.decide / tag_marks / page_senses / label_lines, fill_obscene
#           (Wiktionary's category pages), OBSCENE_VERSION, the OB-1 answers (table obscene_review, unused).
#           Word families (asked for): a word built from one whose first meaning is rude (its etymology's parts:
#           compound, affix, blend ...; or listed among that word's derived terms) gains FAMILY_POINTS towards its
#           kind (rudeness.family_points; kept with the meanings: compact_entry "e" / "d"). Measured: 78.4% with
#           families, the same without the hand-picked list's roots, so ROOT_POINTS is gone and the list only
#           stands in until a save has Wiktionary's meanings (and for a word added by hand). RUDENESS_VERSION 2.
#           Tried and dropped (asked for: "run the examples through an NLP library"): each meaning's Wiktionary
#           examples. Other rude words in an example made it worse (74.9%; 75.0% on slang / rude meanings only:
#           rude words are illustrated beside clean ones), patterns of use ("you ___", "what the ___", "___!")
#           and NLTK's VADER (a hostile example, the word itself taken out) changed nothing (78.0%, 77.9%).
#           Found on the way: the program's compact meanings dropped "informal" / "colloquial", which the rules
#           read (fixed). False alarms: 0.6% of a control sample of ordinary words; 7.7% of the words Claude
#           called clean among its suspects; per kind, Swear is the loosest (41% precision), Slur the surest (89%).
#           Fixed (reported: "did", "take", "best", "p" came up as obscene words): a form now follows its word's
#           first meaning, not its rudest ("did" is "do", "best" is "good", "p" is "pretty"); "intensifier" /
#           "expletive" wording is a swear word only with a rude label ("well: (slang) very"); a Clinical meaning
#           counts only when the word is about it, its first meaning not clean (meaning_kinds: "penis", not "take:
#           to have sex with"); "euphemistic" no longer makes a meaning Sexual ("make: to take the virginity of").
#           Then, from the commonest 3,000 words: hedges ("often", "sometimes") weaken every label of a meaning
#           (kaikki.org sorts the labels, so which one they hedged is lost); a rude label on a meaning about a thing
#           ("system: (often derogatory) the mainstream culture") or on a form is no insult; the insult wording
#           needs a person ("why: unpleasant surprise" was one). RUDENESS_VERSION 4. Measured: 78.5% (80.8% of the
#           commonest), false alarms on ordinary words 0.4%, Insult 68%, Sexual 74%, Slur 90% right when flagged.
#           Then (asked for: "the vast majority of common words are not obscene"): a word at least COMMON_ZIPF
#           (4.5, wordfreq: about the 3,000 commonest) whose first meaning is clean counts a rude meaning only when
#           Wiktionary labels it strongly (vulgar, offensive, derogatory, a slur, a rude category): "top: (slang)
#           fellatio" no longer makes "top" an obscene word, "box: (vulgar) the vagina" still does. Of the 10,000
#           commonest words, 82 drop out (do, back, love, game, play, hot, ...), none of them obscene; flagged
#           among the 3,000 commonest: 211 -> 129. And a rude category on a meaning with no rude label of its own
#           counts 40% (CATEGORY_ALONE: Wiktionary files "wood: chess pieces" under English ethnic slurs; "darn"
#           is now clean). RUDENESS_VERSION 5: 78.5% against Claude's sorting (unchanged: it saw only the first
#           meanings), Clinical right 69% when flagged (from 63%), false alarms on ordinary words 0.4%.
#           Then (asked for: "look up similar problems and solutions that wouldn't normally be applied to
#           vocabulary ... validate for random lists of words"): 9 random lists of 200 words (any word; the 20,000
#           commonest; words with any sign), judged meaning by meaning by two independent subagents (99.2% the
#           same; a third settled the 32 disputed words), only to measure. Of the borrowed ideas, three kept
#           (RUDENESS_VERSION 6): a rude label alone is a suspect, not an insult, without a person described
#           badly in the gloss or WordNet (disease case definitions: two kinds of evidence); "euphemistic" /
#           "childish" soften a meaning (SOFTENED: clinical text's negation / hedge rules); a slang meaning that is
#           a rude word takes its kind ("dam: Damn.") and a short slang name for a body part or sex act gains
#           SLANG_BODY (one step along the link, as TrustRank). Words falsely flagged 48 -> 28, smeared meanings
#           missed 36 -> 27 of 138 (false 16 -> 17); the cost: mild insults missed (words missed 30 -> 47, insults
#           are never smeared). Tried and dropped: label repeated on every meaning as a leak, harmless-topic
#           veto, two sources for unlabelled meanings, per-source caps, a higher bar for late meanings.
#           Checked on 4 fresh held-out lists (800 words, judged the same way): false flags 23 -> 16 held up; the
#           smeared-meaning gain did not (12+17 -> 14+16: it had fitted the tuning lists). A Clinical rule (only
#           when the definition starts with the body / sex / waste) held up (false flags 16 -> 11) but was left out
#           (the user chose the roadmap). Then 17 rule sets voting (asked for): majority, k of 17 and every 3- / 5-
#           voter committee, chosen on the tuning lists: at best 3% fewer errors held out, smeared meanings
#           unchanged: the voters share Wiktionary's data, so they share its mistakes. Not built. How words are dealt: "Obscene words" sits before "Other",
#           and shows a minus while only some kinds under it are ticked (ui_style: the tick box's "alternate").
#           Then (asked for): a word goes into the rude kinds only when one of its meanings needs censoring
#           ("idiot", "penis" are ordinary words: rudeness.results; RUDENESS_VERSION 7). And a group's own name is
#           no slur ("jews", "trans", "gay", "queer"): without a slur marker of its own (a slur / ethnic / vulgar
#           label, English ethnic slurs), a meaning naming a group is no slur when the word has a plain meaning
#           that is the group's name (IDENTITY), when it is only "sometimes" rude by one label, when it is a
#           letter-case form ("jew"), or when it names the group by the word itself ("transgender: a transgender
#           person"); real slurs ("kike", "tranny", "faggot", "dyke", "spic", "hebe") stay (SLUR_MARKS;
#           RUDENESS_VERSION 8). Measured: 78.7% (78.8%), Slur precision 90.0% (89.5%), recall 54.7% (56.0%).
#           Then (reported: uncensored words under "Obscene words"; asked: "Only censored words"): only a word
#           smeared whole keeps its rude kinds (rudeness.score_saved; RUDENESS_VERSION 9); one rude meaning of many
#           ("can: buttocks", "come", "box": about 1,700 words) leaves the word ordinary, that meaning smeared in its
#           definitions. (measure_rudeness compares meaning by meaning: unchanged.)
# [x] OB-5  How words are dealt (asked for): ticking "Obscene words" opens the list of kinds, with Swear word,
#           Crude, Clinical, Double meaning and Insult ticked and Sexual and Slur not; Censor obscene words then
#           smears the ticked kinds' words and each rude meaning inside the definitions. Mock-ups first.
#           Decided: Double meaning words are never smeared as words ("last", "john", "brown" are double), only
#           their rude meanings inside the definitions; Clinical words are smeared like the other ticked kinds.
#           Then decided (asked for: "words can be multiple categories at the same time"): kinds go by MEANING.
#           A word's kinds are its meanings' kinds (then classify_obscene's per-meaning column, archived; now
#           OB-6's rules; forms take their word's), plus its whole-word kind when no stored meaning shows it (the rude sense is not among the
#           stored definitions: "faggot" listed only as a bundle of sticks). Dealt if any meaning is clean or of
#           a ticked kind; left out only if every one is unticked. Censoring smears each rude meaning in the
#           definitions, and the whole word when its first (most common) meaning is rude or every meaning is
#           ("if the most common definition is obscene then it should fall under censoring"). Double meaning
#           is dropped as a kind (it is just a word with clean and rude meanings): seven kinds. The user's run:
#           4,723 base words shown, 2,187 with some meanings smeared, 6,296 smeared whole, 2,195 left out.
#           Built with OB-6's rules: under "Obscene words" (shown while it is ticked) a tick box per kind with its
#           count (Store.kind_counts), Clinical, Crude, Swear words and Insults ticked to start with (meta
#           deal_rude); a word with a meaning of a ticked kind is dealt, one with only rude meanings is otherwise
#           left out, any other word goes by its kind of word (Store._out_sql). Censoring smears only Crude,
#           Swear, Sexual and Slur (obscene.CENSORED; the user: never Clinical or Insult).
# [x] ST-7  Progress windows: a real download speed for packages, and "Step i of n" (asked for). Installing
#           packages used to show only a sweeping bar (pip prints no progress into a pipe), so there was no
#           time left. Now pip gets a temporary folder of its own (TMPDIR) and a watcher thread follows the
#           file being downloaded, adding up the finished ones (pip names each and its size as it starts):
#           "18.6 of 62 MB at 6.2 MB/s (30%)", which drives the bar and the time left (deps.DOWNLOAD holds the
#           measured download sizes). Any pip version. Then "Installing..." with the sweep.
#           "Step 2 of 5" sits in the window's bottom right corner: a job names its main steps up front
#           (constants.plan_line; never printed) and each matching stage line moves it on (retry notes do
#           not). Packages: downloading, installing (plus "making a private environment" when needed);
#           first run: downloading English Wiktionary, reading entries, ranking words, detecting compound
#           words, looking up how common, shuffling the queue (only the ones that will run:
#           wordsource.wiktionary_steps / queue_steps). Nothing shows for a one-step job.
#
# --- Phase 0: housekeeping -------------------------------------------------------------------
# [x] UI-0  Tidy the dead leftovers found in the audit (adds nothing, removes):
#           edit_anchors(first=) unused parameter; Store.reshuffle(progress=) unused callback;
#           redundant `seeds = []` / `seeds = list(seeds)` in pick_within; redundant getattr in
#           stats(). (make_btn(width=) disappears in UI-5; App.tier_btns comes alive in UI-7.)
#
# --- Phase 1: look and feel foundations (no behaviour change) ---------------------------------
# [x] UI-1  Palette.     adds theme.py (PALETTE tokens, six pastel TIER_COLORS, contrast()) and
#           maps every hard-coded colour in tierlist.py onto it. Light theme only. The window
#           and ttk backgrounds are still the system grey until UI-3 styles them.
# [x] UI-2  Typography.  adds fonts.py: pick_font_family() + init_fonts(root) + font(role): shared
#           tkfont.Font objects for the roles word / pair / vs / tier / choice / title / head / label
#           / body, using the first installed of Nunito, Quicksand, SF Pro Rounded, Segoe UI,
#           Helvetica Neue, else Helvetica. Replaced every hard-coded font tuple; sizes are
#           unchanged, so the layout does not move. ttk widgets keep the system font until UI-3.
# [x] UI-3  ttk styling. adds ui_style.py: apply_ttk_style(root) styles the "clam" theme for TFrame,
#           TLabel, TButton, Radio/Checkbutton, Entry, Combobox, Treeview (+heading), Scrollbar,
#           Labelframe and Separator, and sets menu, text, listbox and dialog colours through the
#           option database. Window background is now the cream; make_btn labels are flat with a
#           hairline border (they become rounded in UI-5). The Browser keeps its own font-scaling
#           styles on top of this base.
# [x] UI-4  Motion engine. adds ui_motion.py: ease_out_cubic(t), lerp_color(c1, c2, t) and
#           Animator.run(key, ms, on_frame, on_done): a running animation with the same key is
#           finished first; ~16 ms frames; finish_all() (called by App.on_key) and cancel_all().
#           Also the saved "Reduce motion" switch (View menu, App.toggle_motion): when on, run()
#           jumps straight to the end state. Nothing animates yet; UI-16 onward use it.
#
# --- Phase 2: widgets (each replaces one ad-hoc piece of the current UI) -----------------------
# [x] UI-5  RoundButton.  Canvas widget in widgets.py: smoothed rounded corners, hover tint (fades with
#           the Animator, jumps with Reduce motion), pressed "dip", disabled state, small key-hint
#           caption under the label. Replaces make_btn / set_btn_enabled everywhere (main window and
#           Browse). Label-style options (text, hint, font, wraplength, bg, fg) so existing code kept
#           working; click fires on release inside the button; invoke() / flash() give keyboard
#           shortcuts the pressed look (used by UI-7); refresh_widgets(widget) (was refresh_buttons) re-measures after a
#           shared font was resized (done by the window-fitting code and the Browse text scaling).
#           The ttk buttons (Undo, Browse / edit, dialogs) are still square: UI-24 restyles them.
#           Covered by _selftest_widgets.py.
# [x] UI-6  WordCard.     adds WordCard.set(word, sub) in widgets.py: the big word on a soft rounded
#           white card with a faint shadow and a muted sub-line (frequency rank, "skipped",
#           "compound"). Replaces word_lbl + sub_lbl. The card has a minimum width (so it does not
#           jump from word to word), widens for long words, then wraps; its padding follows the word
#           font so it shrinks with the rest when a small screen forces smaller text. The old
#           refresh_buttons() became refresh_widgets() (handles buttons and cards).
#           Covered by _selftest_widgets.py.
# [x] UI-7  TierRow.      adds TierRow: six pastel pills (letter + key hint) with a hover lift and
#           press(tier), which plays the same pressed "dip" as a mouse click (RoundButton.flash, built
#           in UI-5) so pressing 1-6 on the keyboard looks like pressing the pill. Revives
#           App.tier_btns. (UI-18 wires every other hotkey the same way.)
#           Built: TierRow(parent, tiers, on_pick) in widgets.py; RoundButton gained lift= (rises 3 px off
#           a soft shadow on hover). press() runs the action first, then dips. Covered by
#           _selftest_widgets2.py (the test file for every widget from UI-7 on).
# [x] UI-8  DuelCards.    adds DuelCards.show(left, right): two big cards with a hover ring and
#           arrow-key hints, plus quiet Tie / Skip text buttons. Replaces left_btn / right_btn /
#           tie_btn / skip_pair_btn. Offers press(side) for left / right / tie / skip so the
#           hotkeys (Left/A, Right/L, Down/T, S) can show the pressed look (wired in UI-18).
#           Built: DuelCards(parent, on_answer) in widgets.py, App.duel (left_btn etc. are its buttons).
#           RoundButton gained flat= (quiet text button), ring= (hover ring width) and hint_font=.
# [x] UI-9  AnchorLadder. adds AnchorLadder.update(lo, hi, mid): an S-A-B-C-D-F strip with the
#           still-possible tiers shaded and the anchor being asked about marked; it narrows
#           smoothly after each answer. Shown in the Better / Same / Worse view.
#           Built: AnchorLadder.update_range(lo, hi, mid) in widgets.py (named so it does not hide
#           Canvas.update): ruled-out tiers fade over 180 ms, the asked tier has an accent ring and caret.
#           Sits between the word card and the question.
#
# --- Phase 3: layout and chrome ----------------------------------------------------------------
# [x] UI-10 Modern top bar. adds a mode switch (Place / Refine / Boundary / Conflicts; first planned as a
#           pill SegmentedControl, built as tabs on the page line by request) replacing the
#           Radiobuttons, and the File / Edit / View / Settings menus as soft rounded header buttons
#           with styled drop-down menus instead of the plain system menu bar (same items, same
#           shortcuts). By request: modernize the top; the bottom bar stays as it is.
#           Built: widgets.py TabBar (folder tabs on a full-width page line; the open tab is page
#           coloured and open at the bottom so it joins the page below; it slides, 180 ms), DropMenu (borderless
#           drop-down: roomy rows, pastel highlight, check marks, shortcut hints; Up/Down/Return/Escape;
#           closes on a click elsewhere, a window move, or when the app loses focus) and HeaderMenus
#           (File / Edit / View / Settings as flat buttons; hovering another while one is open switches,
#           like a menu bar). App._build_header; Alt+F/E/V/S and F10 open the menus; keys do nothing
#           else while a menu is open. The system menu bar is gone.
# [x] UI-11 Toast.       adds Toast.show(text, tint): a small pill that fades in and out (colour
#           blend) instead of the full-width flash banner. App.flash() keeps its signature.
#           Built: Toast(parent, font) in widgets.py, floating at the top of the page (place), so it
#           never pushes the layout; fades in 160 ms, out 220 ms; long messages wrap. App.banner is the
#           Toast (cget("text") still works). Messages use a real arrow (apple  \u2192  S).
#           Placement messages (by request) use Toast.fling: the message rises out of the word card
#           (200 ms, fading in), rests just above it while paling slightly (550 ms), then swipes sideways
#           toward its tier (S, A, B left; C, D, F right; further for the outer tiers) while fading out
#           completely (240 ms). It borrows the white of the card as its backdrop while over it (no
#           transparency in tk). A key press or a new message cuts it short; Reduce motion keeps it still.
# [x] UI-12 DefinitionDrawer. adds DefinitionDrawer.toggle(): the panel eases open and closed
#           instead of snapping; nicer text (bold word, italic part of speech, muted examples).
#           Replaces def_frame / def_text.
#           Built: DefinitionDrawer in widgets.py (App.def_frame; def_text is its Text) slides open and shut
#           over 200 ms; definitions.parse_definition() splits the stored text into senses (no tkinter).
#           Lesson: after a height animation, reset the frame's explicit height to 0 as well as turning
#           propagation back on, or Tk flips between the two sizes forever (that hung _selftest_sizing).
#
# --- Phase 4: seeing your list take shape ------------------------------------------------------
# [x] UI-13 DistributionChart. adds DistributionChart.set(counts): six pastel bars (S..F) with
#           counts, fed by Store.tier_counts(); bars grow with ease-out when a count changes.
#           (Read the dataviz skill before building.)
#           Built: src/ui_chart.py, at the right of the status line, in Place new words only (by
#           request; see UI-31 for the other tabs). Bars <= 24 px, rounded data end on one hairline
#           baseline, letter under and count on top in text colours, a hover note per bar
#           (widgets.Tooltip), growth 220 ms, pulse(tier) and bar_top(tier) ready for UI-17. Bars are
#           the tier pastels with the pills' faint same-hue edge. A colour-blind-tuned set (passed the
#           dataviz validator) was built and then dropped by request: it lost the pastel look, and the
#           letter + count on every bar already tell the tiers apart without colour.
#           Covered by tests/_selftest_chart.py.
# [x] UI-14 ProgressBar. Decided (no longer on hold): a bar split into equal-width segments by how common
#           words are, each segment holding ten times the words of the one before: everyday (frequency rank
#           top 1,000), common (1,000-10,000), uncommon (10,000-100,000), rare (100,000 and beyond, including
#           words wordfreq does not know). Each segment fills by the share of its own words placed, so it
#           is a log scale over commonness: every placed word counts (also zero-frequency ones, which a
#           coverage measure would ignore), segments fill roughly left to right because the queue favours
#           common words, and the rare words get a quarter of the bar instead of a millionth of it.
#           Hover / small text: "everyday 100% · common 97% · uncommon 41% · rare 0.3%"; the segment being
#           worked in can show its own count ("rare: 1,204 of 640,000").
#           To the right of the bar, a tag: the share of everyday English the placed words cover (wordfreq
#           frequency-weighted, e.g. "covers 99.4%"), formatted with as many decimals as it takes to show
#           the last change (93%, 99.4%, 99.97%) so it never sits at a flat 99%. It is a label only; it does
#           not drive the bar (on its own it barely moves for rare words).
#           Both come from per-segment counts and a running coverage sum in the Store (no full scan per
#           refresh). Calm: no goals, no streaks. Placed / total stays as text. No ETA: this measures the
#           list, it is not a task running (the ETA rule is for set-up bars).
#           Built: ui_chart.SegmentBar under the status line (lilac fill on the soft track; each segment's
#           name and share under it; a hover note gives the counts: "uncommon words: 22,574 of 90,000
#           placed"), the "covers 92%" tag to its right (ui_chart.format_coverage / format_share).
#           Store.progress(): counted from the save once (~0.6 s with a million words), then kept up to
#           date by place / unplace / undo (bulk changes recount), ~2 ms per placement. Frequencies live
#           in a new words.freq column, filled once at start-up from wordfreq (~3 s; wordsource.
#           fill_frequencies, meta freq_done); words wordfreq does not know count 0 towards coverage.
#           Redesigned (asked for; built, replacing the segment bar above): a bookshelf.
#           One shelf of book spines on a softened log scale of commonness, split by small gaps into five zones
#           named for how often you would meet such a word (wordfreq Zipf steps): page (about once a page),
#           chapter, book, shelf, library. A spine's height is the share of its words placed; its colour comes
#           from the tiers its words went into: either the median tier blended round the colour wheel (stays
#           as bright as the pastels; never a channel mix, which greys) or the "leaning" tier (the tier most
#           over-represented there compared with the whole list). Chosen: the blended median for the colour,
#           with the leaning tier in each spine's hover note ("shelf · 1,245 words · 94% placed · mostly C,
#           leans B"). The coverage text after it reads "95% of text".
#           Built: ui_chart.Bookshelf (soft_median, leaning), theme.tier_blend, constants SHELF_*. Store.shelf()
#           / shelf_layout(): zones from the stored frequencies (Zipf 6/5/4/3), 64 spines as equal steps of
#           log(rank + 30), so a spine near the start holds a few words and one near the end thousands (the
#           note says how many). Tallies per spine (words, placed, per tier) counted once by SQLite on a new
#           covering index (~0.5 s with a million words), then kept current by every tier change (place, a
#           Browse move, unplace, a boundary swap, undo): ~2 ms per action.
#           Fixed (reported: a real save showed only "page", cut off, and "library"): the frequency fill left
#           hyphenated / spaced forms at 0, though the ranking had estimated them near the top, so the first
#           zone boundary landed at rank ~3. The fill now estimates them the same way (Store.FREQ_VERSION 2:
#           older fills redo once at start-up), the zone boundaries ignore words with no frequency, and the
#           zone names are kept whole and apart on the shelf. Rejected: separate segments, a plain coverage bar,
#           a tier-coloured bar, milestone steps, bookends, a bookmark ribbon, a hill profile, average-tier
#           colour mixing.
# [x] UI-15 Calm stats.  adds format_stats(stats): one quiet line (placed, left, skipped;
#           conflicts only when there are some) replacing the dense two-line header. The session
#           count STAYS, as a small muted "+N today" at the end of the line; the "/hr" rate shows
#           only in a tooltip when you hover over "+N today" (adds Tooltip(widget, text_fn)).
#           The placed/total figure stays alongside the UI-14 bar.
#           Built: app.format_stats(): "Placed 6,506 of 9,006 (72.2%) · 2,500 left · 0 skipped" (duels
#           dropped from the line; conflicts only when there are some). "+N today" counts the actions
#           saved since local midnight (Store.actions_since over the undo history, so undo takes one
#           back); the pace ("about 120 an hour" this session) shows only in a hover note.
#           widgets.Tooltip is the shared hover note (also used by the chart).
#
# --- Phase 5: satisfying (but tasteful) motion -------------------------------------------------
# [x] UI-16 Word transition. adds App.animate_word_change(direction): the old word nudges ~12 px
#           toward the chosen tier and fades while the next word eases in (~180 ms in total).
#           Input is never locked; the next keypress completes it instantly.
#           Built: WordCard.transition_from(old_word, old_sub, dx, dy, animator): the old word (drawn under
#           the new one) moves toward its tier (dx by tier, 12 px down) and is gone by 55% of the 180 ms;
#           the new one rises a few px into place from 35%. "Don't know" drifts up instead. Positions are
#           absolute, so a redraw mid-way still ends exactly in place. The placement toast now starts at
#           the card's top edge (an opaque tk canvas over the word hid the letters).
# [x] UI-17 Drop-to-bar. adds fly_chip(word, tier): a small chip travels from the card to that
#           tier's bar (~250 ms) and the bar ticks up with a soft pulse. The main "that felt
#           good" moment.
#           Approved plan: build this as the END of the placement toast's swipe (UI-11) instead
#           of a second chip: the toast already rises out of the word, so once the chart (UI-13) is on
#           screen above the card it can swipe up and toward its tier's bar and land in it, the bar
#           pulsing as it arrives. One motion instead of two, and it says where the word went.
#           Built that way: Toast.fling(target=, on_arrive=) flies the resting message to its bar's top
#           (DistributionChart.bar_top) over 240 ms, fading, and the bar pulses (chart.pulse) as it lands.
#           A message replaced mid-way never "lands". (The sideways swipe was removed in the tidy-up:
#           placing only happens in Place, where the chart is always there.)
# [x] UI-18 Keyboard press feedback. adds one key -> button map used by App.on_key, so EVERY hotkey
#           plays its button's pressed "dip" (RoundButton.flash, ~110 ms) as well as doing its job:
#           1-6 (tier pills), Space (Compare to anchors), U (Don't know), Up/B, E, Down/W and
#           Backspace (Better / Same tier / Worse / Back), and in the duel view Left/A, Right/L,
#           Down/T and S (cards, Tie, Skip). Disabled buttons do not dip. Respects Reduce motion
#           (no dip, the action still happens). Input is never delayed: the action runs first.
#           Built: App._key_target(ks) is the one key -> (button, action) map for each view (place, comparing,
#           duels); on_key runs the action, then button.flash(). A disabled button's key is off too (Space
#           no longer starts a comparison while Compare is greyed out). RoundButton.flash skips the dip with
#           Reduce motion. Covered in tests/_selftest_ui.py.
# [x] UI-19 Duel result. adds DuelCards.resolve(side): the winner lifts slightly and the loser
#           dims (~120 ms) before the next pair; a boundary swap shows the two chips trading
#           places.
#           Built: DuelCards.resolve(side): the answer is saved at once; the winning card rises off its
#           shadow (the same lift the cards now have on hover) and the other fades to its disabled look
#           for 120 ms, then the next pair. A key press goes straight on; clicks during it are ignored.
#           The "two chips trade places" for a boundary swap was left out to keep things lean: the swap
#           toast already says what moved.
#           Later (asked for): the duel cards wear their word's tier colour in Refine, Boundary check and
#           Resolve conflicts (DuelCards.show(colors=)); a word with no tier gets a neutral pastel.
#           Fixed (reported): the cards sat left of centre when the line under them (the conflict note) was
#           wider than they are; DuelCards centres its grid (grid_anchor "n").
#           Fixed (reported: sorting very fast, the buttons moved as the card changed): a long word shown in a
#           smaller font made the card shorter (its padding follows the font) or, a pixel over the wrap limit,
#           wrapped onto two lines and made it taller, so everything below re-centred; and an odd card width
#           shifted the centring by a pixel. (First patched with a minimum height; since replaced by a card of
#           one fixed size, UI-44 (8).)
#           The key hint in the bottom bar no longer has a fixed wrap width (it broke onto two lines when zoomed).
# [x] UI-20 Friendly empty states. adds show_empty_state(kind): short, warm messages ("Nothing to
#           refine yet", "No conflicts - nicely consistent") on a soft card instead of dashes.
#           Built: widgets.EmptyCard (a soft rounded panel with a title and a line of text); App.EMPTY
#           holds the Refine / Boundary / Conflicts messages, and Place shows "Every word is placed".
# [?] UI-21 Next-up peek (optional). adds Store.upcoming(n) and a faded line with the next two
#           words under the card, so the eye can pre-read and the flow stays quick.
#           Shelved (asked for): on the "In consideration" list under Decisions; not built for now.
#
# --- Phase 6: polish ---------------------------------------------------------------------------
# (UI-22, the dark theme toggle, was dropped from the plan by request; IDs are not renumbered.)
# [x] UI-23 Browse window restyle. The Browser uses the shared theme and fonts, pastel tier rows,
#           and RoundButton "Move to" chips. Keeps its scale-with-window behaviour.
#           Built: the toolbar on a white band with a hairline (like the main header); rows in a soft wash
#           of their tier colour (theme.TIER_ROW, theme.tint), the selected row in the full colour with its
#           outline; every button a RoundButton (A- / A+ and Refresh quiet flat ones); the definition a
#           white pane under a muted heading instead of a grooved frame.
# [x] UI-24 Dialog restyle. adds styled_dialog(title): a shared frame so the Anchors, Queue and
#           Merge dialogs match the rest. The bottom bar (Undo, Browse / edit, Definition, key
#           hints) keeps its current look by request; only dialogs change here.
#           Built: widgets.StyledDialog (headline, muted intro, body, rounded buttons with the lilac
#           default on the right; Enter / Escape). Anchors and Queue use it and show problems inline;
#           errors.py's dialogs (errors, questions, tick boxes) and the new show_message are built on it,
#           so the merge / import / save-file messages and Browse's notes no longer use tk's messagebox.
#           errors.py now sits after widgets.py in the layers.
# [x] SZ-1  Screen- and content-aware window sizing (sizing.py). Windows open at a size derived from
#           the monitor under the pointer and the dpi scaling, fonts step down (and the definition
#           pane shortens) when contents would not fit, dialogs are centred on screen.
#           Browse and start-up windows size from measured text. Browse selection is an outline.
#           Covered by _selftest_sizing.py.
# [x] UI-25 Responsive sizing. adds scale_fonts(width, height): the word card and buttons scale
#           with the window, like the Browse window already does.
#           Built: App.grow (_grow_for, _apply_grow): past its preferred size (or what the contents need,
#           if more) the window scales every shared font in proportion, in 5% steps up to 1.75x, 80 ms
#           after resizing pauses (~0.1 s per step). Grow only: the minimum size stays the one measured at
#           the normal size, so the window always shrinks back. A zoom makes the window's current size the
#           new "normal". Switching tabs while grown does not flash back to the normal size.
# [x] UI-27 Keyboard fix (asked for; only if still needed): pressing Down must never open the drop-down
#           of the current tab (the Tier / Boundary choice in Refine and Boundary) instead of doing its
#           job (Tie). A click leaves keyboard focus in that drop-down, so the next Down opens it. Check
#           first, then hand focus back to the window whenever the drop-down closes, picked or not.
#           Related: with a header menu open, Left / Right should move to the neighbouring menu.
#           Checked (openbox + xdotool): Down no longer opens a drop-down (ChoiceButton has no keys of its
#           own since UI-43), but closing any drop-down with Escape or by clicking its button again left
#           the program with no keyboard focus at all, so Down (and every key) did nothing until a click.
#           Fixed: DropMenu gives the focus back to where it was when it opened, only if it still had it
#           (switching to another program still closes it and leaves that program in front). Left / Right
#           in an open header menu open the neighbouring one, wrapping round.
# [x] UI-31 A view of its own for each tab (asked for: the tier chart is only for Place new words). Ideas,
#           each to be shown and approved first: Refine: how settled each tier's order is (the share of
#           its words with enough duels), six bars in the same tier colours. Boundary: the five
#           boundaries S|A .. D|F as a short strip, each with how many checks and swaps it has had.
#           Conflicts: not a chart, a single number ("3 to look at" / "none - nicely consistent").
#           Approved from mock-ups: Refine as shown; Boundary as the pill strip (option A) with only the swaps,
#           one number per join and a single "swaps" caption (no check totals); Conflicts as shown.
#           Built (ui_chart.py): SettledChart (a word counts as settled at App.SETTLED_DUELS = 5 duels;
#           Store.settled_shares, index-only on the new idx_words_tg, ~50 ms with a million placed words),
#           SwapStrip (Store.swap_counts from the new swaps table: one row per boundary duel that swapped,
#           taken off again by undo; counted from now on, earlier swaps were never recorded; the join being
#           checked is bold), ConflictCard. All four views share one spot in the status band, the current
#           one raised and the others hidden, so switching tabs never moves the page.
#           Fixed (reported): switching from Place new words while the chart was still growing (or a bar
#           glowing) left the chart drawn under the next tab's view; a hidden chart now stays hidden mid-animation.
#           Then (asked for): Boundary check's swap strip archived (see "In consideration"); that tab shows no
#           view in the spot. The save still counts swaps per boundary (swaps table, Store.swap_counts).
# [ ] UI-32 Soft moving background (asked for): a pastel polka-dot or blob pattern behind the main page,
#           drifting and jiggling slowly. Two things to settle before building:
#           - It goes against a guardrail above ("nothing loops or moves while idle"), so it needs your
#             OK to relax that one rule for the background only. Proposed limits: very slow (a full drift
#             takes many seconds), a few frames a second rather than 60, faint colours just off the
#             cream, off with Reduce motion (then a still pattern), paused while the window is not in
#             front or minimised, and never touching the database.
#           - tk has no transparency: every widget is an opaque rectangle, so a pattern drawn behind the
#             page would show only in the empty space around the card and buttons, and each widget would
#             sit on a plain cream box. To look right, the pieces on the page need their canvases to
#             paint the pattern under themselves, or the page becomes one canvas. Try it on a small
#             mock-up first and show screenshots before committing to it.
# [x] UI-33 Pace and hover-note polish (asked for, four parts):
#           1. Pace with a timeout: the rate counts only active time. The time between two actions counts
#              up to a cap (about 2 minutes); a longer gap is a break and adds nothing, so stepping away
#              does not drag the number down. (Today it is actions / time since the window opened.)
#           2. Wording: the hover says "about 120 per hour" (not "an hour").
#           3. The hover note stays where it first appeared (next to what it describes) instead of
#              following the pointer.
#           4. The hover note matches the theme: rounded corners, the soft lilac surface and hairline used
#              by the drop-down menus, the shared fonts; the same look for every Tooltip (chart, "+N
#              today", later ones).
#           Built: App._count_action adds the time since the last action, capped at PACE_GAP_S (120 s);
#           Tooltip opens just below its widget (or beside it, side="right", for "+N today", which has the
#           progress bar under it) and keeps its place while its text changes; drawn as a rounded faint-lilac
#           card with a hairline (corners painted in the page colour: tk windows cannot be see-through).
#           Then (asked for): the notes say just "22,574 of 90,000 placed" and "about +120/hr" (nothing
#           until there is enough to say); a note is drawn and placed before it shows (no blank white box
#           flashing first); "covers 92%" is quiet grey text after the bar, like the segment labels.
# [x] UI-34 Status line: "Placed N of M (x%)" stays and the "N left" part goes (it repeats what placed / total
#           already says). The frequency-weighted coverage becomes the tag beside the progress bar (UI-14).
# [x] UI-35 The definition drawer did not open smoothly (reported). Measured frame by frame under a real window
#           manager: pressing D blocked ~150 ms in a full window-fitting pass, then the first update took
#           ~280 ms more because every frame of the slide re-fitted and redrew every button (each change
#           of the page's height ran _fit_big_text + refresh_widgets), so the 200 ms slide had already
#           ended when the screen first showed it. Fixed: a height-only change of the page only re-centres
#           (wrapping depends on the width); opening does one quick size check instead of the full fit
#           (the full fit runs only when the drawer does not fit); _fit_window skips re-scaling fonts that
#           are already the right size; and the drawer is packed folded, so it never flashes at full
#           height first. Now: the slide starts within ~25 ms (was ~430) and runs one frame every ~17 ms,
#           opening and closing. Also: switching tabs finishes a duel result still showing.
#           Later (reported: the drawer flickered opening when zoomed in): with no room, the fit showed the drawer
#           open at full height for every size it tried. It now stays folded and is counted at its full height
#           (_fit_window(folded_drawer=True)); the text steps down once to what fits, then the drawer slides.
# [x] UI-36 Tier chart: no hover note at all (asked for: remove it from the whole chart). Done in the tidy-up.
# [x] UI-37 Compare to anchors: Space toggles it (asked for): Space starts comparing, Space again leaves it
#           (what Escape does today), so Backspace is no longer how you get out. Backspace / Back keep
#           stepping back one answer while comparing (confirmed). The Compare button's key hint and the bottom-right
#           hint follow.
#           Built: Space (or Escape) leaves; Back is greyed out until there is an answer to step back from, so
#           a held Backspace stops at the first question; the bottom-right hint reads "Space stop comparing".
# [x] UI-38 Browse window opening and closing (asked for): a quick opening animation (about 150 ms: it eases
#           in from slightly smaller; preferred over a fade), and a click on the main window's empty
#           background closes it (not a click on a pill, card or button, so a quick click never loses your
#           place). Its unsaved state (search, filter, scroll) is
#           remembered for the next open, so closing by accident costs nothing.
#           Built: it eases out from 94% of its size round its centre once it is on screen, and the list
#           fills when the ease ends (loading rows mid-ease made each frame 40-60 ms; now ~6 ms). A click on a
#           bare frame of the main window closes it (App._click_background; not the pills' row, cards,
#           buttons, labels or the shelf). Search, Show, Sort, the selected word and the scroll position come
#           back on the next open (for this run of the program). Reduce motion: no ease.
# [x] UI-39 Browse: the Delete key (and Backspace on macOS) unplaces the selected word(s) (asked for), same as
#           the Unplace button, with undo.
#           Built: Delete (keypad too; Backspace on macOS) in the list unplaces the selected word, anchors
#           still protected; Ctrl+Z (Cmd+Z) in Browse undoes the last saved action and shows it there. Typing in
#           the search box is unaffected. (Browse selects one word at a time.)
# [x] UI-40 Anchors follow their tier (asked for): when an anchor word is moved to another tier (Browse, a
#           duel swap, a merge), its old tier gets a new anchor straight away: if it moved down, the word
#           ranked just below it in that tier; if it moved up, the word ranked just above it. A short
#           toast says so ("table moved to C; the B anchor is now gristle"). If the old tier has no other
#           words, its anchor slot stays empty until one is picked (confirmed). Today the moved word stays
#           registered as the old tier's anchor, which is quietly wrong.
#           Built: Store._follow_anchors runs after every tier change (place: Browse's Move to; a boundary
#           swap) and returns what changed; ties in rating are fine (any of the equals). Undo puts the
#           anchors back (the history keeps them). Browse's Move to no longer refuses anchor words; moving a
#           word to the tier it is already in does nothing (it used to reset its duels). App.anchors now
#           reads the save each time. A merge never moves placed words, so it cannot move an anchor.
#           Unplace (back to queue) still refuses anchor words.
# [x] UI-41 Queue randomness dialog: two small diagrams (asked for), the exponential and the gaussian drop-off
#           drawn as soft pastel curves (chance of coming up early against frequency rank), the chosen one
#           highlighted and redrawn live as spread changes. The intro text shrinks to one line.
#           Built (mock-up A, chosen): a card per shape (widgets.ShapeCard) replaces the radio buttons; a click
#           picks it. The chosen card is white with a lilac edge, its curve filled (peach / sky) and a dotted
#           "half by #13.9k" line; the axis is fixed (#1 to #100k, constants.QUEUE_AXIS) so typing a spread
#           visibly reshapes the curves. The old "half of early words rank below" note is gone (the card says
#           it). The intro no longer says gaussian "drops off faster": it is flatter at first and only falls
#           faster past about 2 spreads, which the curves now show.
# [x] UI-42 File dialogs (Import earlier progress, Export tier list): clicking the label next to the file-type
#           drop-down should open the drop-down too; today it flickers open and shut. Applies to the file
#           browser in general. Seen on Linux, where tk draws this dialog itself: fix it there, or replace
#           it with a small themed file picker that matches the app (Windows and macOS keep the system's
#           own dialog).
#           Built (mock-up C with A behind it, chosen): filepicker.py, on Linux only. Import lists what it
#           finds first (other saves with how many words they have placed, and exports named like a tier
#           list, newest first); "Look somewhere else..." opens the browser. Export asks for a name, a format
#           (Text / CSV / Markdown pills) and shows the folder as steps; "Change folder..." opens the browser
#           to pick a folder; the folder and format are remembered (meta export_dir / export_kind); replacing a
#           file asks first. The browser: places (Home, Desktop, Documents, Downloads, next to your save), the
#           path as clickable steps, a list (widgets.FileList) of folders and the files that fit; Enter /
#           double-click opens, Backspace goes up. No tk menus anywhere, so nothing grabs input or floats over
#           other programs. _selftest_filepicker.py.
# [x] UI-43 Bug (reported, Linux): open a drop-down, switch to another program (Chrome, say), and the drop-down
#           stayed in front of that program. First fix (closing menus when focus left) did not work: tried
#           again with a real window manager (openbox + xdotool), the Tier list (a ttk.Combobox) grabs all
#           input while open, so no focus event ever arrives. Fixed for real: the Tier / Boundary choice
#           and Browse's Show / Sort are now ChoiceButtons (a button + the same DropMenu as the header
#           menus, which never grabs input); watch_focus asks Tcl who has the focus and closes every open
#           DropMenu when the program loses it; nothing is "always on top". Verified with the window
#           manager: both the header menus and the choice lists close on switching away. (Tk's own file
#           dialog still uses tk menus that grab input: replaced by the themed file picker in UI-42.)
# [x] UI-44 Fixes after trying UI-16..19 (reported): (1) the placement pill no longer flies as a box over
#           the chart: it shrinks into a small drop as it flies (tk has no transparency, so a full-size
#           pill was an opaque box); (2) Refine within tier (and every duel) now shows a short result
#           message, "apple > pear", like Boundary's swap note; (3) sorting fast: each message is its own
#           pill, the newest on top, and older ones (and every other running animation) speed out of the
#           way within 90 ms (Animator.hurry / hurry_all, Toast.hurry) instead of jumping; a word that
#           interrupts the card's transition shows at once; (4) content is centred in the visible page
#           (tab line to bottom bar), which fixes Resolve conflicts sitting low; (5) more room between
#           the word card and the tier pills.
#           Then (reported: white flicker when placing fast with the number keys): (6) the word card no longer
#           goes blank: a redraw during its transition (the card resizing for the next word) kept deleting the
#           outgoing word or tucking it under the card's face, and the crossfade left a gap where both words
#           were near white; (7) the placement pill picks its backdrop (white on the card, cream elsewhere)
#           from its whole rectangle against where the card is now, not from its height alone, which painted a
#           white box beside the card (over the tier buttons); it comes out at the card's top edge instead
#           of over it, and a long one narrows to a round drop before it reaches the chart bars.
#           Then (reported again: buttons moving or covered while sorting fast, even with Reduce motion):
#           (8) the word card has one fixed size, from the fonts and the room only, never from the word; a long
#           word is fitted inside it in a private copy of the font (smaller, then wrapped), so placing a word
#           changes no widget's size and no shared font. Before, the card hugged the word: the centred block
#           shifted a pixel either way and, for a frame, went wide before the font was shrunk. Found and
#           checked with tools/layout_trace.py (frame-by-frame widget geometry: moves, spikes, overlaps).
#           (9) Then (reported: a "white text" copy of the word showing): mid-transition the paler word was drawn
#           over the darker one and cut white gaps through its letters (tk cannot blend); the darker of the
#           two is now always on top, swapping halfway.
# [x] UI-45 Zoom the whole main window (asked for): View > Zoom in / Zoom out / Actual size, and Ctrl + /
#           Ctrl - / Ctrl 0 (keypad too). Every shared font scales (60-200%, steps of 10%), so buttons,
#           cards, the chart and menus follow; saved in the save (meta zoom). It multiplies the screen-fit
#           scale, so a zoom never pushes the window past the screen. (Browse keeps its own zoom.)
#           Plain messages (zoom, skip, duel results) now appear just above the bottom bar, clear of the card.
#           Fixed (reported): on a screen too small for the zoomed contents, switching tabs or closing the
#           definitions lost the zoom (the screen fit shrank the fonts a step and never grew them back), and
#           zoom out could then jump. Now what shows is the zoom or the biggest size that fits (0.1 steps),
#           whichever is smaller, worked out again on every change (remembered per layout, so no flicker);
#           closing the definitions re-fits once the drawer is out of the way. Zoom out is always one step
#           and never makes anything bigger; a zoom in that cannot get bigger says "as big as fits" and
#           changes nothing. In a window enlarged by UI-25, Ctrl + / - step from the size on screen.
#           Main and Browse keep separate zooms, both saved (meta zoom / browse_zoom). _selftest_zoom.py.
#           Then (reported: holding Ctrl + caused trouble): the zoom keys are paced like every held key; a
#           zoom in that did not fit is remembered per layout (tab, definitions pane, screen) and refused on
#           the spot afterwards, so a held key tries it on screen once at most; a repeated refusal wiggles
#           the one "as big as fits" message side to side (Toast.wiggle) instead of stacking new ones.
#           Then (reported again: the zoom "reset" on opening / closing the definitions or switching tabs, and
#           went closer than 100% and closer than zoom in allows): the UI-25 growth, not the zoom. Each fit
#           re-measured the size that counts as "normal" smaller than the window, so the contents grew to fill
#           it, past the zoom and past the screen-fit limit. Now that size is set when the window opens and by
#           a zoom, and later fits may only raise it, so the contents grow only when you enlarge the window.
#           Checked under a real window manager at 1366x768, 1920x1080 and 2560x1440, with the window normal,
#           enlarged and maximised, zoomed in and out (18 cases, all keep their size); _selftest_zoom covers it.
# [x] UI-46 Tabs only when they have something to do (asked for): the "Refine within tier" tab is hidden
#           while no tier holds two words yet (only at the very start), "Boundary check" while no two
#           neighbouring tiers both hold words, and "Resolve conflicts" while there are no conflicts. A tab appears (sliding in, with the same 180 ms ease as the tab bar) as soon
#           as it has work, and goes when it has none. If you are on a tab when its last piece of work is
#           done (the last conflict resolved), it stays until you leave it, showing its friendly empty
#           state (UI-20), so the page never vanishes under you. The saved mode falls back to Place new
#           words if its tab is hidden at start-up. The check uses cheap counts (Store.tier_counts and
#           the conflicts count, already read for the status line), never a scan per refresh.
#           Built: TabBar.show_only(keys) folds tabs away / grows them in; App.modes_with_work(stats).
# [x] UI-50 Queue randomness Apply (asked for): Apply & reshuffle with nothing changed says "No settings
#           changed" (inline, cleared by the next edit; the dialog stays open, confirmed) instead of reshuffling. Otherwise the reshuffle runs on
#           a worker thread while the dialog shows a back-and-forth (indeterminate) bar, its buttons greyed
#           and Escape waiting, so the window keeps drawing (the buttons were clipped while it blocked); it
#           closes itself when done. App.busy holds back the definition cache's writes meanwhile. With
#           Reduce motion the bar stands still.
# [x] UI-51 Look up a word to sort it (asked for): a little search icon opens a search over the whole unsorted
#           list (as you type, like Browse's search, but over words not placed yet); picking one makes it the
#           word on the card in Place new words, to sort now, without changing the queue order for the rest.
#           Where the icon goes is to be talked over first (beside the word card, in the header, or the tab
#           row). (Browse can already find placed words; W-1 looks words up from inside a definition.)
#           Built (decided: the icon at the top right of the word card, typing on the card itself): a magnifier
#           (smooth.ICONS "search") in the card's corner, darker on hover, its note "Look up a word (/)"; it or
#           the / key (keymap action "find", changeable) turns the card into the place to type (a pale "type a
#           word", a thin lilac caret, "Enter: sort it · Esc: back"). Enter: an unplaced word comes up to sort now
#           ("- looked up"; the rest of the queue keeps its order, App.looked_up until placed or skipped); a placed
#           one shakes the card ("Already placed in B · Browse to change it"); one not in the list shakes it
#           ("Not in the word list · Enter again to add it") and Enter again adds it (Store.add_word: the last
#           rank, the back of the queue, nothing else redone) and brings it up. While typing every key is the
#           card's; a tab switch, Escape or the magnifier again puts the word back. _selftest_lookup.py.
# [x] UI-52 Shelf hover (asked for): hovering a spine darkens its outline and lifts it a little off the
#           shelf, its left and right neighbours less (Bookshelf.hover; eased 140 ms, at once with Reduce
#           motion; moving along the shelf never snaps). The shelf has that much room above it.
# [x] UI-53 Smooth shapes (reported on Windows 11: the queue dialog's curve, the tier pills, buttons and chart
#           bars looked pixelated, and the bars had little bumps on their corners). Tk draws canvas shapes
#           with no anti-aliasing, and the old rounded-corner trick (a smoothed polygon) left bumps. Tk 8.6
#           cannot draw SVG, so smooth.py draws each rounded shape into a small image with soft edges
#           (SmoothCanvas.round_rect): the very outline Tk drew before (so the pills keep their rounded-square
#           look), filled with exact left / right edges and 4 sub-rows per row, and a soft 1 px hairline.
#           The shape is still an (invisible) canvas polygon, so tags, coords, move, delete, stacking and
#           itemcget("fill") work as before; its image follows it. Fast enough to animate: a shape's
#           coverage is worked out once (its straight middle is stretched, not recomputed, so growing bars
#           and shrinking messages cost almost nothing), colours snap to steps of 4 so fades reuse images,
#           and a shape on the plain canvas colour is blended in advance into a solid image (Tk on Linux
#           blends see-through pixels slowly); the word card carries its shadow in its own image. The queue
#           dialog's curve is one smooth image too. _selftest_smooth.py.
# [x] UI-54 Windows: sharp at display scaling, and pop-ups on the right monitor (reported: a drop-down on a
#           second monitor opened at the far side of the main screen). Pop-ups were kept inside Tk's screen
#           size, which on Windows is the main monitor only; now sizing.monitor_at / clamp_to_monitor keep
#           drop-downs, hover notes and dialogs on the monitor they open from (the monitors' work areas come
#           from Windows, as they already did from xrandr on Linux). set_dpi_awareness() runs before the first
#           window: per-monitor display scaling, so at 125% / 150% Windows no longer stretches the window
#           like a picture (soft, pixelated text and edges) and positions are real pixels. Not yet tried on a
#           real Windows machine (the calls are covered by tests with stand-ins). Tk 8.6 does not re-scale
#           when the window moves to a monitor with a different scaling: it keeps the size it opened at.
# [x] UI-55 Where the words are, on the shelf (asked for): in Refine within tier, Boundary check and Resolve
#           conflicts, a little triangle pointing down at the spine (book) each word on screen comes from;
#           when both words are in the same spine, one triangle only.
#           Built: Bookshelf.mark(spines) draws a small soft lilac triangle over each (a band above the shelf
#           holds them; a mark rises with its spine on hover); Store.spine_of(word) finds the spine from the
#           word's rank. Cleared in Place new words and when a tab has no duel.
# [x] UI-56 The definitions pane fits its senses (asked for: "tries to open so all the definitions are visible; if
#           it can't due to space limitations it shouldn't"). DefinitionDrawer.lines_needed() counts the text's
#           pixels at its width; App._fit_defs raises the pane's lines to that (9 usual, at most 40) and refits:
#           the window grows if the screen has room, else _fit_window gives the pane the lines that fit (before
#           any smaller font). It only grows from word to word (shrinking for each short one would make the
#           page jump on every word) and is back to 9 lines when the pane is closed. A window grown past the
#           screen's edge is now moved back onto it (it grew downward from where it opened).
# [x] UI-57 A zoom for the maximized window (asked for: "when maximized ... the zoom it last had while maximized,
#           and vice versa", so every window size keeps its own relative size). The main window keeps two zooms:
#           "zoom_max" for it maximized, "zoom" for any other size; a zoom chosen while maximized is kept as the
#           first, and maximizing or restoring brings back the one kept for that state (App._follow_maximize,
#           sizing.is_maximized: the state "zoomed" on Windows / macOS, the -zoomed attribute on Linux), after a
#           restart too. Maximized before a zoom was ever chosen there, the contents grow with the window (UI-25).
#           A fit no longer moves or resizes a maximized window (that un-maximizes it). Found while testing it: in a
#           grown window, Ctrl - from 130% said "as big as fits" and fell to 100% (a step down to 120% was taken
#           for a zoom in); now it steps 120%, 110%. Checked for real: Xvfb + openbox, maximize and restore.
# [x] UI-58 View > Censor obscene words (asked for): the same switch as in How words are dealt, as a tick in the View
#           menu (App.toggle_censor). The card, the duel cards, the definitions and Browse follow at once, and a
#           comparison carries on; a change made in How words are dealt shows in the tick too.
# [x] UI-59 The kind of a rude word, faintly above it on the card (asked for: "bum-fuck should have sexual right
#           above it"; kept whole, never clipped). rudeness.main_kind: of the censored kinds, the one the word's
#           meanings give most points (as word_points counts them: its first meaning most): fuck, cunt, wanker sexual,
#           shit, piss, bullshit crude, motherfucker a swear word, kike a slur; a word that is only forms of another
#           takes that one's. Kept in words.rude_main (RUDENESS_VERSION 11: every save scores again once);
#           Store.rude_kind. WordCard.set(kind=) draws it in the card's top margin, centred between the edge and
#           the letters' tops (0.8 em above the baseline), its font made smaller if that room is ever too low; the
#           card's size never changes. Checked pixel by pixel at 50-200% with short, long, wrapped and accented
#           words: never cut off, never touching the word. Words not smeared whole show nothing.
# [x] UI-60 A duel's definitions side by side (asked for: "on their respective sides in two column format"). In
#           Refine, Boundary check and Conflicts the definitions pane shows the left card's word on the left and the
#           right card's on the right, a hairline between (DefinitionDrawer: a second text, two equal grid columns
#           sized so together they ask no more room than the one column, so the window never widens; set_lines /
#           lines for both; lines_needed is the taller one). One word, or a looked-up word (W-1), is one column.
# [x] UI-48 Keyboard shortcuts menu (asked for): Settings > Keyboard shortcuts... opens a dialog listing every
#           action that has a key (place in S..F, compare to anchors, don't know, better / same / worse /
#           back, left / right / tie / skip, undo, definitions, next / previous tab, zoom), grouped by
#           view, each with its current key(s). Click a key, press the new one, done; a key already used
#           in the same view is pointed out ("U is already Don't know: swap them?") instead of silently
#           taken. "Reset to defaults" per row and for all. Saved in the save (meta keymap), so it
#           survives restarts. Everything that shows a key follows the change: the button hints (1, Space,
#           U, Up / B...), the bottom-right hint and the menus' shortcut column. Builds on UI-18's single
#           key map (App._key_target), which becomes a table the dialog edits. Reserved keys that cannot be
#           rebound: Escape (cancel / close) and the Alt+letter menu keys.
#           Built (layout C chosen: cards side by side; decided: the 1-6 placing keys are one row that moves as
#           a set, and every key can be changed, Ctrl ones and Escape too; only Alt+F / E / V / S and F10, which
#           open the menus, are refused): keymap.py (no tkinter) holds every action, its view and default keys,
#           the user's changes (meta keymap, only what changed), event_spec (a key press -> "Ctrl+z", keypad =
#           main keys, Command = Ctrl on macOS), lookup (a view's own keys first, then the Everywhere ones, so
#           Backspace is Back while comparing and Undo otherwise) and clash. App.on_key and Browser._on_key go
#           through it (the separate Ctrl+Z / zoom bindings are gone); App.apply_keys puts the keys in the button
#           hints, the Definition button, the menus and the bottom-right hint. shortcuts.ShortcutsDialog: click a
#           key, press the new one ("+" adds one, up to 3; Remove; "↺ default" per row; Reset all); a key used in
#           the same view offers a swap ("W is already Worse. Swap them: Worse gets ↑?"); the placing set takes
#           its first key and the five after it on that keyboard row (1, Q, A, Z, F1...). In Browse, plain keys
#           type in the search box as usual. _selftest_keymap.py, _selftest_shortcuts.py.
#           Fixed (reported: Reset all to defaults made the window flicker smaller and black): every change
#           rebuilt all the rows, emptying the dialog for a moment (Windows paints that at once), and re-fitted
#           its size. Now the rows are built once; a change refills only its own keycaps, new ones in before the
#           old go, and the window only grows when a row needs it.
#           Fixed (reported: the dialog opened at the main window's top left, then flickered down to the middle):
#           building it showed the window before it was placed. Every StyledDialog now stays hidden until show()
#           has sized and centred it, so it first appears where it stays (all dialogs, not just this one).
# [x] UI-49 Bug (reported): holding a tier key kept placing words, and lagged on after the key was released
#           (auto-repeat sends ~30 presses a second, faster than placing, so they queued). Fixed: a held key
#           repeats like a keyboard's own defaults: nothing for 500 ms after the first press, then at most
#           one action per 250 ms; faster repeats are dropped, so nothing queues. Held keys are recognised on
#           Windows (presses without releases) and X11 (release + press with the same timestamp). Applies to
#           every action key. Measured with a real held key (xdotool): 1.5 s held placed 23 words before, 5
#           now, and none after release.
#           Later (reported: holding a key in Refine crashed the PC): could not be reproduced here (a held key
#           in Refine or Boundary on a 300,000-word save: memory flat, ~3.5 duels/s, stops on release), but
#           two hazards were fixed: Boundary check built every pair of the weakest / strongest 5% of two
#           tiers (25 million pairs, gigabytes and ~40 s on a big save; now at most 30 a side, ~0.15 s,
#           Store.BOUNDARY_POOL), and a held key's next repeat now waits 250 ms from when the last action
#           finished (App._action_done), so a slow save still gets time to draw between repeats.
# [x] UI-28 Anchor words dialog clean-up (asked for): tidy and prettify the Anchor words pop-up: the tier
#           letters as the same pastel pills as the tier row, roomy aligned entry fields, a short friendly
#           intro instead of the three-line block, inline "not in the word list" / "used twice" notes
#           under the field instead of separate error boxes, RoundButton Save / Cancel. (UI-24 restyles
#           the other dialogs; this one gets its own pass because it is the first thing a new user sees.)
#           Built: widgets.TierChip (a rounded pastel tier label like the pills), wider entries, a two-line
#           intro, and per-field notes ("Fill this one in", "Used twice...", "Not in the word list") that
#           clear as soon as that field is edited. On the shared StyledDialog (UI-24).
# [-] UI-29 Tier letters as hotkeys: dropped by request; placing stays on the number keys 1-6 (and the
#           buttons), so D keeps showing definitions and the duel keys keep their meanings.
# [x] UI-47 Tab moves between the tabs (asked for): Tab goes to the next tab (Place new words -> Refine ->
#           Boundary -> Conflicts -> back to Place), Shift+Tab to the previous one, skipping any tab hidden
#           by UI-46. It does exactly what clicking the tab does (the open tab slides over, the view
#           switches). Tab no longer moves keyboard focus between widgets in the main window (nothing there
#           takes focus anyway); dialogs and Browse keep the normal Tab between fields. The bottom-right
#           hint gains "Tab next tab" (no button shows it).
#           Built: App.next_tab(d), from on_key (so held-key repeat and "nothing while a menu is open" apply);
#           Shift+Tab is ISO_Left_Tab on X11 and Shift-state Tab elsewhere. The hint shows "Tab next tab"
#           only while there is more than one tab. Checked with real keys (openbox + xdotool), dialogs too.
# [x] UI-30 A link per package (changed by request: hover notes dropped, since the install dialog already
#           says what each package is for). Each package's name in the dialog links to its own web page
#           (wordfreq: https://pypi.org/project/wordfreq/, nltk: https://www.nltk.org/), opened in the
#           browser with webbrowser.open; styled as a quiet underlined link in the muted colour. In the
#           terminal (tkinter), the page address is printed after the package's line. One table
#           (deps.HOMEPAGE) feeds both.
#           Built: a choice in errors.ask_choices can carry (link text, url); the tick box, the name as the
#           link (darker on hover, opens with errors.open_link = webbrowser.open), then the rest of the
#           label, which still ticks the box. terminal_setup prints "More about it: <address>".
# [x] UI-26 Final pass.  Performance check on a ~1M-word save (no animation frame touches the
#           database), refresh the module docstring, and add a UI smoke test that drives every
#           mode and saves screenshots.
#           Done: _selftest_smoke.py drives Place (keys, Don't know, comparing, a looked-up word,
#           definitions), Refine, Boundary, a conflict, zoom, Tab, undo, Browse (sorting both ways), the
#           Anchor / Queue / Keyboard shortcuts dialogs and every header menu, fails on any error raised in a
#           callback, and saves a screenshot per stage (SMOKE_SHOTS, else a temporary folder; Pillow). On a
#           1M-word save (5,000 placed): placing ~26 ms, a duel 15-23 ms, a tab switch ~17 ms, Browse ~95 ms;
#           animation frames median 0.6 ms, worst 7 ms, no queries at all; opening ~0.8-1.1 s (0.25 s of it the
#           shelf's tallies, counted once). The docstring's "How it works" names the newer features.
#
# --- Window by window (asked for: every window's planned changes in one place) -------------------------
#   Main window ........ header + tabs (UI-10, UI-27), status line (UI-15, UI-34), tier chart (UI-13,
#                        UI-31, UI-36), word card and its motion (UI-6, UI-16, UI-17), keys (UI-37,
#                        UI-47), duel view (UI-8, UI-19), empty states (UI-20), next-up peek (UI-21),
#                        definition drawer (UI-12, UI-35), background (UI-32), responsive sizing (UI-25)
#   Browse / edit ...... restyle (UI-23), open / close (UI-38, M-5), Delete unplaces (UI-39), sort by
#                        clicking a column (M-7)
#   Anchor words ....... clean-up (UI-28), anchors follow their tier (UI-40)
#   Keyboard shortcuts . new dialog (UI-48, done)
#   How words are dealt  diagrams (UI-41), shared dialog look (UI-24), grew out of Queue randomness (ST-6,
#                        done; also the first start's three steps)
#   Import / Export .... file dialog (UI-42), spacing and icons (M-8..M-10)
#   Merge offer, "Where is my save file?" ... shared dialog look (UI-24, done)
#   Install packages ... tick boxes + sizes (ST-4, done), a web link per package (UI-30)
#   First-run progress . shared dialog look (UI-24)
#   Error dialog ....... shared dialog look (UI-24)
#   Hover notes ........ still and themed (UI-33)
#   Source & Updates ... T-6 / T-7 (later)
#
# --- Last: definitions as a way in (asked for; at the very end of the plan) --------------------------
# [x] W-1  Click any word inside a definition to look it up. Its definition appears (the drawer and the
#           Browse pane), and the word joins the Browse list for the moment as a greyed-out row under F
#           ("not placed yet"). In Browse you can then sort it straight away with the tier buttons or
#           the 1-6 keys, which places it for real (it leaves the queue like any placed word); if you
#           do not, it disappears from the list again when Browse is refreshed or closed. Words that
#           are not in the word list are offered as "add to the list" first.
#           Built: in both panes the word under the pointer (in a meaning, an example or a form's line, not a
#           heading or label: widgets.word_at, LINK_TAGS) is underlined with a hand; a click calls on_word
#           (fill_definitions). App.look_up keeps it in app.lookups (a word not in the list: "Add it" / "Just show
#           it", the definition shows either way). The main window's pane shows the clicked word under a "Back to
#           ..." line (App.def_lookup, until then or the next word); Browse shows waiting words as rows at the
#           bottom (Browser.show_lookups: an unplaced one greyed with "not placed yet" in the Rating column, which
#           widens for it), kept at the bottom as more rows load, gone on a refresh or close; clicked in Browse's own
#           pane, the row is selected. Browse now takes the placing keys (1-6, the keymap's) for the selected word,
#           like its tier buttons. _selftest_lookup.py.
#
# --- Packaging as a program (T-6..T-8 asked for; built after the UI steps) ----------------------
# T-1..T-3 are the groundwork for T-6..T-8; T-4 was dropped, T-5 is the release's notes.
# Notes from the discussion: PyInstaller builds only
# for the OS it runs on (no cross-compiling), so this would be a build.py run once per OS, and only
# Linux can be tested from here (Windows / macOS builds would need testing on those machines).
# [x] T-1  app_dir(): a save/config folder that is the executable's own folder (or the home folder)
#          when frozen. REQUIRED before any build: a one-file build unpacks to a temporary folder,
#          so a save kept "next to the script" would be deleted when the program exits.
#          Built: saves.app_dir(): from source tierlist.py's folder (unchanged); built (sys.frozen) the folder
#          the program sits in (saves.program_dir: on macOS the folder holding the .app, not inside the
#          bundle, which a new version replaces); a read-only one (Program Files, a disk image; tested by
#          really making a file, os.access is wrong there on Windows) falls back to saves.user_data_dir
#          (%APPDATA%\Word Tier List, ~/Library/Application Support/Word Tier List, $XDG_DATA_HOME or
#          ~/.local/share/word-tierlist), which find_saves also searches. The save you used last is still
#          found first (the pointer file in your home folder), so source and program share one save.
#          saves.restart_args: a built program restarts itself with its options only (no script name).
#          tierlist.main and App.SCRIPT_DIR use them. _selftest_appdir.py (with a stand-in built program in
#          its own process; a real build is T-3).
# [x] T-2  Bundle data: tell the builder to include wordfreq's data files (tens of MB); WordNet
#          stays an optional download as it is now.
#          Built: tools/bundle.py (now src/bundle.py, for T-6): datas() [(file, folder in the program)] for PyInstaller's --add-data, and
#          EXCLUDE (wordfreq's Chinese / Japanese / Korean tokenizers, test suites). wordfreq ships 60 MB in
#          40 languages; only the English lists go in (large_en, small_en: 1.6 MB), plus langcodes' language
#          registry (wordfreq looks "en" up in it) and nltk's VERSION file (read on import): 2.3 MB in all.
#          Code and compiled parts (msgpack, regex) PyInstaller follows by itself. _selftest_bundle.py puts a
#          folder together the way a build would (code without data, then only that list) and runs wordfreq
#          and nltk from it with nothing else on the path; it found the packages needed by trying: wordfreq,
#          msgpack, langcodes, regex, ftfy, wcwidth, locate, nltk, defusedxml. To check in T-3: PyInstaller's
#          own nltk hook may pull in the build machine's ~/nltk_data (WordNet, ~30 MB); keep it out.
# [x] T-3  build.py: detects the OS, installs PyInstaller if missing, builds .exe / .app / binary.
#          Depends on ST-1 and ST-2 (a windowed program has no console for messages).
#          Built: tools/build.py (python tools/build.py [--check] [--dist]): installs PyInstaller if missing (pip,
#          then --break-system-packages for a Python that refuses plain installs), builds from tierlist.py with
#          src/ on the path, tools/bundle.py's data and exclusions, --windowed; one file on Linux / Windows,
#          an app bundle on macOS (one-file .app bundles are discouraged there). tools/hooks/hook-nltk.py
#          replaces PyInstaller's nltk hook, which packs the build machine's ~/nltk_data (checked: a planted
#          folder went in with PyInstaller's hook and stayed out with ours). --check starts the new program from
#          a folder of its own with a short word list and no internet and checks it stays open and keeps its
#          save beside itself. Linux build here: 22 MB, about 25 s; the window opens (first-start steps). Windows
#          and macOS builds are untried (need those machines). _selftest_build.py (a real build when PyInstaller
#          is installed).
# [-] T-4  Launchers instead (run.bat / run.command): dropped by the user (the program and the first-start
#          package offer cover it).
# [x] T-6  "Make a program" button (asked for). File > Make a standalone program... (shown when running
#           from source): asks first, installs PyInstaller if missing (the ST-4 way), builds a one-file
#           program for this OS behind the progress window (T-3 is the engine), bundles the complete
#           source inside it (see T-7), then starts the new program and closes this window. Both use the
#           same save (T-1), so nothing is lost. Needs T-1 and T-2 first. Only builds for the OS it runs
#           on (PyInstaller cannot cross-compile; T-8 covers the other OS).
#           Always builds from the source as it is now, so every change since the last build (files
#           edited, added or deleted) is in the new program. Each build records a manifest (file list
#           + hashes) inside the program; if nothing changed since the last build, it says so and just
#           starts the existing program instead of rebuilding.
#           Built: File > Source & Updates... (from source only; src/sources.py) says what it does, where the program
#           goes (next to tierlist.py: program_path), and when the program there was built from exactly this
#           source ("Nothing has changed ...": Start it / Build again). "Make the program" runs
#           standalone.make_program behind the progress window ("Step i of n": Installing PyInstaller, Building,
#           Putting it in place): PyInstaller is installed with pip if missing (asked first, in that page: the ST-4
#           dialog is for the program's own requirements), the source (standalone.source_files: the same list the
#           zip ships) and its manifest (sha256 per file) are copied inside the program under source/ for T-7, the
#           program replaces any older one, and the manifest is left beside it (.word-tierlist-build.json). Then
#           the program starts on its own and this window closes; a failed build shows PyInstaller's last lines and
#           changes nothing. tools/build.py and check_release.py now use src/standalone.py (which also took over
#           tools/bundle.py, now src/bundle.py), so the zip and the program carry the same files. Checked here: a
#           real build (23 MB), its source and manifest inside it (PyInstaller's archive reader), started with the
#           same save. The "Update to the newest version first" tick came with T-8.
#           _selftest_sources.py, _selftest_build.py.
# [x] T-7  "Back to source" button (asked for), the reverse of T-6. File > Unpack the source code...
#           (shown in the built program): writes the exact source files that were bundled (no real
#           decompiling is needed or attempted) into a folder you pick: the program files at the top,
#           and the Claude files (CLAUDE.md, CHECKLIST.md) plus the tests (_selftest_*.py, run_tests.sh,
#           check_release.py) in a separate folder inside it. run_tests.sh and check_release.py learn
#           to find the program files one level up. Then it opens the folder and offers to start
#           tierlist.py from it.
#           Unpacking into a folder that already has the source syncs it with the program instead of
#           copying blindly: changed files are updated, new ones added, and files the program no longer
#           has are removed. Only files listed in the program's manifest (T-6) are ever touched, so a
#           save (.db), tierlist.log, a .venv or anything else of yours is never removed. A summary
#           ("3 updated, 1 added, 1 removed") is shown first, with Cancel; a file you edited in the
#           folder since the last unpack is backed up (name.py.bak) rather than overwritten silently.
#           "Source & Updates" (asked for: unpacking doubles as updating). T-6 and T-7 are one File menu
#           item and one dialog, File > Source & Updates..., whose action fits the form you are running:
#           in the built program "Unpack the source code", from source "Make a standalone program".
#           Either way the dialog has a tick box, ticked to start with: [x] Update to the newest version
#           first. Ticked, it fetches the newest release from GitHub (T-8 publishes them) and unpacks or
#           builds from that, so unpacking is also how you update; unticked, it uses exactly the version
#           you have. Offline or no newer version: it says so in a line and carries on with yours. The
#           update keeps your save untouched and, like any unpack, only changes files the program owns.
#           Built (the update tick came with T-8): File > Source & Updates... in the built
#           program shows "Unpack the source code" (src/sources.py): the folder (beside the program, "Word Tier List
#           source", or Change folder...: the themed folder browser on Linux) and what it will do there, before it
#           does it. standalone.plan_unpack / unpack: the source the program carries (bundled_source: source/ in
#           PyInstaller's folder) goes in with the repository's own layout (R-1 replaced the planned "tests in a
#           separate folder", so run_tests.sh and check_release.py need no change). Into a folder unpacked before
#           (its record: .word-tierlist-source.json) it syncs: updated / added / removed, only files in the
#           program's manifest or in that record; a file edited since the last unpack, or differing in a folder never
#           unpacked into (a clone), is kept as name.bak first; a save, its log or a .venv are never looked at. Then
#           the folder opens (file manager) and it offers to start tierlist.py from there with this computer's
#           Python (the same save: the pointer file); without a Python it says to install one. _selftest_sources.py;
#           _selftest_build.py takes the source back out of a real build, checks every byte against the manifest,
#           unpacks it and runs the unpacked copy's core self-test.
# [x] T-8  One command for packaged builds on Linux AND Windows (asked for). `python build.py` builds
#           for the OS it runs on (T-3). `python build.py --all` (or the "Build programs" workflow
#           button on GitHub) runs a GitHub Actions workflow (.github/workflows/build.yml) that builds
#           on a Linux and a Windows machine at the same time from the pushed source and attaches
#           word-tierlist-linux and word-tierlist-windows.exe as downloads; --all waits and fetches them
#           into dist/. Needs the code pushed to GitHub and a GitHub login (gh) for --all; without
#           them it explains and builds for this OS only. Building a Windows .exe on Linux through
#           Wine was considered and rejected: fragile, and the result would still need testing on Windows.
#           Built: .github/workflows/build.yml ("Build programs"): on the Actions tab's Run workflow button (or --all)
#           it builds on ubuntu-22.04 (an older glibc, so newer Linux runs it too) and windows-latest, starts each
#           program once to check it runs (tools/build.py --check; Linux under xvfb) and keeps them as the run's
#           downloads, named word-tierlist-linux and word-tierlist-windows.exe (standalone.RELEASE_ASSETS). A pushed
#           tag v<VERSION> does the same, checks the tag matches constants.VERSION (new: 1.0.0) and publishes a
#           GitHub Release with both (gh release create): what the README's download links point to (R-1's last
#           item). tools/build.py --all (build_all): gh installed and logged in, the commit pushed, else it says
#           which and builds for this computer only; then gh workflow run, finds the run by its commit, gh run
#           watch, gh run download into dist/ (Linux one made runnable). GitHub starts a workflow by button or gh
#           only once the file is on the default branch (main). The update tick (T-6 / T-7's last piece): File >
#           Source & Updates asks GitHub's API for the newest release on a worker thread (standalone.latest_release;
#           offline / none yet: None) and says in a line what it found. Ticked and newer: from source "Make the
#           program" downloads that version's source (the repository's zip at its tag: fetch_source, with a
#           manifest) and builds from it, next to tierlist.py, your files untouched; in the program "Unpack"
#           downloads it, shows what unpacking it changes, and the next Unpack does it. Not tried for real here:
#           the workflow on GitHub (no gh login in this container) and a real release (none published yet).
#           _selftest_updates.py, _selftest_sources.py.
# [x] T-9  Introduce the other form on first start (asked for). The first time the program starts as a
#           script (tierlist.py) it asks once: "Make this a standalone program? It saves, builds, and
#           reopens as the program" (T-6); the first time the built program starts it asks the reverse:
#           "Unpack the source code next to it?" (T-7). Either way the save is committed first, the
#           answer is remembered (meta), and both stay in the File menu afterwards. Never asked during
#           a first-run download or while another question is open; --no-install also silences it.
#           Built: App._offer_other_form, started from App._startup after the start's own questions (merge,
#           How words are dealt, anchors); it waits while one of our dialogs is open (widgets.dialog_open), a long
#           job runs (App.busy) or Wiktionary's meanings are downloading (App.rude_read). Asked once per form (meta
#           offered_program / offered_source, set before asking, so "Not now" is remembered too); every save write
#           commits already. Yes does Source & Updates' own action at once (SourceDialog(go=True): from source
#           make the program and reopen as it; in the program unpack into "Word Tier List source" beside it, the page
#           showing only if that fails), from the version you have. Not asked when a program already sits next to
#           tierlist.py, or when the program carries no source. App(offer_form=...) is off unless main() turns it on
#           (not with --no-install), so tests never see it. _selftest_sources.py.
# [x] T-10 The built program's first start unpacks its source by itself (asked for: into a folder named for it, "unless
#           the user has already made something along those lines"): App._unpack_beside writes it into "Word Tier
#           List source" beside the program and says so in a message, instead of T-9's question; not when a copy is
#           there already (standalone.existing_source: tierlist.py beside the program, as T-6 builds it, or a folder
#           beside it holding tierlist.py or an unpack record, whatever its name). Once per save, as T-9. And
#           starting the other form closes this one (asked for): "Start it" after unpacking starts tierlist.py on its
#           own (standalone.start_source, detached as standalone.start) and closes the program, as "Start it" after
#           making the program already did; never two on one save.
# [x] T-11 The chain program -> unpack -> start the source -> make the program again (reported: "Tk data/library
#           directory ('/tmp/_MEI.../_tk_data') could not be collected!"). A built program points Tcl / Tk, and its
#           library path, into its own temporary folder; the tierlist.py it started inherited that, and so did the
#           PyInstaller run under it, after the program had closed and its folder was gone. standalone.clean_env drops
#           those (and PyInstaller's _PYI_ variables; the computer's own library path comes back) for everything one
#           form starts: the other form, Python, PyInstaller and pip, the file manager; tierlist.py also cleans its
#           own at start, for a source an older program started. Reproduced here (PyInstaller fails with exactly that
#           message under the dead paths) and fixed. The same build log showed GTK (gi) and Qt (PySide6) pulled in from
#           the computer, the likely 99 MB: every window toolkit but Tk is excluded now (bundle.UNUSED).
# [x] T-12 "Clean up behind?" (asked for: making the program from an unpacked source with no program beside it).
#           Asked before the build (standalone.cleanup_place: the source has an unpack record and no program sits
#           beside its folder). Yes: the program goes beside the source folder (T-15: now in it, unless a program it
#           was unpacked from sits beside it); this window closes, the save moves
#           next to the program if it was inside the folder (standalone.move_save, never over another file; its
#           -wal / -shm, .bak backups and the log with it) and is remembered; the save notes the source was given
#           out (offered_source), so the program does not unpack it again; then the program starts with
#           --remove-source and removes the folder as it starts (standalone.remove_source: on a thread, trying
#           again while the old window lets go of it, as Windows needs). Only the program's own files go (those the
#           unpack record lists, __pycache__, .venv, the log): a save or a file of yours stays, and so does the
#           folder then. No: the program goes next to tierlist.py, as before. Checked for real: tierlist.py
#           --remove-source on an unpacked copy removed its 117 files and kept one added by hand.
# [x] R-1  Repository layout on GitHub (asked for; see the notes, two points were pushed back on):
#           - Downloads front and centre: the README opens with "Download for Windows / Linux" links to
#             the newest GitHub Release, whose assets are the T-8 builds. Pushed back: binaries go in
#             Releases, not in a committed folder: a 30-60 MB binary per build would bloat every clone
#             forever, and Releases are what GitHub shows on the repo's front page anyway.
#           - src/ the program (tierlist.py and its modules, requirements.txt); tests/ the self-tests and
#             run_tests.sh; tools/ check_release.py and build.py; docs/ screenshots (and the roadmap if
#             it ever moves out of this file); .github/workflows/ the T-8 build.
#           - Claude assets in .claude/ (CLAUDE.md, CHECKLIST.md). Pushed back: CLAUDE.md must stay where
#             Claude Code loads it automatically, the repo root or .claude/, so .claude/ is the folder,
#             not a custom "claude/" one.
#           - Decided: tierlist.py (the thing you run) and the save files / tierlist.txt export stay at the
#             TOP of the folder, outside every sub-folder, both in the repo / downloaded source and in a
#             folder the program unpacks (T-7). Only the modules move into src/; tierlist.py adds src/ to
#             the import path. So "next to the script" stays where it was and no save appears to be lost.
#           - Approved (both pushbacks accepted); built ahead of T-6..T-9 so later steps use the layout.
#           Built: src/, tests/ (each test starts with `import _paths`), tools/, .claude/; tierlist.py adds
#           src/ to the import path; check_release.py knows the folders (flags a module left at the top,
#           ships the tree with its folders, ignores your save / log / export next to tierlist.py).
#           T-8 added the README's "Download for Windows / Linux" links to the newest Release.
# [x] T-5  A short note on every release's page (.github/release-notes.md, the user's choice: not a long note):
#          the programs are unsigned, so Windows' SmartScreen may need "More info > Run anyway" and Linux needs
#          the download allowed to run (chmod +x). Nothing for Tk on Linux: from source, the first start offers to
#          install it (deps.py), and the program carries its own.
#
# --- Looks (asked for after W-1, before the icon) ---------------------------------------------------------------
# [x] UI-61 Tier colours: Settings > Tier colours... (src/tiercolours.py): each tier's pill as it will look, a strip of
#           pastel swatches (theme.SWATCHES, every one light enough for the dark ink) and its #RRGGBB to type any
#           other; Reset to defaults; Apply saves them in the save (meta tier_colors) and reopens the window in them.
# [x] UI-62 Dark mode (asked for; not the default): View > Dark mode, a soft plum night (theme.DARK, the same roles as
#           the light look) with the same pastel tiers; Browse's rows are a deeper wash under light text
#           (TIER_ROW_TEXT). Kept in the save (meta dark_mode). How both show: theme.apply() changes the palette in
#           place before a window is built (app.apply_look, from the save, before even the start-up window), and a
#           change reopens the main window with the save still open (App.reopen, app.reopen_while_asked; UI-66: in
#           place, Browse too). Nothing copies a colour at import any more (button defaults, the chart's mark lilac);
#           a button picks its ink from its fill (theme.ink_on: dark ink on a pastel, so tier pills, duel cards and
#           Browse's Move to read in the dark too). Screenshots of every window in both looks. _selftest_looks.py.
#
# --- The very end (asked for: after everything else, W-1 and packaging included) -------------------------
# [x] UI-63 The word card's faint label (asked for: "table" had none) names every word's parts of speech, then for a
#           word smeared whole its kind of rude word: "noun · verb", "adverb", "noun · sexual" (constants.card_label,
#           from words.kinds; "other" is too vague to show, so a word that is only "other" or not known yet has no
#           label and keeps its full size). The label's row and the 85% word are F-15's.
# [x] UI-64 Asked for: turning on Censor obscene words says it may not be fully accurate. The first time in a save
#           (meta censor_noted) a small dialog: "Censoring is not perfect" (rules, not a person, pick the words out;
#           they can miss a rude word or smear an ordinary one; censoring never changes what is placed), over How
#           words are dealt when ticked there; every later time from View a toast ("Censoring on · it may miss...").
#           How words are dealt also says it in a muted line under the tick box, always (constants.CENSOR_CAVEAT*;
#           App.censor_note never waits).
# [x] T-13 Asked for: update just the source, without making the program. From source, File > Source & Updates
#           shows "Update the source only" once GitHub has a newer version: it downloads it, says what it changes
#           (the T-7 sync: only the program's own files; an edited one kept as .bak first; the save untouched; a git
#           checkout is told git pull is the usual way), brings this folder up to date, then starts tierlist.py again
#           from it with the same save (--db) and closes. The unpack record now says whether a folder came from the
#           program (standalone.came_from_program; older records: yes), so a folder only updated this way is never
#           offered to be cleaned up behind (T-12) nor removed. (The built program already updated its unpacked
#           source without building: T-8's tick on its Unpack page.)
# [x] UI-65 Asked for: "compound word" goes up into the card's faint label (it was on the frequency line): "noun ·
#           compound word · sexual" (constants.card_label(compound=)).
# [x] UI-66 Asked for: switching to dark mode (or new tier colours) closed the window and opened it again: jarring
#           (measured under openbox: about 0.3 s with no window at all, then back in another spot). Now the new window is
#           built while the old one is still on screen (App.reopen ends the event loop without closing it), takes its
#           place, size and maximized state, the word looked up on its card and its Browse window (App.take_over),
#           shows, and only then does the old one close (_drop_old): recorded at 30 frames a second, no frame without
#           a window, light straight to dark.
# [x] ST-8 Asked for (git missing was the example): what the program needs from outside Python's packages is offered,
#           not only told. Git turned out not to be one (Update the source only downloads a zip). Pip (Python's own
#           ensurepip first, then the system's package), Python's venv module (Debian keeps it apart; for the
#           private environment) and Python itself (to run a source the built program unpacked) are offered like
#           tkinter: the system's package manager (apt-get, dnf, pacman, zypper; Homebrew; winget for Python),
#           from the window through pkexec, the desktop's own password prompt (deps.SYSTEM_PACKAGES,
#           system_install_command, run_system_install; startup.offer_system_install).
# [x] UI-67 Asked for: a small "opens elsewhere" icon at the top right of a definition (the drawer, each duel column,
#           Browse's pane) opens the word's Wiktionary page (its etymology and the rest), only while Wiktionary can
#           be reached (definitions.Online: a worker thread asks now and every minute; the window checks every 3 s
#           and shows or hides it; never in the tests).
# [x] F-19 Asked for: the log keeps everything that goes wrong. Besides Python's errors (as before): each start is
#           marked with the version and the system, a session that never closed is said on the next start, a hard
#           crash (Python or Tk failing) writes every thread's stack there (faulthandler), and a window that has not
#           answered for 10 s is written down with where each thread was, then when it answers again
#           (problems.start_session / end_session, errors.watch_freezes).
# [x] IC-2 Reported: the program built on Fedora 42 showed no icon in the file manager. A Linux program cannot carry one
#           inside (a Windows .exe does); its file gets GNOME Files' custom icon (gio set ... metadata::custom-icon,
#           to a copy of the icon in ~/.local/share/icons) when it is built and whenever it starts
#           (standalone.give_icon). Not seen here (no desktop's metadata service in this container); File > Add to
#           applications menu gives it a launcher with the icon on any desktop.
# [x] ST-9 Reported: on Windows the console window stayed open behind the program (on Linux it goes, ST-5). Letting go
#           of the console (FreeConsole) does not close it while the py launcher that opened it (a double-clicked .py)
#           waits on. Asked: rename tierlist.py to .pyw on Windows? No: the update sync, the manifest, launchers, git
#           and the docs all expect tierlist.py (and an update would bring it back). Instead, as on Linux, it starts
#           itself again with pythonw.exe (no console window), detached, and this copy ends: the console closes, a
#           terminal gets its prompt back, and a failure right at the start still shows there (deps.should_detach,
#           detach_terminal, windowless_python). With no pythonw.exe the old FreeConsole stays. Confirmed by the user
#           on real Windows.
# [x] IC-3 Reported: on Fedora the icon showed in Files but not in the taskbar. GNOME no longer takes a window's own
#           icon there: it pairs the window with a launcher by its class. Every window is now named (tk.Tk(className=
#           "word-tierlist"): X's WM_CLASS "word-tierlist", "Word-tierlist"), the launcher names it (StartupWMClass,
#           and its file is word-tierlist.desktop), and on Linux every start writes the launcher if there is none,
#           out of the applications menu (NoDisplay) until File > Add to applications menu, or brings it up to date
#           (deps.ensure_launcher). Not seen here (no GNOME Shell): confirm on Fedora.
# [x] T-14 Asked for: making the program did not ask to clean up behind (T-12 asked only for a source unpacked from the
#           program). Now it asks every time it is made from source, whatever the source: Keep the source (the
#           default), Zip it (the source packed into <folder>.zip beside it first, never over a file) or Remove it.
#           Either of the last two puts the program beside the folder (T-15: in it), moves the save, and writes down the files
#           that may go (REMOVE_RECORD: the source's own), so a download or a clone keeps anything else (.git, files
#           of yours); the new program removes them as it starts (standalone.remove_source).
# [x] F-20 Reported (back again, Windows and Linux): the definitions pane flickered as it opened. Measured in the app every
#           4 ms under a window manager: at the end of the slide the pane's contents vanished for a frame. While it
#           slides they are placed (clipped); at the end they go back to being packed, and Tk left that to the next
#           idle moment, so one frame drew the pane empty. Unseen before; the Wiktionary link inside the pane (UI-67)
#           made that frame long enough to see. The change now finishes at once (DefinitionDrawer._natural);
#           _selftest_drawer opens it under openbox and checks the contents never vanish once shown.
# [x] F-21 Reported: the program froze on Linux and had to be closed by force; the log's watchdog (F-19) caught the window
#           thread inside a canvas delete, from the word card's magnifier being hovered. Its Enter / Leave redrew it
#           by deleting it and making it anew; the new item under the pointer was entered again, and Tk looped on
#           that for good (reproduced here under openbox: the pointer on the icon's corner froze it at once). The
#           magnifier is now made once and only moved and recoloured (WordCard._draw_find); _selftest_freeze rests
#           the pointer on its every edge and shows new words under it, under openbox, and fails rather than hangs.
# [x] UI-68 Asked for: Browse's sort arrow pointed up for S to F; it now points the way the values grow (down for S..F,
#           a..z and commonest first; up for the highest rating or most duels first; a second click turns it round),
#           and the Sort drop-down says "Tier" instead of "Default" (the order the Tier column sorts in).
# [x] UI-69 Reported (Fedora): the window opened with its contents bigger than allowed, and maximizing then made them
#           smaller. The two zooms (UI-57: one for the window maximized, one for any other size) were kept apart and
#           nothing kept them compatible: a usual zoom of 150% with 100% kept for maximized opened at 150%, then
#           maximizing showed 100% (reproduced under openbox). Now the usual window never shows more than the
#           maximized one: a usual zoom chosen above the maximized one raises that too, one chosen maximized below
#           the usual one lowers that too, a save left with the usual one above opens at the maximized one, and a
#           big window that is not maximized grows its contents (UI-25) only up to the maximized zoom
#           (App._keep_compatible, _max_zoom, _grow_for).
# [x] IC-1 An icon for the program: the window / taskbar icon (iconphoto) and the built programs' icon
#           (T-6 / T-8: .ico for Windows, .png for the Linux launcher), in the pastel look.
#           The user's design: the progress shelf's six spines filled S to F in the tier colours, the lilac shelf
#           mark over C, on the cream tile with rounded corners, the shelf filling most of it. tools/make_icon.py
#           draws it into src/icons (16..256 px, 1024 px, icon.ico; each size from the shapes, 32 px and under on
#           whole pixels). ui_style.set_icon (from apply_ttk_style) puts every size on each root, and so on every
#           window (on Windows also its own taskbar group); a build packs src/icons as "icons" and the Windows
#           program takes icon.ico as its own; the Linux launcher points at a copy in ~/.local/share/icons.
# [x] F-22 Reported (after F-20): the definitions pane still flickered, now and then, opening and closing (Windows and
#           Linux). Tracked frame by frame (asked for): the screen grabbed every ~25 ms under openbox and the tier
#           buttons' place in each frame read, beside the layout read in the app every 3 ms. Five causes, each fixed:
#           - opening in a window that had to grow: the window grew first and the page dropped (59 px here), then slid
#             back up as the pane opened. The room the window gains now goes to the folded pane in the very layout
#             of the window's new size (App._give_room from <Configure>; DefinitionDrawer.at_least);
#           - a hiccup in the event loop mid-slide (now and then, ~150 ms seen): the slide then leapt to its end.
#             An animation now moves on by Animator.STALL_MS at most per frame;
#           - closing: the pane was put back to its full size for one frame just before it left (F-20's refresh), the
#             page jumping up and back; it now leaves the layout first. Its gap went only after it had gone (a last
#             3 px jump): the gap is inside the pane now and slides shut with it;
#           - a window grown for the pane only by its minimum size shrank back the moment the pane closed (a jump
#             after the slide): the grown size is set as the window's size;
#           - at a zoom the open pane needs smaller text for: every text size from the full zoom down was tried and
#             drawn, the page swelling past the window and stepping back (~0.5 s); opening now tries from the size
#             shown. And the page shook by a pixel as the pane slid (two roundings): it is placed by its top.
#           _selftest_drawer opens and closes it in two windows under openbox (the page only ever moves with the
#           slide; it fails on the old code); _selftest_motion holds an animation up.
# [x] T-15 Asked for: "Zip it" put the program in the folder holding the source, outside it. A clean up now puts the
#           program where the source was, in its own folder (as Keep does), with the zip and the save; the program
#           removes only the source's files there and keeps itself, its build record, the save, the log and the zip
#           (standalone.cleanup_place, remove_source). A folder unpacked from a program sitting beside it still
#           replaces that program (T-12).
# [x] F-23 Reported (Fedora 42): opening the definitions pane, its text blinked down a little. F-22 gave the pane the
#           room the window grew by as its whole height; a window manager that grows the window only after the slide
#           has begun (GNOME's, not openbox's) then set the pane shorter-topped than it already was, its top edge and
#           text dropping. The room is now added on top of the height the pane has then (DefinitionDrawer.give, from
#           App._give_room, step by step if the window grows in steps). Not seen here (openbox resizes at once);
#           _selftest_widgets2 hands it the room mid-slide.
# [x] UI-70 Asked for: the typing line in a search blinks, as in most programs. The word card's search caret blinks
#           (530 ms), shows on every key, and stays shown after 10 s without one (as GTK does: nothing runs while
#           idle). Browse's search box (a ttk entry) blinked already.
# [x] UI-71 Asked for: the note that censoring is not fully accurate is not a window of its own. Ticked in How words
#           are dealt, the first time in a save, the line under the tick box says it in full; from View > Censor
#           obscene words, a longer message in the main window. After that a short message, as before.
# [x] F-24 Asked for: making the program and removing the source must really remove it. Tried for real: a program
#           built here from a copy of the source, started with --remove-source, removed it all but .gitignore (in every
#           download and clone, not counted as source), which alone kept the folder there when the program went
#           beside it. .gitignore and .gitattributes are source files now (standalone.REPO_FILES); on Windows the
#           removal waits up to 30 s for the old window to let go of its files (10 s before).
# [x] IC-4 Asked for: a slightly darker border round the icon (tools/make_icon.py, EDGE), so it stands out on light
#           and dark backgrounds alike.
# [x] W-2  Asked for: words in a smeared meaning can be clicked once it shows (W-1: underlined under the pointer;
#           smeared_label's on_word), and a smeared form's word too. When the word itself is smeared, its smeared
#           meanings un-smear with it, the pointer anywhere over the pane; otherwise each under the pointer.
# [x] F-25 Reported: "sqlite3.InterfaceError: bad parameter or other API misuse" twice at closing, from the first
#           start's offer of the other form (App._offer_other_form, T-9) reading a save that had been closed. Not
#           reproduced here (the yes and no paths, a window closed while a question was open, a new look); its
#           timer now stops once the window is shut (App.shut) or the save closed (Store.closed).
# [x] F-26 Reported: in the definitions pane the part of speech (noun, verb...) and the examples kept their size when
#           the zoom changed, until the pane was opened again: their italics were a copy of the body's size, made as
#           the pane was filled. refresh_widgets (run after every zoom, main window and Browse) sets them again.
# [x] F-27 Reported (Fedora 42 and Windows, maximized or not, now and then, words seen before too): the whole
#           definitions pane dipped and came back as it opened (F-23 again). Going back over the earlier fixes: the
#           slide (UI-35) kept the pane's contents packed; F-2 placed them while folded and packed them again at each
#           slide's end, and every flicker since came from that switch (F-20: a frame empty, F-22: a frame at full
#           height). The switch unmapped and remapped the contents at the end of every opening (counted: 20 times in
#           20 opens); on a compositing desktop a frame could show the pane without them. Now they are placed for
#           good, at their own height, and the pane's height is always set: by the slide, else from them
#           (DefinitionDrawer._follow). _selftest_drawer counts no unmap while it opens or is open (fails on the old
#           code). Also tried here: waiting, folded, for a slow window manager to grow the window first; under mutter
#           Tk always learned the new size at once, so it changed nothing and was left out. A window that must grow
#           for the pane may still show GNOME's compositor resizing it a frame late (seen once in seven).
# [x] F-28 Asked for: a longer definition made the open pane jump to its new height; it now eases there like opening
#           (the same strategy as F-22 / F-27, which the user confirmed worked): App._fit_defs holds the pane at its
#           height (DefinitionDrawer.hold), fits the window counting it at its new one, gives it what the window grew
#           by, then opens it the rest of the way. Recorded frame by frame under openbox and mutter: in a tall or
#           maximized window the pane's top rises smoothly over ~200 ms and the page above slides up with it; in a
#           window that must grow, the pane takes exactly what the window gains (its top and the page stay still;
#           the window's own resize stays one step: resizing it every frame flickered, UI-35).
# [x] F-29 Asked for: comparing to anchors must shrink the definitions pane smoothly so everything fits. Comparing
#           never re-fitted the window: its question could run under the pane. Starting or ending a comparison now
#           re-fits only when the page's contents (and a message's room) really do not fit, or, once it ends, when the
#           pane was shortened for it (App._refit_if_needed); any fit that changes an open pane's height eases it
#           there from where it was (App._fit_window -> DefinitionDrawer.ease_from), unless the text size changed too.
# [x] F-30 Asked for: the first zoom in past what fits grew the window and snapped back (later ones remembered).
#           Trying a size is the only sure way to know (the page grows 0.5 to 1.7 times as fast as its text, with
#           fonts in whole points: no estimate held), so it is tried while the window is still hidden as it opens
#           (App._precheck_zoom: the pane open and closed, ~0.8 s once per screen) and the limit kept in the save for
#           each screen and version (meta zoom_caps); a limit not known yet is tried once on screen, then kept. A
#           refused zoom only shakes its message "no", the first time too.
# [x] UI-72 Asked for: the window keeps room for a message under the page's contents, so one never covers the word
#           card, the buttons or the definitions pane (App._toast_room: in the page's breathing room, the contents
#           kept above it by _recenter). Zoom limits stay as before (the 1366 x 768 laptop still reaches 110%).
# [x] ST-10 Asked for: Add to applications menu on Windows too. File > Add to Start menu writes a shortcut in the
#           user's own Start menu (no administrator needed), through Windows' own PowerShell (WScript.Shell: no
#           package; the paths reach it through the environment, never quoted in the script). From source it starts
#           pythonw.exe with tierlist.py (no console window, ST-9) and shows the icon (src/icons/icon.ico); a built
#           program starts itself, with its own icon. deps.add_to_start_menu; a failure says why. Never run on real
#           Windows here (faked in _selftest_deps / _selftest_ui2).
# [x] F-31 Found in a review of the rounds above: tierlist.md is both tierlist.py's note (R-1) and the default name
#           of a Markdown export, which .gitignore leaves out: the note had never reached GitHub, and an export saved
#           beside tierlist.py would have overwritten it. The note is tracked now (only tierlist-export.md is left
#           out), and an export aimed at a code file's note goes to tierlist-export.md, saying so (saves.is_code_note).
# --- A less generated look (asked for: "make the UI style less AI generated"; mock-ups in two rounds, each beside
#     the real window; the user picked these, kept the buttons, card, labels and borders as they are, and wants
#     the borders and the card's shadowy edge in a pass of their own, with befores and afters to choose from) ---
# [x] UI-73 Typefaces: Young Serif for the words (the card, a duel, a definition's heading) and Atkinson
#           Hyperlegible for everything else, shipped in src/typefaces (SIL Open Font Licence, the licences beside
#           them) and loaded for this program only (fonts.load_typefaces: fontconfig, a private GDI font,
#           CoreText; never installed; the old installed fonts stand in if that fails). The text keeps to three
#           sizes, 20 / 12 / 10 pt, beside the card's word and a duel's two words. As shipped their lines were
#           tall and the window grew by a quarter (much of the layout is measured in lines): tools/make_typefaces.py
#           tightens them, and the window is within a few percent of its old size (a 1366 x 768 laptop still
#           shows 100%). Packed into a build as "typefaces".
# [ ] UI-74 A light film grain (0.1) over the window's background, as in the mock-ups.
# [x] UI-75 A GitHub link at the top right of the main window (the menu bar's row): "GitHub" and the "opens
#           elsewhere" icon, muted until hovered (LinkButton with words; App.open_page, constants.REPO_PAGE). The
#           GitHub mark itself was left out: the icons are one hand-drawn polygon style (smooth.ICONS).
# [x] UI-76 Stronger contrast: muted text about 7:1 (it was 5.0:1), and the key numbers on the tier pills in the
#           dark ink (they were a paler ink, 3.4:1 at worst: below WCAG's 4.5:1 for text); every button's key
#           follows its label's colour (RoundButton._paint). theme.contrast; _selftest_looks checks both looks.
#           The card's faint rude kind (UI-59) stays faint on purpose.
# [x] UI-77 Dark mode in the "Dusk" colours (warm night, cream text; the tiers in the film pastels) instead of the
#           plum night. The light look keeps its colours. theme.DARK; a save that never chose tier colours gets
#           the look's own (theme.default_tiers: DUSK_TIERS in the dark), and Tier colours' Reset puts back the
#           look's. Every text colour on its background is 7:1 or better, the dark ink on the tiers 5.3:1.
# [ ] UI-78 Borders and the card's shadowy edge: a pass of their own, mock-ups with befores and afters first.
#
# Decisions
#   Settled:  progress bar (UI-14): a bookshelf of spines by commonness (page .. library), "95% of text" after it;
#             modernize the top (menus, mode switch: UI-10) but keep the bottom bar's current look
#             (Undo, Browse / edit, Definition, key hints); the light look by default, with a dark mode
#             to choose (UI-62: asked for later, so "light theme only" was lifted; not the default); the
#             session count stays as a muted "+N today", with the pace only in a hover note.
#   In consideration (shelved, not planned; ask before building):
#             - Next-up peek (UI-21).
#             - Boundary check's swap strip (UI-31, archived by request): the six tiers as pills with the swaps
#               per join under them, the join being checked in bold. Last version: ui_chart.SwapStrip in commit
#               9b78889. The swap counts are still recorded, so it would show the full history if it came back.
#   Planned:  Packaging, now asked for: T-6 (make a program), T-7 (back to source, as a sync) and T-8
#             (one command for Linux + Windows builds), which need T-1, T-2 and T-3 first. T-4 dropped, T-5
#             the release's notes. After the UI steps.
#
# File layout: see the code map in the docstring above. New UI steps add files named for their
# job: more widgets in widgets.py (UI-5..12), ui_chart.py (UI-13).
# ==========================================================================================
import argparse
import json
import os
import sys

# The program's modules live in src/ (R-1); this file stays at the top of the folder, next to your save.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import deps  # noqa: E402  (after the path line above)
import standalone  # noqa: E402

# Re-exported (hence the noqa comments) so the self-tests and anyone doing `import tierlist` can
# still reach everything as tierlist.Store, tierlist.TIER_COLORS, and so on.
from constants import DEFAULT_ANCHORS, FOCUS_ROUNDS, MODES, TIERS, VERSION, WM_CLASS, plan_line  # noqa: F401
from definitions import Definitions
from saves import (_pointer_file, app_dir, choose_save, default_save_path, find_saves,  # noqa: F401
                   remember_save, restart_args, save_progress, write_export)
from sizing import set_dpi_awareness
from store import Store
from theme import PALETTE, TIER_COLORS, TIER_ROW, TIER_TEXT, tint  # noqa: F401
from wordsource import (build_word_list, build_wiktionary, compute_penalties,  # noqa: F401
                        prepare_queue, queue_steps, wiktionary_steps)

# The window code needs tkinter, which is optional (e.g. Debian needs `apt install python3-tk`).
# Without it everything above still works; main() explains what is missing.
try:
    import tkinter as tk
    from tkinter import filedialog  # noqa: F401
    from app import App, apply_look, reopen_while_asked
    from fonts import init_fonts
    from errors import install_handlers, run_guarded
    from problems import SetupError, end_session, ensure_streams, open_log, start_session
    from startup import detach_console, ensure_packages, run_with_progress
    from ui_style import apply_ttk_style
    from browser import Browser  # noqa: F401
except ImportError as exc:
    if (getattr(exc, "name", "") or "").split(".")[0] not in ("tkinter", "_tkinter"):
        raise  # a real bug, not a missing tkinter
    tk = App = Browser = None
    from problems import SetupError, end_session, ensure_streams, open_log, start_session   # (no tkinter)


def main():
    """Start the program: parse options, pick and open the save, build the word list on first run, open the window."""
    if not getattr(sys, "frozen", False):     # (started by a built program: its Tcl / Tk folders are not ours and
        clean = standalone.clean_env()        # are gone once it closes; T-10, reported)
        for key in set(os.environ) - set(clean):
            del os.environ[key]
        os.environ.update(clean)
    ap = argparse.ArgumentParser(description="Tier-list every word in the English dictionary.")
    ap.add_argument("--db", default=None,
                    help="save file to use. By default your earlier save is found automatically "
                         "(the one used last time, or the one with the most progress), so replacing or "
                         "moving this script never loses your tier list")
    ap.add_argument("--wordlist", help="optional text file, one word per line, in presentation order "
                                       "(only used when the save file is first created)")
    ap.add_argument("--source", choices=["wiktionary", "wordnet"], default="wiktionary",
                    help="word source: wiktionary = every English Wiktionary word (default, ~1M); "
                         "wordnet = ~77k base-form dictionary words")
    ap.add_argument("--wiktionary-file", help="use an already-downloaded kaikki.org English JSONL "
                                              "(.jsonl or .jsonl.gz) instead of downloading it")
    ap.add_argument("--include-phrases", action="store_true",
                    help="also include multi-word entries such as 'ice cream' (Wiktionary source)")
    ap.add_argument("--keep-download", action="store_true",
                    help="keep the 3 GB Wiktionary download after building the word list")
    ap.add_argument("--console", action="store_true",
                    help="keep the terminal (Linux, macOS) or console window (Windows) attached and print to "
                         "it, for troubleshooting. Normally the program carries on in its own window, the "
                         "terminal gets its prompt back and messages go to tierlist.log next to the save file")
    ap.add_argument("--no-install", action="store_true",
                    help="never offer to pip-install missing packages (they are listed in requirements.txt), "
                         "nor to make a program / unpack the source on the first start")
    ap.add_argument("--crash-test", action="store_true", help=argparse.SUPPRESS)   # ST-2: fakes a bug 3 s after start
    ap.add_argument("--remove-source", help=argparse.SUPPRESS)  # T-12: the unpacked source this was made from
    ap.add_argument("--seed", type=int,
                    help="seed for the random queue order (reshuffles the words you haven't placed yet)")
    args = ap.parse_args()
    if args.remove_source:                    # (cleaning up behind, T-12: in the background, while the old window
        import threading                      # closes; only the program's own files, never a save)
        threading.Thread(target=standalone.remove_source, args=(args.remove_source,), daemon=False).start()
    set_dpi_awareness()          # Windows: sharp at 125% / 150% display scaling (before any window opens)
    script_dir = app_dir()          # tierlist.py's folder, or a built program's own (T-1)
    # --- 1. packages, stage 1 (ST-4). A private environment made earlier is used straight away. In a
    #        terminal, before any window, only tkinter is asked about (the window needs it to open);
    #        every Python package is offered later, in the window, each as its own choice.
    restart_argv = restart_args(script=__file__)
    if not args.no_install and not getattr(sys, "frozen", False):
        deps.use_private_env(restart_argv, script_dir)
    if tk is None and deps.wants_terminal_setup(args.no_install):
        deps.terminal_setup(restart_argv)
    # tkinter is needed for the window (everything else works without it)
    if tk is None:
        sys.exit("tkinter is not installed. " + deps.tk_advice())
    # --- 1b. Linux / macOS (ST-5), Windows (ST-9): nothing more to ask in the terminal, so the program carries on
    #        on its own (a session of its own; on Windows pythonw.exe) and the terminal gets its prompt back, or the
    #        console window a double-click opened closes (closing it no longer closes the program)
    if deps.should_detach(args.console):
        sys.exit(deps.detach_terminal(restart_argv))

    def start():
        # --- 2. find the save file: --db, else the earlier save (see saves.choose_save)
        best, others = None, []
        if args.db:
            db_path = os.path.abspath(args.db)
        else:
            db_path, best, others = choose_save(script_dir)
        store = Store(db_path)
        if not args.db:
            remember_save(store.path)
        note = None
        if best:
            print(f"Resuming your save file: {db_path} ({best['placed']:,} placed, {best['skipped']:,} skipped)")
            if os.path.realpath(db_path) != os.path.realpath(default_save_path(script_dir)):
                note = f"Resumed your earlier tier list from {db_path} ({best['placed']:,} words placed)"
        for o in others:
            print(f"Also found: {o['path']} ({o['placed']:,} placed). You'll be asked whether to merge it.")
        # --- 3. Windows: close the console window behind the app (messages go to tierlist.log from
        #        here on, and errors become dialogs; see startup.detach_console / run_guarded).
        log_path = os.path.join(os.path.dirname(db_path), "tierlist.log")
        if os.environ.get(deps.DETACHED_ENV):     # (ST-5: the copy that gave the terminal back)
            sys.stdout = sys.stderr = open_log(log_path)
        elif not args.console:
            detach_console(log_path)
        ensure_streams(log_path)          # started without a console at all (pythonw): print() must not crash
        start_session(log_path, VERSION)  # (in the log: when it started, on what; a hard crash writes its stacks there)
        if getattr(sys, "frozen", False):  # (Linux: its icon on its file in the file manager, reported missing)
            import threading
            threading.Thread(target=standalone.give_icon, args=(sys.executable,), daemon=True).start()
        deps.ensure_launcher(sys.executable, None if getattr(sys, "frozen", False) else os.path.abspath(__file__))
        #                                  (Linux: the taskbar's icon comes from a launcher naming the window's class)
        # `current` is the source the list was built from; an older WordNet save is upgraded to
        # Wiktionary in place, keeping all progress.
        existing = store.count_words()
        current = store.get_meta("source") or ("wordnet" if existing else None)
        builds_wiktionary = (not args.wordlist and current != "custom"
                             and args.source == "wiktionary" and current != "wiktionary")

        def set_up(log):
            # the main steps, up front, for the progress window's "Step 2 of 5" (the same branches as below)
            steps, adds = [], False
            if args.wordlist:
                adds = existing == 0
            elif current == "custom":
                pass
            elif builds_wiktionary:
                steps, adds = wiktionary_steps(store, args.wiktionary_file), True
            elif args.source == "wordnet" and existing == 0:
                steps, adds = ["First run: building the word list"], True
            steps += queue_steps(store, adds_words=adds, by_wiktionary=builds_wiktionary)
            if args.seed is not None and args.seed != store.queue_settings()["seed"]:
                steps.append("Reshuffling the queue")
            log(plan_line(steps))
            if args.wordlist:
                if existing == 0:
                    store.insert_words(build_word_list(args.wordlist))
                    store.set_meta("source", "custom")
            elif current == "custom":
                pass  # a custom list is never replaced automatically
            elif builds_wiktionary:
                if existing:
                    log(f"Upgrading your {existing:,}-word list to the full Wiktionary list. "
                        "Your progress is kept.")
                try:
                    build_wiktionary(store, args.wiktionary_file, args.include_phrases,
                                     args.keep_download, log=log)
                except (RuntimeError, OSError) as exc:
                    raise SetupError(f"Could not build the Wiktionary word list: {exc}\n\n"
                                     "Try again (downloads resume), download the file yourself and pass "
                                     "--wiktionary-file, or use --source wordnet.") from exc
            elif args.source == "wordnet" and existing == 0:
                log("First run: building the word list (about 10-30 seconds)...")
                store.insert_words(build_word_list())
                store.set_meta("source", "wordnet")
            # queue order: flag compounds and shuffle (cheap when already done), honour --seed
            prepare_queue(store, log=log)
            if args.seed is not None and args.seed != store.queue_settings()["seed"]:
                log(f"Reshuffling the queue with seed {args.seed}...")
                store.reshuffle(seed=args.seed)

        def new_root():
            r = tk.Tk(className=WM_CLASS)   # (named, so a Linux taskbar finds the program's icon: ensure_launcher)
            r.withdraw()                     # stays hidden until set-up is done / the window is built
            init_fonts(r)
            apply_ttk_style(r)
            install_handlers(r, log_path, db_path)      # unexpected errors: log + friendly dialog
            return r

        def launch():
            # --- 4. make sure the save has a word list and a queue order. This is the slow part on a
            #        first run, so it runs on a worker thread behind a progress window (startup.py); the
            #        window only appears if it takes more than a moment. Every message goes through `log`.
            apply_look(store)                # dark mode and the tier colours, before any window (UI-61, UI-62)
            root = new_root()
            try:
                # packages, stage 2 (ST-4): anything missing is offered in one dialog, one tick box per
                # package (required and optional each their own choice); only asks when something is missing
                if not args.no_install:
                    wordnet_build = args.source == "wordnet" and existing == 0 and not args.wordlist
                    declined = set(json.loads(store.get_meta("declined_packages", "[]")))

                    def restart(python):              # moved into a private environment: start again in it
                        store.close()
                        root.withdraw()               # (destroyed by the except below if this returns)
                        deps.restart(python, restart_argv)
                    ensure_packages(
                        root, list(deps.REQUIRED) + (["nltk"] if wordnet_build else []), optional=deps.OPTIONAL,
                        declined=declined, restart=restart, home=script_dir,
                        on_decline=lambda names: store.set_meta("declined_packages", json.dumps(sorted(declined | set(names)))))
                run_with_progress(root, set_up,
                                  initial_stage="Initializing download..." if builds_wiktionary else "Initializing...")
            except BaseException:
                root.destroy()
                raise
            print(f"{store.count_words():,} words ready.")
            # --- 5. show the main window, built, sized and filled while still hidden (F-1); App runs until closed.
            #        A new look (App.reopen) closes it with the save still open, and it is built again at once.
            defs = Definitions(store)
            app = App(root, store, defs, note=note, other_saves=others,
                      ask_dealing=store.get_meta("dealt_asked") != "1",   # (ST-6: once a save)
                      offer_form=not args.no_install)                     # (T-9: the other form, once)
            app.open_window()
            if args.crash_test:           # lets you see the friendly error dialog; the program keeps running
                root.after(3000, lambda: 1 / 0)
            root.mainloop()
            reopen_while_asked(app, store, defs, new_root)

        # Always guarded: with or without a console, a failure ends in a dialog and a log entry.
        try:
            run_guarded(launch, log_path, db_path)
        finally:
            end_session(log_path)         # (not reached by a hard crash or a kill: the next start says so)


    # Everything from opening the save onward is guarded, so even a save that cannot be opened
    # ends in a dialog (logged next to this script until the save's folder is known).
    run_guarded(start, os.path.join(script_dir, "tierlist.log"), args.db)

if __name__ == "__main__":
    main()
