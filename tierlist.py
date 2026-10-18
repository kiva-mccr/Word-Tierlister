#!/usr/bin/env python3
"""
Word Tier List
==============
Tier-list every word in the English dictionary (S / A / B / C / D / F).

Setup (once):
    pip install wordfreq nltk
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
  Same seed = same order. Change it under Settings > Queue randomness & seed (or
  --seed N). (--source wordnet gives a smaller ~77k list instead.)
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
  Ctrl+mouse-wheel zoom; rows load as you scroll, so there is no row limit.
* Tab / Shift+Tab move to the next / previous tab.
* PLACE mode: type 1-6 to drop a word straight into a tier, or press Space to
  place it by comparing against one anchor word per tier (about 3 questions).
  "Don't know / later" (U) sends a word to the back of the queue; skipped
  words come back after every fresh word has been handled.
* REFINE mode: head-to-head duels between words in the same tier (Elo ratings,
  fewest-duels-first, nearest-rating opponents) to order words within a tier.
* BOUNDARY mode: duels between the weakest word of one tier and the strongest of
  the next; if the lower-tier word wins, the two swap tiers.
* CONFLICTS: if a new answer contradicts earlier ones (A>B, B>C, then C>A) the
  pair is flagged; re-judge them in "Resolve conflicts".
* Under the status line, a progress bar in four equal parts by how common words
  are (everyday, common, uncommon, rare), each filling by the share of its own
  words placed, and a tag with how much of everyday English the placed words cover.
* Tabs have their own little view at the top right: the tier chart (Place), how
  settled each tier's order is (Refine), and the number of conflicts (Conflicts).
* A mode's tab only shows once it has work (Refine: a tier with two words;
  Boundary: two neighbouring tiers with words; Resolve conflicts: a conflict).
* Every action is committed to SQLite immediately: close the window or lose
  power and nothing is lost. Undo (Ctrl+Z) survives restarts too.
* Press D any time to show the dictionary definition next to the word(s).

Code map (run tierlist.py; it stays at the top of the folder, next to your save. The modules below
live in src/, the self-tests in tests/, check_release.py in tools/, the Claude notes in .claude/)
----------------------------------------------------------------------------------------------
    tierlist.py     entry point: command-line options, start-up sequence, main(). Re-exports
                    the pieces below so `import tierlist` keeps working for the self-tests.
    constants.py    tier names, modes, ranking defaults.        (no dependencies)
    store.py        Store: the SQLite save file. Tiers, Elo duels, undo history, queue order,
                    conflicts, merging. Every change is committed immediately.
    wordsource.py   building the word list: WordNet, Wiktionary download/parse, compound
                    detection, queue preparation.
    saves.py        finding your earlier save, remembering it, exporting the tier list.
    definitions.py  Definitions: WordNet offline, dictionaryapi.dev online, cached.
    theme.py        colour palette (UI-1).            fonts.py     typography (UI-2).
    ui_style.py     ttk / tk styling (UI-3).          widgets.py   RoundButton and other small widgets.
    ui_motion.py    easing, colour blend, Animator (UI-4).
    startup.py      first-run progress window; runs set-up on a worker thread (ST-1).
    problems.py     plain-language error text, SetupError, log helpers (ST-2; no tkinter).
    deps.py         required packages: detect and install them; the terminal stage (ST-3, ST-4; no tkinter).
    errors.py       friendly error / message / question dialogs, error handlers, run_guarded (ST-2).
    browser.py      Browser: the Browse / edit window.
    app.py          App: the main window and all modes.

Layers: constants -> store -> wordsource / saves / definitions -> (UI) theme, fonts,
sizing, ui_style, ui_motion, widgets, errors, startup -> ui_chart, browser -> app -> tierlist. Nothing lower imports anything higher, and
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
# Added later, in this order after the UI steps: ST-5 (Linux terminal), ST-6 (how words are dealt), then
# T-1..T-3 -> T-6, T-7, T-8.
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
# [ ] ST-5  Linux: the terminal only when it is really needed (asked for after ST-4). Today a Linux
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
# [ ] ST-6  How words are dealt (asked for): an extension of the start-up and of the Queue randomness window
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
# [ ] UI-37 Compare to anchors: Space toggles it (asked for): Space starts comparing, Space again leaves it
#           (what Escape does today), so Backspace is no longer how you get out. Backspace / Back keep
#           stepping back one answer while comparing (confirmed). The Compare button's key hint and the bottom-right
#           hint follow.
# [ ] UI-38 Browse window opening and closing (asked for): a quick opening animation (about 150 ms: it eases
#           in from slightly smaller; preferred over a fade), and a click on the main window's empty
#           background closes it (not a click on a pill, card or button, so a quick click never loses your
#           place). Its unsaved state (search, filter, scroll) is
#           remembered for the next open, so closing by accident costs nothing.
# [ ] UI-39 Browse: the Delete key (and Backspace on macOS) unplaces the selected word(s) (asked for), same as
#           the Unplace button, with undo.
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
# [ ] UI-41 Queue randomness dialog: two small diagrams (asked for), the exponential and the gaussian drop-off
#           drawn as soft pastel curves (chance of coming up early against frequency rank), the chosen one
#           highlighted and redrawn live as spread changes. The intro text shrinks to one line.
# [ ] UI-42 File dialogs (Import earlier progress, Export tier list): clicking the label next to the file-type
#           drop-down should open the drop-down too; today it flickers open and shut. Applies to the file
#           browser in general. Seen on Linux, where tk draws this dialog itself: fix it there, or replace
#           it with a small themed file picker that matches the app (Windows and macOS keep the system's
#           own dialog).
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
# [ ] UI-51 Look up a word to sort it (asked for): a little search icon opens a search over the whole unsorted
#           list (as you type, like Browse's search, but over words not placed yet); picking one makes it the
#           word on the card in Place new words, to sort now, without changing the queue order for the rest.
#           Where the icon goes is to be talked over first (beside the word card, in the header, or the tab
#           row). (Browse can already find placed words; W-1 looks words up from inside a definition.)
# [ ] UI-48 Keyboard shortcuts menu (asked for): Settings > Keyboard shortcuts... opens a dialog listing every
#           action that has a key (place in S..F, compare to anchors, don't know, better / same / worse /
#           back, left / right / tie / skip, undo, definitions, next / previous tab, zoom), grouped by
#           view, each with its current key(s). Click a key, press the new one, done; a key already used
#           in the same view is pointed out ("U is already Don't know: swap them?") instead of silently
#           taken. "Reset to defaults" per row and for all. Saved in the save (meta keymap), so it
#           survives restarts. Everything that shows a key follows the change: the button hints (1, Space,
#           U, Up / B...), the bottom-right hint and the menus' shortcut column. Builds on UI-18's single
#           key map (App._key_target), which becomes a table the dialog edits. Reserved keys that cannot be
#           rebound: Escape (cancel / close) and the Alt+letter menu keys.
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
# [ ] UI-26 Final pass.  Performance check on a ~1M-word save (no animation frame touches the
#           database), refresh the module docstring, and add a UI smoke test that drives every
#           mode and saves screenshots.
#
# --- Window by window (asked for: every window's planned changes in one place) -------------------------
#   Main window ........ header + tabs (UI-10, UI-27), status line (UI-15, UI-34), tier chart (UI-13,
#                        UI-31, UI-36), word card and its motion (UI-6, UI-16, UI-17), keys (UI-37,
#                        UI-47), duel view (UI-8, UI-19), empty states (UI-20), next-up peek (UI-21),
#                        definition drawer (UI-12, UI-35), background (UI-32), responsive sizing (UI-25)
#   Browse / edit ...... restyle (UI-23), open / close (UI-38), Delete unplaces (UI-39)
#   Anchor words ....... clean-up (UI-28), anchors follow their tier (UI-40)
#   Keyboard shortcuts . new dialog (UI-48)
#   Queue randomness ... diagrams (UI-41), shared dialog look (UI-24), grows into "How words are dealt" (ST-6)
#   Import / Export .... file dialog (UI-42)
#   Merge offer, "Where is my save file?" ... shared dialog look (UI-24, done)
#   Install packages ... tick boxes + sizes (ST-4, done), a web link per package (UI-30)
#   First-run progress . shared dialog look (UI-24)
#   Error dialog ....... shared dialog look (UI-24)
#   Hover notes ........ still and themed (UI-33)
#   Source & Updates ... T-6 / T-7 (later)
#
# --- Last: definitions as a way in (asked for; at the very end of the plan) --------------------------
# [ ] W-1  Click any word inside a definition to look it up. Its definition appears (the drawer and the
#           Browse pane), and the word joins the Browse list for the moment as a greyed-out row under F
#           ("not placed yet"). In Browse you can then sort it straight away with the tier buttons or
#           the 1-6 keys, which places it for real (it leaves the queue like any placed word); if you
#           do not, it disappears from the list again when Browse is refreshed or closed. Words that
#           are not in the word list are offered as "add to the list" first.
#
# --- Packaging as a program (T-6..T-8 asked for; built after the UI steps) ----------------------
# T-1..T-3 are the groundwork for T-6..T-8; T-4 and T-5 stay notes.
# Notes from the discussion: PyInstaller builds only
# for the OS it runs on (no cross-compiling), so this would be a build.py run once per OS, and only
# Linux can be tested from here (Windows / macOS builds would need testing on those machines).
# [ ] T-1  app_dir(): a save/config folder that is the executable's own folder (or the home folder)
#          when frozen. REQUIRED before any build: a one-file build unpacks to a temporary folder,
#          so a save kept "next to the script" would be deleted when the program exits.
# [ ] T-2  Bundle data: tell the builder to include wordfreq's data files (tens of MB); WordNet
#          stays an optional download as it is now.
# [ ] T-3  build.py: detects the OS, installs PyInstaller if missing, builds .exe / .app / binary.
#          Depends on ST-1 and ST-2 (a windowed program has no console for messages).
# [?] T-4  Launchers instead (cheaper): run.bat (Windows) and run.command (macOS) that install the
#          dependencies once and start the program. Roughly ten lines each, nothing to sign.
# [ ] T-6  "Make a program" button (asked for). File > Make a standalone program... (shown when running
#           from source): asks first, installs PyInstaller if missing (the ST-4 way), builds a one-file
#           program for this OS behind the progress window (T-3 is the engine), bundles the complete
#           source inside it (see T-7), then starts the new program and closes this window. Both use the
#           same save (T-1), so nothing is lost. Needs T-1 and T-2 first. Only builds for the OS it runs
#           on (PyInstaller cannot cross-compile; T-8 covers the other OS).
#           Always builds from the source as it is now, so every change since the last build (files
#           edited, added or deleted) is in the new program. Each build records a manifest (file list
#           + hashes) inside the program; if nothing changed since the last build, it says so and just
#           starts the existing program instead of rebuilding.
# [ ] T-7  "Back to source" button (asked for), the reverse of T-6. File > Unpack the source code...
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
# [ ] T-8  One command for packaged builds on Linux AND Windows (asked for). `python build.py` builds
#           for the OS it runs on (T-3). `python build.py --all` (or the "Build programs" workflow
#           button on GitHub) runs a GitHub Actions workflow (.github/workflows/build.yml) that builds
#           on a Linux and a Windows machine at the same time from the pushed source and attaches
#           word-tierlist-linux and word-tierlist-windows.exe as downloads; --all waits and fetches them
#           into dist/. Needs the code pushed to GitHub and a GitHub login (gh) for --all; without
#           them it explains and builds for this OS only. Building a Windows .exe on Linux through
#           Wine was considered and rejected: fragile, and the result would still need testing on Windows.
# [ ] T-9  Introduce the other form on first start (asked for). The first time the program starts as a
#           script (tierlist.py) it asks once: "Make this a standalone program? It saves, builds, and
#           reopens as the program" (T-6); the first time the built program starts it asks the reverse:
#           "Unpack the source code next to it?" (T-7). Either way the save is committed first, the
#           answer is remembered (meta), and both stay in the File menu afterwards. Never asked during
#           a first-run download or while another question is open; --no-install also silences it.
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
#           Still to do with T-8: the README's "Download for Windows / Linux" links to the Releases.
# [?] T-5  Per-OS caveats to document: Windows SmartScreen / antivirus warnings on unsigned
#          builds; macOS Gatekeeper (right-click > Open unless signed and notarized) and the need
#          for a Python with a current Tk; Linux depends only on system libraries.
#
# Decisions
#   Settled:  progress bar (UI-14): a bookshelf of spines by commonness (page .. library), "95% of text" after it;
#             modernize the top (menus, mode switch: UI-10) but keep the bottom bar's current look
#             (Undo, Browse / edit, Definition, key hints); light theme only (a dark theme can be
#             added later: theme.py is built so a second palette with the same keys drops in); the
#             session count stays as a muted "+N today", with the pace only in a hover note.
#   In consideration (shelved, not planned; ask before building):
#             - Next-up peek (UI-21).
#             - Boundary check's swap strip (UI-31, archived by request): the six tiers as pills with the swaps
#               per join under them, the join being checked in bold. Last version: ui_chart.SwapStrip in commit
#               9b78889. The swap counts are still recorded, so it would show the full history if it came back.
#   Planned:  Packaging, now asked for: T-6 (make a program), T-7 (back to source, as a sync) and T-8
#             (one command for Linux + Windows builds), which need T-1, T-2 and T-3 first. T-4 and T-5
#             stay notes. After the UI steps.
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

# Re-exported (hence the noqa comments) so the self-tests and anyone doing `import tierlist` can
# still reach everything as tierlist.Store, tierlist.TIER_COLORS, and so on.
from constants import DEFAULT_ANCHORS, FOCUS_ROUNDS, MODES, TIERS  # noqa: F401
from definitions import Definitions
from saves import (_pointer_file, choose_save, default_save_path, find_saves,  # noqa: F401
                   remember_save, save_progress, write_export)
from store import Store
from theme import PALETTE, TIER_COLORS, TIER_ROW, TIER_TEXT, tint  # noqa: F401
from wordsource import (build_word_list, build_wiktionary, compute_penalties,  # noqa: F401
                        prepare_queue)

# The window code needs tkinter, which is optional (e.g. Debian needs `apt install python3-tk`).
# Without it everything above still works; main() explains what is missing.
try:
    import tkinter as tk
    from tkinter import filedialog  # noqa: F401
    from app import App
    from fonts import init_fonts
    from errors import install_handlers, run_guarded
    from problems import SetupError, ensure_streams
    from startup import detach_console, ensure_packages, run_with_progress
    from ui_style import apply_ttk_style
    from browser import Browser  # noqa: F401
except ImportError as exc:
    if (getattr(exc, "name", "") or "").split(".")[0] not in ("tkinter", "_tkinter"):
        raise  # a real bug, not a missing tkinter
    tk = App = Browser = None
    from problems import SetupError, ensure_streams   # these need no tkinter


def main():
    """Start the program: parse options, pick and open the save, build the word list on first run, open the window."""
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
                    help="Windows: keep the console window open and print to it (for troubleshooting). "
                         "Normally the console is closed once the program starts and messages go to "
                         "tierlist.log next to the save file")
    ap.add_argument("--no-install", action="store_true",
                    help="never offer to pip-install missing packages (they are listed in requirements.txt)")
    ap.add_argument("--crash-test", action="store_true", help=argparse.SUPPRESS)   # ST-2: fakes a bug 3 s after start
    ap.add_argument("--seed", type=int,
                    help="seed for the random queue order (reshuffles the words you haven't placed yet)")
    args = ap.parse_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # --- 1. packages, stage 1 (ST-4). A private environment made earlier is used straight away. In a
    #        terminal, before any window, only tkinter is asked about (the window needs it to open);
    #        every Python package is offered later, in the window, each as its own choice.
    restart_argv = [os.path.abspath(__file__), *sys.argv[1:]]
    if not args.no_install and not getattr(sys, "frozen", False):
        deps.use_private_env(restart_argv, script_dir)
    if tk is None and deps.wants_terminal_setup(args.no_install):
        deps.terminal_setup(restart_argv)
    # tkinter is needed for the window (everything else works without it)
    if tk is None:
        sys.exit("tkinter is not installed. " + deps.tk_advice())

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
        if not args.console:
            detach_console(log_path)
        ensure_streams(log_path)          # started without a console at all (pythonw): print() must not crash
        # `current` is the source the list was built from; an older WordNet save is upgraded to
        # Wiktionary in place, keeping all progress.
        existing = store.count_words()
        current = store.get_meta("source") or ("wordnet" if existing else None)
        builds_wiktionary = (not args.wordlist and current != "custom"
                             and args.source == "wiktionary" and current != "wiktionary")

        def set_up(log):
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

        def launch():
            # --- 4. make sure the save has a word list and a queue order. This is the slow part on a
            #        first run, so it runs on a worker thread behind a progress window (startup.py); the
            #        window only appears if it takes more than a moment. Every message goes through `log`.
            root = tk.Tk()
            root.withdraw()                  # stays hidden until set-up is done
            init_fonts(root)
            apply_ttk_style(root)
            install_handlers(root, log_path, db_path)   # unexpected errors: log + friendly dialog
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
            # --- 5. show the main window; App runs until it is closed
            root.deiconify()
            App(root, store, Definitions(store), note=note, other_saves=others)
            if args.crash_test:           # lets you see the friendly error dialog; the program keeps running
                root.after(3000, lambda: 1 / 0)
            root.mainloop()

        # Always guarded: with or without a console, a failure ends in a dialog and a log entry.
        run_guarded(launch, log_path, db_path)


    # Everything from opening the save onward is guarded, so even a save that cannot be opened
    # ends in a dialog (logged next to this script until the save's folder is known).
    run_guarded(start, os.path.join(script_dir, "tierlist.log"), args.db)

if __name__ == "__main__":
    main()
