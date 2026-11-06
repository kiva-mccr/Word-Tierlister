#!/usr/bin/env python3
"""
Word Tierlister
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
* Looks: light by default, View > Dark mode for the warm "Dusk" night; Settings > Tier colours for your own
  colours; the words in Young Serif, the rest in Atkinson Hyperlegible (both ship with it).

Code map (run tierlist.py; it stays at the top of the folder, next to your save. The modules below
live in src/, the self-tests in tests/, the developer's tools in tools/ (check_release, layout_trace, build,
measure_rudeness, notes, speed_check, stress_ui, make_icon, make_typefaces), the Claude notes in .claude/; each code file has a note beside it (name.md: read it
before editing the file); DEVELOPERS.md has the same map with more detail)
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
    theme.py        the light and Dusk looks (UI-1, UI-77).  fonts.py  the bundled typefaces, size roles (UI-2, UI-73).
    sizing.py       window sizes from the screen and the contents; monitors; Windows display scaling.
    ui_style.py     ttk / tk styling (UI-3).          ui_motion.py easing, colour blend, Animator (UI-4).
    smooth.py       soft-edged rounded shapes, curves and icons drawn as images (UI-53).
    smears.py       censored words drawn smeared (ST-6).    popups.py  Toast and Tooltip (UI-11, UI-13).
    buttons.py      RoundButton, the tier pills, small icon and smear buttons, the developer tools' bubbles.
    menus.py        drop-down menus, choices, the header menus and tabs (UI-10, UI-43).
    drawer.py       the definitions pane (UI-12).   cards.py  the word card, duel cards and other drawn panels.
    dialogs.py      StyledDialog, every dialog's frame (UI-24).   widgets.py  refresh_widgets after a font change.
    errors.py       friendly error / message / question dialogs, error handlers, run_guarded (ST-2).
    startup.py      first-run progress window; runs set-up on a worker thread (ST-1).
    ui_chart.py     each tab's view at the top right (the tier chart...) and the progress shelf.
    browser.py      Browser: the Browse / edit window.
    filepicker.py   the app's own Import / Export file choosing on Linux (UI-42).
    shortcuts.py    Settings > Keyboard shortcuts... (UI-48).
    review.py       the review of rude meanings by hand (OB-9; a developer tool: How words are dealt's bubble or --review-rude).
    tiercolours.py  Settings > Tier colours... (UI-61).
    dealing.py      Settings > How words are dealt... and the first start's three steps (ST-6).
    sources.py      File > Source & Updates...: updates; make a standalone program; in the program, unpack its source.
    devtools.py     the developer tools' bubbles (Settings > Developer tools): the review words, the tuner, Log, Crash test.
    app.py          App: the main window and all modes.

Layers: each module imports only from the ones before it (DEVELOPERS.md draws them; tools/check_release.py
LAYERS enforces them), and only the UI layer imports tkinter, so the core runs and is tested without it.
"""
# The roadmap (every step, what was asked and built, the decisions) is ROADMAP.md, next to this file.
import argparse
import json
import os
import sys

# The program's modules live in src/ (R-1); this file stays at the top of the folder, next to your save.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import deps  # noqa: E402  (after the path line above)
import launch  # noqa: E402
import standalone  # noqa: E402

# Re-exported (hence the noqa comments) so the self-tests and anyone doing `import tierlist` can
# still reach everything as tierlist.Store, tierlist.TIER_COLORS, and so on.
from constants import DEFAULT_ANCHORS, FOCUS_ROUNDS, LOG_FILE, MODES, REVIEW_FILE, TIERS, VERSION, WM_CLASS, plan_line  # noqa: F401
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
    from fonts import init_fonts, load_typefaces
    from errors import install_handlers, run_guarded
    from problems import end_session, ensure_streams, open_log, start_session
    from startup import detach_console, ensure_packages, run_with_progress
    from ui_style import apply_ttk_style
    from browser import Browser  # noqa: F401
except ImportError as exc:
    if (getattr(exc, "name", "") or "").split(".")[0] not in ("tkinter", "_tkinter"):
        raise  # a real bug, not a missing tkinter
    tk = App = Browser = None
    from problems import end_session, ensure_streams, open_log, start_session   # (no tkinter)


def main():
    """Start the program: parse options, pick and open the save, build the word list on first run, open the window."""
    if not getattr(sys, "frozen", False):     # (started by a built program: its Tcl / Tk folders are not ours and
        clean = standalone.clean_env()        # are gone once it closes; T-10, reported)
        for key in set(os.environ) - set(clean):
            del os.environ[key]
        os.environ.update(clean)
    deps.use_system_certificates()            # (U-3: a built program trusts this computer's certificates)
    if tk is not None:
        load_typefaces()                      # (before the first Tk: a Mac's Tk may not see fonts added after it)
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
    ap.add_argument("--keep-download", action="store_true",
                    help="keep the 3 GB Wiktionary download after building the word list")
    ap.add_argument("--console", action="store_true",
                    help="keep the terminal (Linux, macOS) or console window (Windows) attached and print to "
                         "it, for troubleshooting. Normally the program carries on in its own window, the "
                         "terminal gets its prompt back and messages go to tierlist.log next to the save file")
    ap.add_argument("--no-install", action="store_true",
                    help="never offer to pip-install missing packages (they are listed in requirements.txt), "
                         "nor to make a program / unpack the source on the first start")
    ap.add_argument("--review-rude", nargs="?", const="", default=None, metavar="FILE",
                    help="(developer) review the rude words' meanings by hand: FILE, or rude_review.jsonl next to "
                         "the save (from tools/measure_rudeness.py sample); the answers go beside it and only "
                         "test the rules")
    ap.add_argument("--crash-test", action="store_true", help=argparse.SUPPRESS)   # ST-2: fakes a bug 3 s after start
    ap.add_argument("--remove-source", help=argparse.SUPPRESS)  # T-12: the unpacked source this was made from
    ap.add_argument(standalone.BUILD_NIGHTLY, help=argparse.SUPPRESS)  # the program to build in place of (nightly)
    ap.add_argument("--seed", type=int,
                    help="seed for the random queue order (reshuffles the words you haven't placed yet)")
    args = ap.parse_args()
    if args.remove_source:                    # (cleaning up behind, T-12: in the background, while the old window
        import threading                      # closes; only the program's own files, never a save)
        threading.Thread(target=standalone.remove_source, args=(args.remove_source,), daemon=False).start()
    if getattr(sys, "frozen", False):         # (U-1: the program an update replaced, once it has closed)
        import threading
        threading.Thread(target=standalone.remove_old_program, daemon=True).start()
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
        log_path = os.path.join(os.path.dirname(db_path), LOG_FILE)
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
        builds_wiktionary = launch.builds_wiktionary(current, args.wordlist, args.source)

        def set_up(log):
            # the word list (an older WordNet save is upgraded to Wiktionary in place, keeping all progress) and the
            # queue; every step is named first for the progress window's "Step 2 of 5" (launch.stages)
            launch.set_up(store, log, existing, current, wordlist=args.wordlist, source=args.source,
                          wiktionary_file=args.wiktionary_file, keep_download=args.keep_download, seed=args.seed)

        def new_root():
            r = tk.Tk(className=WM_CLASS)   # (named, so a Linux taskbar finds the program's icon: ensure_launcher)
            r.withdraw()                     # stays hidden until set-up is done / the window is built
            init_fonts(r)
            apply_ttk_style(r)
            install_handlers(r, log_path, db_path)      # unexpected errors: log + friendly dialog
            return r

        def open_program():
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
                        system_optional=deps.SYSTEM_OPTIONAL, declined=declined, restart=restart, home=script_dir,
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
            if args.build_nightly and not getattr(sys, "frozen", False):   # (the program's nightly update: build it
                from sources import SourceDialog                               # from this source, in its place)
                root.after(500, lambda: SourceDialog(app, go=True, target=args.build_nightly))
            if args.review_rude is not None:      # (OB-9: a developer option)
                review = args.review_rude or os.path.join(os.path.dirname(os.path.abspath(store.path)), REVIEW_FILE)
                if os.path.exists(review):
                    app.open_review(review)
                else:
                    print(f"No review file at {review}: make one with tools/measure_rudeness.py sample.")
            if args.crash_test:           # lets you see the friendly error dialog; the program keeps running
                root.after(3000, lambda: 1 / 0)
            root.mainloop()
            reopen_while_asked(app, store, defs, new_root)

        # Always guarded: with or without a console, a failure ends in a dialog and a log entry.
        try:
            run_guarded(open_program, log_path, db_path)
        finally:
            end_session(log_path)         # (not reached by a hard crash or a kill: the next start says so)


    # Everything from opening the save onward is guarded, so even a save that cannot be opened
    # ends in a dialog (logged next to this script until the save's folder is known).
    run_guarded(start, os.path.join(script_dir, LOG_FILE), args.db)

if __name__ == "__main__":
    main()
