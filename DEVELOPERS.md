# Word Tierlister: developer guide

How the code fits together, where things live, and how to test, build and release it. The user-facing
introduction is the [README](README.md).

**Contents:** [Quick start](#quick-start) · [The big picture](#the-big-picture) ·
[Import layers](#import-layers) · [Start-up](#start-up) · [A key press](#a-key-press) ·
[The life of a word](#the-life-of-a-word) · [The save file](#the-save-file) · [Threads](#threads) ·
[Builds, releases and updates](#builds-releases-and-updates) · [Find your way](#find-your-way) ·
[Options](#options) · [Folders](#folders) · [Files](#files) · [Notes beside the code](#notes-beside-the-code) ·
[Where to change things](#where-to-change-things) · [Tests](#tests) · [Reference](#reference)

## Quick start

```sh
pip install -r requirements.txt      # wordfreq (required), nltk (optional: offline definitions, WordNet)
python tierlist.py --db test.db      # a throwaway save; --help lists every option
sh tests/run_tests.sh                # every self-test (KEEP_GOING=1 lists all failures)
python tools/check_release.py --tests   # the checks to pass before handing work over
```

tkinter ships with Python (Debian / Ubuntu: `sudo apt install python3-tk`). Window tests need a display; on a
headless Linux box they run under `xvfb-run` by themselves. The roadmap (every step, its status and the decisions
behind it) is the big comment block at the top of `tierlist.py`; `.claude/CLAUDE.md` holds the conventions.

## The big picture

`tierlist.py` starts everything. The save is a single SQLite file, and **`Store` is the only thing that touches
it**: every public `Store` method that changes something commits before it returns, so the program can be killed
at any moment without losing an answer. The main window (`App`) never keeps state of its own that matters: after
each action it asks the Store again and redraws (`App.refresh`).

```mermaid
flowchart TB
    user([You: keys and clicks])
    main["tierlist.py<br/>main(): options, find the save, set up, open the window"]
    startup["startup.py<br/>progress window; set-up on a worker thread"]
    wordsource["wordsource.py<br/>build the word list from Wiktionary or WordNet,<br/>frequencies, kinds of word, queue prep"]
    app["app.py: App<br/>the main window and its four modes"]
    widgets["widgets.py, ui_chart.py, smooth.py<br/>word card, tier pills, duel cards, toasts,<br/>definitions pane, tier chart, progress shelf"]
    dialogs["browser.py, dealing.py, tiercolours.py,<br/>shortcuts.py, sources.py, filepicker.py<br/>Browse and the settings windows"]
    defs["definitions.py: Definitions<br/>lookups on a worker thread"]
    store[("store.py: Store<br/>tierlist.db (SQLite)")]
    rude["rudeness.py, obscene.py<br/>which meanings are rude"]
    standalone["standalone.py, deps.py<br/>packages, builds, self-update"]
    net{{"the internet:<br/>kaikki.org Wiktionary, dictionaryapi.dev,<br/>GitHub releases, PyPI"}}

    user --> app
    main --> startup --> wordsource --> store
    main --> app
    wordsource --> rude
    app --> widgets
    app --> dialogs
    app -- "every action: a Store method<br/>(commits), then refresh()" --> store
    dialogs --> store
    app --> defs
    defs -- "cached in the defs table" --> store
    defs -.-> net
    wordsource -.-> net
    standalone -.-> net
    dialogs --> standalone
    store --> rude
```

## Import layers

A file only imports from files in earlier layers. `tools/check_release.py` enforces it (`LAYERS`), so the arrows
below can only point down. Only the UI layers import tkinter; `problems.py`, `deps.py` and everything else in the
bottom layer work without it. Each box lists the modules of one layer, and the arrows show what each layer really
imports (worked out from the code).

```mermaid
flowchart TB
    subgraph L6["entry point"]
        tierlist["tierlist.py"]
    end
    subgraph L5["the main window"]
        app["app"]
    end
    subgraph L4["windows and views"]
        direction LR
        ui_chart["ui_chart"] ~~~ browser["browser"] ~~~ filepicker["filepicker"] ~~~ shortcuts["shortcuts"] ~~~ tiercolours["tiercolours"] ~~~ dealing["dealing"] ~~~ sources["sources"]
    end
    subgraph L3["UI building blocks (tkinter)"]
        direction LR
        theme["theme"] ~~~ fonts["fonts"] ~~~ sizing["sizing"] ~~~ ui_style["ui_style"] ~~~ ui_motion["ui_motion"] ~~~ smooth["smooth"] ~~~ widgets["widgets"] ~~~ errors["errors"] ~~~ startup["startup"]
    end
    subgraph L2["words and saves (no tkinter)"]
        direction LR
        wordsource["wordsource"] ~~~ saves["saves"] ~~~ definitions["definitions"]
    end
    subgraph L1["the save"]
        store["store"]
    end
    subgraph L0["foundations (no tkinter)"]
        direction LR
        constants["constants"] ~~~ obscene["obscene"] ~~~ rudeness["rudeness"] ~~~ problems["problems"] ~~~ deps["deps"] ~~~ keymap["keymap"] ~~~ bundle["bundle"] ~~~ standalone["standalone"]
    end
    L6 --> L5 --> L4 --> L3 --> L2 --> L1 --> L0
    L6 -. "also store, saves, startup, deps, ..." .-> L1
    L5 -. "also store-free helpers:<br/>keymap, rudeness, deps, standalone" .-> L0
    L4 -. "browser, filepicker read the Store directly" .-> L1
```

Who uses whom, module by module (from the imports; `python tools/notes.py` writes the same into each file's
note):

| Module | Imports |
|---|---|
| `tierlist` | app, browser, constants, definitions, deps, errors, fonts, problems, saves, sizing, standalone, startup, store, theme, ui_style, wordsource |
| `app` | browser, constants, dealing, definitions, deps, errors, filepicker, fonts, keymap, rudeness, saves, shortcuts, sizing, sources, standalone, theme, tiercolours, ui_chart, ui_motion, ui_style, widgets, wordsource |
| `sources` | constants, deps, errors, filepicker, fonts, problems, saves, standalone, startup, theme, widgets |
| `browser` | constants, errors, fonts, keymap, sizing, smooth, store, theme, ui_motion, widgets |
| `filepicker` | errors, fonts, saves, store, theme, widgets |
| `dealing` | constants, fonts, obscene, rudeness, theme, widgets |
| `tiercolours` | constants, fonts, smooth, theme, ui_motion, widgets |
| `shortcuts` | fonts, keymap, sizing, theme, widgets |
| `ui_chart` | constants, smooth, theme, ui_motion |
| `widgets` | constants, definitions, fonts, rudeness, sizing, smooth, theme, ui_motion |
| `startup` | constants, deps, errors, fonts, problems, sizing, theme |
| `errors` | constants, fonts, problems, theme, ui_style, widgets |
| `ui_style` | fonts, theme |
| `smooth` | fonts |
| `wordsource` | constants, obscene, problems, rudeness |
| `saves`, `definitions` | constants |
| `store` | constants, obscene, rudeness |
| `standalone` | bundle, constants, deps |
| `rudeness` | obscene |
| `deps` | constants |
| `constants`, `obscene`, `problems`, `keymap`, `bundle`, `theme`, `fonts`, `sizing`, `ui_motion` | nothing of ours |

## Start-up

What `tierlist.main()` does, in order. Everything from opening the save onward runs inside `errors.run_guarded`,
so any failure ends in a friendly dialog and a line in `tierlist.log` instead of a traceback.

```mermaid
flowchart TB
    A["main()"] --> B["clean the environment (standalone.clean_env),<br/>certificates, load the typefaces"]
    B --> C["parse the options"]
    C --> D{"tkinter missing?"}
    D -- yes --> D1["deps.terminal_setup: offer to install it<br/>in the terminal, then restart"]
    D -- no --> E{"started from a terminal<br/>without --console?"}
    E -- yes --> E1["deps.detach_terminal: start again on its own<br/>(Windows: pythonw.exe) and give the prompt back"]
    E -- no --> F["run_guarded(start)"]
    F --> G["saves.choose_save: --db, else the save used last<br/>or the one with the most progress"]
    G --> H["Store(path); the log; the Linux launcher"]
    H --> I["new_root(): a hidden Tk with fonts and styles"]
    I --> J["startup.ensure_packages: one dialog,<br/>a tick box per missing package"]
    J --> K["startup.run_with_progress(set_up)<br/>on a worker thread, a progress window with time left"]
    K --> K1["set_up: build_wiktionary or the word list,<br/>then wordsource.prepare_queue"]
    K1 --> L["App(root, store, Definitions(store)).open_window()"]
    L --> M["root.mainloop()"]
    M --> N{"App.reopen asked?<br/>(dark mode, tier colours)"}
    N -- yes --> I2["app.reopen_while_asked: build the window again<br/>in the new look, then take over the old one"] --> M
    N -- no --> O["end_session in the log"]
```

## A key press

Every key goes through `App.on_key`. Keys are never hard-coded: `keymap.py` says what a key means in the current
view, and the user can change any of them. Input never waits for an animation: running ones hurry out of the way.

```mermaid
sequenceDiagram
    autonumber
    participant Tk as Tk event loop
    participant App as App.on_key (app.py)
    participant K as Keymap (keymap.py)
    participant Anim as Animator (ui_motion.py)
    participant S as Store (store.py)
    participant W as widgets
    Tk->>App: <KeyPress>
    App->>App: held key? App._repeat_allowed (500 ms, then every 250 ms)
    App->>Anim: hurry_all() (running animations speed up, never jump)
    App->>K: lookup(view, key)  (view: place, compare or duel)
    K-->>App: action, e.g. "place" or "left"
    App->>App: _key_target(action) gives the button and what it does
    App->>S: place(word, tier) / record_comparison(a, b, result, kind) / undo()
    S->>S: change the rows, push an undo step, COMMIT
    App->>App: refresh(): read the Store again
    App->>W: show the next word or pair, update the chart and shelf
    App->>W: the button flashes, and a Toast if there is news
```

## The life of a word

A word's state is a few columns of its row in `words` (`tier`, `skips`, `out`, `rating`, `games`). The four tabs
are four ways of moving words through these states.

```mermaid
stateDiagram-v2
    [*] --> Queued: build the word list (wordsource)
    Queued --> LeftOut: How words are dealt unticks its kind (out = 1)
    LeftOut --> Queued: ticked again
    Queued --> Skipped: Don't know / later (skips + 1)
    Skipped --> Queued: every fresh word has had its turn
    Queued --> Placed: 1-6, or Compare to anchors
    Placed --> Placed: Refine duel (Elo rating within its tier)
    Placed --> Placed: Boundary check (if the lower word wins, the two swap tiers)
    Placed --> Placed: Move to another tier in Browse
    Placed --> Queued: Unplace (Browse, Delete)
    Placed --> Conflict: answers in a circle (A > B > C > A)
    Conflict --> Placed: Resolve conflicts (the new answer replaces the old ones)
    note right of Placed
        Every change is one undo step in
        the history table: Ctrl+Z puts the
        rows back, even after a restart.
    end note
```

Which word comes next (`Store.next_unplaced`): fresh words first, then skipped ones, each in the seeded queue order
(`qkey`, set by `Store.reshuffle`: the odds of coming up early fall off with the frequency rank; compound words are
pushed back). Which pair comes next: `Store.pick_within` (fewest duels first, the nearest rating),
`Store.pick_boundary`, `Store.pick_conflict`.

## The save file

One SQLite file (`tierlist.db`). New indexes go in `store.WORD_INDEXES`, and writes of more than `BULK_ROWS` rows
go through `Store.bulk_write`.

```mermaid
erDiagram
    words {
        text word PK
        int rank "frequency rank, 1 = commonest"
        int tier "0-5 = S-F; NULL = not placed"
        real rating "Elo within its tier"
        int games "duels played"
        int skips "times put off for later"
        real qkey "seeded queue order"
        int pen "compound-word push-back"
        real freq "wordfreq frequency"
        int kinds "parts of speech (bits)"
        int obscene "smeared whole"
        int out "left out by How words are dealt"
        int rude "kinds of rude meaning (bits)"
        int rude_main "its main rude kind"
    }
    comparisons {
        int id PK
        text winner
        text loser
        int tie
        text kind "within, boundary or conflict"
        real ts
    }
    conflicts {
        text a PK
        text b PK
    }
    swaps {
        int comp_id PK "a boundary win that swapped tiers"
        int boundary
    }
    anchors {
        int tier PK
        text word
    }
    defs {
        text word PK
        text text "cached definition"
    }
    rude {
        text word PK
        text senses "the meanings the rules read"
        text smeared "which meanings are smeared"
    }
    history {
        int id PK
        text payload "rows as they were: one undo step"
        real ts
    }
    meta {
        text key PK
        text value "settings: zoom, dark_mode, keymap, tier_colors, qseed, ..."
    }
    words ||--o{ comparisons : "winner / loser"
    words ||--o{ conflicts : "a / b"
    comparisons ||--o| swaps : "comp_id"
    words ||--o| anchors : "one per tier"
    words ||--o| defs : "word"
    words ||--o| rude : "word"
```

## Threads

Tk is single-threaded, so only the main thread touches widgets. Worker threads hand their results back through
queues that the main loop polls. No animation frame may touch the database.

```mermaid
flowchart LR
    subgraph main["main thread: the Tk event loop"]
        App["App and every window"]
        Anim["Animator: animation frames<br/>(never the database)"]
    end
    subgraph workers["worker threads (never tkinter)"]
        Setup["startup.run_with_progress:<br/>building the word list"]
        Defs["Definitions._worker:<br/>WordNet, then dictionaryapi.dev"]
        Upd["the update check:<br/>standalone.latest_release"]
        RudeRead["App._start_rude_read:<br/>an older save's rude meanings"]
        Deal["dealing.py: a reshuffle<br/>(App.busy; nothing else writes)"]
        Pip["deps.install: pip, and a watcher<br/>measuring its download"]
        Watch["errors: the freeze watchdog<br/>(a window stuck for 10 s goes in the log)"]
    end
    Setup -- "log lines, queue" --> App
    Defs -- "drain(): results queue" --> App
    Upd -- "queue" --> App
    RudeRead -- "queue" --> App
    Deal -- "done" --> App
```

## Builds, releases and updates

```mermaid
flowchart LR
    src["the source<br/>(tierlist.py + src/)"] -- "tools/build.py<br/>(PyInstaller; standalone.py)" --> prog["a program for this computer<br/>(word-tierlister, .exe, .app),<br/>its source packed inside"]
    src -- "push to main" --> gh["GitHub"]
    gh -- "Actions > Build programs > Run workflow,<br/>or a pushed tag v&lt;VERSION&gt;" --> wf[".github/workflows/build.yml<br/>Linux, Windows, macOS builds,<br/>each started once to check it"]
    wf --> rel["a GitHub Release<br/>word-tierlister-linux, -windows.exe, -macos.zip<br/>(+ the old word-tierlist-* names)"]
    rel -- "README download links" --> users["people"]
    rel -- "File > Source & Updates > Update<br/>(sources.py, standalone.latest_release)" --> prog2["the program replaces itself<br/>(kept as .old until the new one starts)"]
    gh -- "git pull, or a sync of the source zip" --> src2["a source folder brought up to date"]
    prog -- "Unpack the source code" --> src
```

The download links in the README must keep naming the current assets (`standalone.RELEASE_ASSETS`);
`tests/_selftest_updates.py` checks them against the workflow.

## Find your way

| You want to change... | Start in |
|---|---|
| A ranking rule: duels, Elo, undo, the queue, conflicts, merging saves | `src/store.py` |
| What a key or button does, what shows on screen | `src/app.py` (`on_key`, `_key_target`, `_show_place`, `_show_pair`) |
| A key's default | `src/keymap.py` (`ACTIONS`) |
| The menus | `App._menu_items` in `src/app.py` |
| How a widget looks or animates | `src/widgets.py` (and its test, `tests/_selftest_widgets2.py`) |
| Colours | `src/theme.py` (`PALETTE`, `TIER_COLORS`, the dark look `DARK`, `contrast()`) |
| Fonts and text sizes | `src/fonts.py` (`font(role)`) |
| Window sizes, zoom, fitting the screen | `src/sizing.py`, `App._fit_window`, `App.set_zoom` |
| Rounded shapes and icons | `src/smooth.py` (`SmoothCanvas.round_rect`, `icon_image`) |
| The tier chart and the progress shelf | `src/ui_chart.py` |
| The word list: download, parsing, frequencies | `src/wordsource.py` |
| What counts as rude | `src/rudeness.py` (bump `RUDENESS_VERSION`), `src/obscene.py` |
| Definitions | `src/definitions.py` |
| An error's wording | `src/problems.py` (`describe`) |
| Packages and their install dialog | `src/deps.py`, `src/startup.py` |
| Builds, updates, unpacking the source | `src/standalone.py`, `src/sources.py`, `tools/build.py`, `.github/workflows/build.yml` |

The more detailed list is [Where to change things](#where-to-change-things), and every code file has a note
beside it with its rules and pitfalls: read `src/app.md` before editing `src/app.py`.

## Options

All optional; `python tierlist.py --help` explains each.

| Option | What it does |
|---|---|
| `--db FILE` | Use this save. Without it, the save you used last (or the one with the most progress) is found by itself. |
| `--wordlist FILE` | Start a new save from your own list, one word per line, in that order. |
| `--source wiktionary` / `wordnet` | Where a new save's words come from: all of English Wiktionary (default, about 1M) or WordNet's ~77k base forms. |
| `--wiktionary-file FILE` | Build from a kaikki.org English download you already have (`.jsonl` or `.jsonl.gz`). |
| `--include-phrases` | Also take multi-word entries such as "ice cream" (Wiktionary). |
| `--keep-download` | Keep the 3 GB Wiktionary download after building. |
| `--seed N` | Reshuffle the words you haven't placed yet with this seed. |
| `--console` | Keep the terminal / console attached and print to it (troubleshooting). |
| `--no-install` | Never offer to install missing packages, nor (on the first start) to make a program or unpack the source. |

## Folders

```
tierlist.py        run this. Your save (tierlist.db), its log and exports stay next to it.
requirements.txt   the Python packages (the program offers to install them itself)
src/               the program's modules; src/icons/ holds its icon (drawn by tools/make_icon.py), src/typefaces/
                   its two fonts (fetched by tools/make_typefaces.py)
tests/             the self-tests and run_tests.sh
tools/             check_release.py (pre-hand-off checks, builds the zip), layout_trace.py (layout jitter finder),
                   build.py + hooks/ (build it as a program), measure_rudeness.py (measures the rudeness rules),
                   make_icon.py (draws the icon), make_typefaces.py (fetches the fonts), speed_check.py and
                   stress_ui.py (speed and stress checks), notes.py (keeps the notes beside the code current)
.claude/           notes for Claude Code: CLAUDE.md (project notes) and CHECKLIST.md
.github/           the build and macOS test workflows, the release notes
docs/images/       the README's screenshots
README.md          the user-facing introduction; DEVELOPERS.md is this guide
```

`tierlist.py` stays at the top on purpose: the save is found "next to the script", so moving or
replacing the other folders never loses your list. A built program (File > Source & Updates, or `tools/build.py`) keeps it next to
the program instead (on macOS next to the .app), or, if that folder is read-only, in your user data folder
(`%APPDATA%\Word Tierlister`, `~/Library/Application Support/Word Tierlister`, `~/.local/share/word-tierlister`);
either way the save you used last is found again, so switching between the two loses nothing.

## Files

| File | Job |
|---|---|
| `tierlist.py` | Entry point: command-line options, start-up sequence, `main()`. Also holds the roadmap. |
| `src/constants.py` | The program's VERSION and GitHub repository (T-8), tier names, modes, ranking defaults, the kinds of words (ST-6) and the masked text of a censored word. No dependencies. |
| `src/obscene.py` | The kinds of rude meaning (Clinical, Crude, Swear word, Insult, Sexual, Slur), which start ticked and which are censored; Wiktionary's rude labels; a short list chosen by hand (the stand-in until a save has Wiktionary's meanings, and for a word added by hand). No tkinter, no internet. |
| `src/rudeness.py` | How rude each meaning is, by rules, no word list (OB-6): points towards each kind (Clinical, Crude, Swear word, Insult, Sexual, Slur) from Wiktionary's labels, its topics and categories, the definition's wording, the word itself and, when nltk's WordNet is installed, the matching WordNet meaning's place in its tree and its usage labels; a second pass over Wiktionary's synonym lists says which kind a slang meaning is; a meaning's kind; the word's points, its first meaning counting most (enough of them: the whole word smeared); word families (a word built from a rude one: its etymology, or that word's derived terms) add a little; what a word's scores lead to (`score_saved`: the kinds of its meanings, smeared whole, the meanings smeared); how the program keeps meanings compactly (`compact_entry`, `expand`, `has_signal`). No tkinter, no internet. |
| `src/keymap.py` | The keyboard shortcuts (UI-48): every action with a key, its view and default keys, your changes on top (saved in the save); key presses to key names. No tkinter. |
| `src/store.py` | `Store`: the SQLite save. Tiers, anchors (they follow their tier), Elo duels, undo, queue order, which words are dealt (kinds of word and of rude meaning, the ones left out; ST-6, OB-5), the meanings the rudeness rules read and what they found (OB-6), conflicts, boundary swaps, the progress shelf's tallies, merging. |
| `src/wordsource.py` | Building the word list (WordNet, Wiktionary; each word's parts of speech), compound detection, word frequencies (for the coverage tag), kinds for an older save (from its definitions), the meanings the rudeness rules read (`RudeCollector`, kept at the Wiktionary build; `fetch_rude_senses` for an older save, in the background) and scoring them (`find_rude`), queue prep. |
| `src/saves.py` | Where the save lives (`app_dir`: tierlist.py's folder, or a built program's own, T-1); finding / remembering your earlier save; export. |
| `.github/workflows/build.yml` | Build programs (T-8, T-16): builds the Linux, Windows and macOS (Apple Silicon) programs on GitHub (a button, or `tools/build.py --all`); a pushed tag `v<VERSION>` publishes them as a release. |
| `.github/workflows/macos.yml` | Test on macOS (T-18): on GitHub's Macs (Apple Silicon and Intel), runs every self-test, builds the program and starts it, and keeps screenshots of each stage and the built app as downloads of the run. Runs on pull requests that touch the code, pushes to main, and the Run workflow button. |
| `.github/release-notes.md` | The short note at the top of every release's page (T-5): the programs are unsigned, so Windows may warn (More info > Run anyway) and Linux needs the download made runnable. |
| `src/definitions.py` | Background definition lookup (WordNet offline, dictionaryapi.dev online); splitting it into senses; the word a meaning only names ("Alternative spelling of jail": `form_target`), whose first meaning the panes show under it. |
| `src/theme.py` | The two looks (light, and Dusk for dark mode, UI-77), each with its default tier colours; Browse's softer row tints, and `contrast()` (text about 7:1, UI-76). |
| `src/fonts.py` | Typography (UI-73): loads the two bundled typefaces for this program only (never installed) and builds the named size roles: Young Serif for the words, Atkinson Hyperlegible for the rest, the text in three sizes (20 / 12 / 10 pt). |
| `src/typefaces/` | Young Serif and Atkinson Hyperlegible (regular, bold, both italics), from Google Fonts under the SIL Open Font Licence (the licences beside them), with their line spacing tightened by `tools/make_typefaces.py`; `overhang.json`, the letters whose ink reaches past their box. |
| `src/ui_style.py` | ttk / tk styling (applies the palette and fonts to every widget; draws the tick boxes); puts the program's icon on every window (IC-1). |
| `src/icons/` | The icon (IC-1): the progress shelf's six spines in the tier colours on a cream tile with a slightly darker border (IC-4), the lilac mark over C. PNGs from 16 to 1024 px (windows, taskbar, the Linux launcher) and `icon.ico` (the Windows program's own icon). |
| `src/deps.py` | Packages: finds missing ones and installs them (measuring the download for a real speed and time left); the terminal stage, the private `.venv`; each package's size, purpose and web page; giving the terminal back and the applications-menu launcher (ST-5) (no tkinter). |
| `src/problems.py` | Plain-language error text (`describe`), `SetupError`, log helpers. No tkinter. |
| `src/errors.py` | Friendly error dialog, plain messages and question dialogs (all on `StyledDialog`; tick-box choices can link to a web page), global error handlers, `run_guarded` (the whole program runs inside it). |
| `src/sizing.py` | Screen/dpi-aware window sizing: usable area (xrandr on X11), `fit_size`, centring, dialog placement. |
| `src/ui_motion.py` | Easing, colour blending and the `Animator` (animations run on the Tk event loop). |
| `src/startup.py` | First-run progress window (set-up on a worker thread; time left, "Step i of n") and the window's package install step. |
| `src/smooth.py` | Smooth (anti-aliased) rounded shapes and curves for the canvases: drawn as small images, since Tk's own canvas shapes have jagged edges (worst on Windows); text whose letters reach past their boxes (Young Serif's j and f) is repainted whole (F-32). |
| `src/widgets.py` | `Tooltip` (hover notes), `RoundButton` (rounded pastel buttons with hover, press and key hints), `WordCard` (the big word on its card; its magnifier looks up any word to sort it now, typed on the card with a blinking caret; a censored word is smeared sideways, never past its own ends (F-33), its end letters smeared further inward (F-43), and un-smears under the pointer, `smear_items` / `Unsmear`), `TierRow` (the S..F pills), `TierChip` (a tier label drawn like a pill), `DuelCards` (the two duel cards with Tie / Skip), `AnchorLadder` (the S..F strip while comparing), the header pieces (`TabBar` mode tabs, which show only once they have work, `HeaderMenus` + `DropMenu`), `ChoiceButton` (drop-down choices), `Toast` (messages), `EmptyCard` (friendly "nothing to do" panels), `ShapeCard` (a queue shape and its curve, in How words are dealt), `StyledDialog` (the shared dialog frame), `SmearToggle` (the small "abc" pill, smeared or plain, that censors a kind of rude meaning or not), `LinkButton` (a small "opens elsewhere" icon, alone or after words: the Wiktionary and GitHub links), `DefinitionDrawer` (the definitions pane, with a slim scroll bar while its meanings do not all fit (F-34): it opens tall enough to show every sense when the screen has room, and eases taller for a longer definition; under "plural of colour" or "Alternative spelling of jail", that word's own meaning), `FileList` (the file picker's list) and other small widgets. |
| `src/ui_chart.py` | Each tab's own view at the top right: the tier chart (Place new words), `SettledChart` (Refine), `ConflictCard` (Conflicts); `Bookshelf`, the progress shelf under the status line (every spine one width, UI-79; a hovered spine lifts, its neighbours less; in the duel tabs a little triangle in each word's tier colour marks the spines the two words come from). |
| `src/dealing.py` | Settings > How words are dealt... (ST-6): the order (Most common first, or a little shuffled with its shape, spread, seed), which kinds of words (a tick box each, with counts; obscene words too, with a tick box per kind of rude meaning under it, OB-5, and beside each kind censoring can smear a small smear button to censor it or not, OB-7) and Censor obscene words; on the first start the same in three steps. |
| `src/shortcuts.py` | Settings > Keyboard shortcuts...: change any key (click it, press the new one), add or remove keys, swap on a clash; the 1-6 placing keys move as a set. |
| `src/tiercolours.py` | Settings > Tier colours... (UI-61, UI-80): click a tier's pill, then set its colour with the H / S / V bars or a hex code (each follows the other); a colour too dark for the tier's letter is said so and Apply waits; Reset to defaults; Apply saves them and shows them (the window is rebuilt in place). |
| `src/filepicker.py` | Import / Export file choosing on Linux (UI-42): what it found first (other saves, exports), a themed folder browser behind it; Windows and macOS keep their own dialogs. |
| `src/browser.py` | The Browse / edit window: search, Show (a tier, unplaced words, or the placed words of a kind) / Sort (or click a column heading; again to turn it round; its arrow fills as the rows load), rows in soft tier colours (a censored word reads b•••••d), Move to, Unplace (or the Delete key; Ctrl+Z undoes), definition; it opens complete and in its place, like the other windows, and remembers what it showed. |
| `src/app.py` | The main window and all four modes. |
| `tools/check_release.py` | Pre-hand-off checks (packages vs requirements, docs, tests listed, files in the right folder, each code file's notes up to date, the import layers); `--tests`, `--zip`. See `.claude/CHECKLIST.md`. |
| `tools/speed_check.py` | Times refresh, placing, duels and every Browse sort on a big throwaway save (a million words by default, dense and sparse); fails when something is more than twice its budget (F-9). |
| `tools/make_typefaces.py` | Fetches the two typefaces into `src/typefaces/` with their licences and tightens their line spacing (needs the internet and fontTools). Run it only to change the fonts. |
| `tools/make_icon.py` | Draws the icon into `src/icons/` at every size (each size from the shapes, small ones snapped to whole pixels; needs Pillow). Run it only to change the icon. |
| `tools/stress_ui.py` | Random actions on the real window (keys, tabs, resizes, Browse, dialogs, censoring) on a pretend small screen; fails on any error or a window bigger than the screen (F-9). |
| `tools/notes.py` | Keeps each code file's notes (`name.md` beside `name.py`) up to date: regenerates their uses / used by / tests / public API from the code, keeping the hand-written parts; `--check` lists what is missing or stale. |
| `src/bundle.py` | What a built program carries besides its code (T-2): wordfreq's English word lists only (1.6 of its 60 MB), langcodes' registry, nltk's VERSION; `python src/bundle.py` lists them. WordNet stays an optional download. |
| `src/standalone.py` | The program and its source (T-3, T-6, T-7): the complete source (the same list the zip ships), its manifest (a hash per file), whether the program next to tierlist.py was built from exactly this source, the PyInstaller build that carries the source inside the program, and unpacking / syncing that source into a folder (only the program's own files; edits kept as .bak); the newest release on GitHub and downloading its source (T-8). No tkinter. |
| `src/sources.py` | File > Source & Updates... (one panel since U-4). Updates (U-1): asks GitHub for the newest release and says why when it cannot (a private repository answers "Not Found"); "Update" replaces the program with the newest release's, or updates the source with git pull or a sync; both start again on the same save. From source (T-6): make a standalone program for this computer next to tierlist.py (same save), then start it; or start the one already built from this source. In the program: unpack its source into a folder (or bring one up to date), showing what will change first, then open it and offer to start tierlist.py (this one then closes). Either way, ticked to start with: update to the newest version on GitHub first (T-8); from source, the Updates section's "Update" updates this folder without making the program (T-13). |
| `tools/measure_rudeness.py` | Measures `src/rudeness.py`'s rules against an earlier sorting by Claude (OB-6; developers): `fetch` keeps every lower-case English entry of the Wiktionary download compactly (with its word family: the words its etymology names, its derived terms), `measure` says how often both lead to the same thing, per censoring policy, with or without each source (`--no-links`, `--no-wordnet`, `--no-families`). |
| `tools/build.py` | Builds the program for this system with PyInstaller (T-3; the work is in `src/standalone.py`): `python tools/build.py` (installs PyInstaller if missing; `--check` then runs the new program for a moment). Linux / Windows: one file, no console; macOS: an app bundle. Into `dist/`. `--all`: Linux, Windows and macOS at once on GitHub (T-8, T-16). |
| `tools/hooks/hook-nltk.py` | Replaces PyInstaller's nltk hook, which would pack the build machine's WordNet data into the program. |
| `tools/layout_trace.py` | Debugging: places words fast in a throwaway save and reports widgets that moved when they should not, one-frame spikes, and anything over the tier buttons (`--reduce-motion`, `--every`, `--zoom`, `--csv`). |

Layers, lowest first: `constants`, `obscene`, `rudeness`, `problems`, `deps`, `keymap`, `bundle`, `standalone` -> `store` -> `wordsource` / `saves` / `definitions` -> `theme`,
`fonts`, `sizing`, `ui_style`, `ui_motion`, `smooth`, `widgets`, `errors`, `startup` -> `ui_chart`, `browser`, `filepicker`, `shortcuts`, `dealing`, `sources` -> `app` -> `tierlist`. A file only imports from files
earlier in that list. Only the UI files import `tkinter`.

## Notes beside the code

Every code file has a note beside it (`src/app.py` and `src/app.md`, `tools/build.py` and `tools/build.md`, ...),
written for anyone about to edit it, people or agents: what the file is for, what it uses and what uses it, which
self-tests cover it, its public functions and classes, the rules that must stay true and the bugs fixed before (so
they stay fixed), and where to change things. The facts are generated from the code by `python tools/notes.py`, so
they cannot drift; the purpose and the rules are written by hand. `tools/check_release.py` fails when a note is
missing or out of date, and also checks that each module imports only from the layers below it.

## Where to change things

- A rule about ranking, duels, undo or the queue: `store.py`.
- Colours: `theme.py` (the light look and the dark one, Dusk, each with its default tier colours; `contrast()`). Settings > Tier colours...
  (`tiercolours.py`) and View > Dark mode keep them in the save; the window is rebuilt in the new look behind the
  old one, which it then replaces in place, same size and spot, Browse too (`App.reopen`, `App.take_over`).
  Fonts and sizes: `fonts.py` (the typefaces themselves: `src/typefaces/`, `tools/make_typefaces.py`). How widgets look: `ui_style.py`.
- What a key or button does, what appears on screen: `app.py` (`on_key`, `_key_target`, `next_tab` for Tab, `_show_place`, `_show_pair`).
- The menus (File / Edit / View / Settings): `App._menu_items` in `app.py`; the GitHub link at the top right of their row: `App._build_header` (`LinkButton` with words, UI-75).
- The order words come in, which kinds, censoring: Settings > How words are dealt (`dealing.py`; the data in
  `Store.deal_settings` / `set_deal`, `Store.reshuffle`).
- Zoom: View > Zoom in / out / Actual size, or Ctrl + / Ctrl - / Ctrl 0 (`App.set_zoom` / `zoom_step`, saved;
  what fits the screen: `App._fit_window`). The maximized window keeps a zoom of its own: maximizing or restoring
  the window brings back the zoom you last used in that state (`App._follow_maximize`, UI-57). A zoom in past what
  fits is refused with a "no" shake of its message, never tried on screen: the limits are found while the window is
  still hidden as it opens and kept for each screen (`App._precheck_zoom`, F-30). The page keeps room under its
  contents for a message, so one never covers the word card or the definitions pane (UI-72); comparing to anchors
  re-fits if it would not fit, the pane easing shorter (F-29). Browse has its own zoom (`Browser.zoom_by`).
- Contents growing with a bigger window (UI-25): `App._grow_for` / `App._apply_grow` (`GROW_MAX`, `GROW_STEP`).
- Definitions while comparing two words (UI-60): side by side, each under its own card (`DefinitionDrawer`'s two
  columns; one word is one column).
- Clicking a word in a definition (W-1): any word in a meaning, an example or a form's line is underlined under the
  pointer; a click shows its definition there (the main window's pane says "Back to ..." to return) and puts it in
  Browse for the moment, greyed at the bottom ("not placed yet"), where the tier buttons or the placing keys (1-6)
  place it for real; a refresh or closing Browse lets it go. A word not in the list is offered to add first.
  (`widgets.word_at` / `fill_definitions(on_word=)`, `App.look_up`, `Browser.look_up` / `show_lookups`.)
- Anything that must survive a restart: save it through a `Store` method (it commits).

## Tests

`sh tests/run_tests.sh` runs everything (`tests/_selftest*.py`), from any folder. Window tests need
tkinter and run headless under `xvfb-run` when there is no display. A single test runs on its own too:
`python tests/_selftest_ui.py`. Before handing work over: `python tools/check_release.py --tests`.
It stops at the first failure; `KEEP_GOING=1` runs them all and lists every failure. A test that runs past
`TEST_TIMEOUT` seconds (600 by default) is stopped, and shortly before that it prints where each thread was.
Without a Mac, the Test on macOS workflow runs the same tests on GitHub's Macs (Actions > Test on macOS).

## Reference

The details behind the README's features, for whoever changes them.

### How words are dealt

The first start asks three short questions (any time later: Settings > How words are dealt...):

- **Order:** "Most common first" (strictly by how common a word is) or "Mostly common, a little shuffled"
  (the default: its shape, spread and seed decide how much).
- **Which words:** nouns, verbs, adjectives, adverbs, obscene words, other, each a tick box with how many
  words it holds (point at one to see what it covers). Every kind starts ticked except "Obscene words".
  The word card names a word's kinds faintly above it ("noun · verb"; "other" is left out), and "compound word"
  for one made of words.
  Ticking it opens a tick box per kind of rude meaning: Clinical, Crude, Swear words and Insults start ticked,
  Sexual and Slurs do not ("Obscene words" shows a minus while only some are). "Obscene words" holds only the
  words censored as a whole (the ones smeared on the card); a word with one rude meaning among ordinary ones
  ("can", "come", "box") is an ordinary word, dealt with its kind of word, and only that meaning is smeared in
  its definitions. An obscene word comes up if one of its meanings is of a ticked rude kind, or it has a clean
  meaning and its kind of word is ticked; one whose meanings are all rude of unticked kinds is left out.
  Unticked ones are left out of the queue, never deleted; untick every kind of word but "Obscene words" to
  sort only those.
- **Censor obscene words** ("blurred, except on hover"; also View > Censor obscene words, a click away): a word is
  smeared sideways on the cards and in Browse's list until the pointer is over it, and reads b•••••d in messages,
  when its first (most common) meaning is rude enough; the word card writes what kind it mostly is (sexual, crude,
  swear word, slur) faintly above it, after its parts of speech ("noun · sexual"), censoring or not;
  inside the definitions (the drawer and Browse's pane) each rude meaning is smeared, un-smearing under the
  pointer (when the word itself is smeared, the pointer anywhere over the pane shows it and all its meanings), and
  once it shows its words can be clicked like any other. Only Crude, Swear word, Sexual and Slur meanings are
  smeared, never Clinical or Insult, and each of those four can be let through on its own: the small "abc" pill
  beside it under "Obscene words" is smeared while that kind is censored and plain while it is not (click it; the
  kinds open there while "Obscene words" or Censor obscene words is ticked). A word with several kinds stays smeared
  while any of them is censored. The words are picked out by rules, not by a person, so it can miss a rude word
  or smear an ordinary one: turning it on says so in the window it was turned on in (the whole note the first time
  in a save, under the tick box in How words are dealt or as a message in the main window; a short message after
  that), and so does a line under the tick box. Exports keep the real words.

What is rude is decided by rules, not a list (`src/rudeness.py`, OB-6): every meaning earns points towards the
six kinds from Wiktionary's labels, its topics and categories, the wording of the definition, WordNet when it is
installed, the links between words (Wiktionary's synonym lists) and word families ("bullshit" is built from
"shit"); its kind is the one with
the most points, if it has enough. A word's points come mostly from its first meaning: enough of them and the whole
word is smeared, otherwise only its rude meanings are. A plural, a clipping or another form counts as its word's
first meaning ("did" is "do", not its slang meaning; "boys" and "mayo" are ordinary words, their slang meanings
smeared in the definitions; "fucks" is not), and a Clinical meaning only counts when the word is about it ("penis",
not "take"). A slur or other rude meaning that is not a word's usual one smears that meaning only ("fairy"). A very common word (about the 3,000 commonest, by wordfreq) is rarely meant rudely: only meanings
Wiktionary labels plainly rude count for it ("box: (vulgar) the vagina", not "top: (slang) fellatio"), and a
hedged label never smears it whole ("what the hell" is only mildly vulgar). A hyphenated word with a rude word
among its parts makes its slang meanings as rude ("piss-taker"; "doo-wop" and "tit-for-tat" have no slang
meaning, so they stay as they are). Words a definition only gives as examples ("such as slime or semen") do not
count; in a word smeared whole, a meaning that names the word itself is smeared too ("an instance of
skull-fucking"). A
"derogatory" label alone is not an insult unless the definition describes a person badly; a euphemism is the
polite word ("pass water"); a slang meaning that is itself a rude word ("dam: Damn.") is rude like it.
A word goes into the rude kinds only when it is censored as a whole ("idiot" and "penis" are ordinary words, and
so is "can", whose rude meaning is smeared in its definitions only). A group's own name is never a slur ("jews", "trans", "gay", "queer"), even where some uses are labelled
offensive; a meaning is a slur when it is marked as one (a slur, ethnic or vulgar label: "kike", "dyke").
The Wiktionary build keeps the meanings the rules read (about 150,000 words of a million, in the save's `rude`
table) and scores them once at the end of setting up (about a minute; again only when the rules change).
A save from before this, or one made from a word list, reads them from the Wiktionary download in the background
while you sort (once, resumable; until then its earlier flags and a short list chosen by hand in
`src/obscene.py` stand in). `tools/measure_rudeness.py` measures the rules against an earlier sorting by Claude
(79% the same outcome, 81% for the commonest words). That earlier way, Claude sorting the words and a review tab
to check them, is archived (see the roadmap's OB-3 / OB-4).

### Building a program

`python tools/build.py` turns the source into a program for the system it runs on (`dist/word-tierlister` on
Linux, `dist/word-tierlister.exe` on Windows, `dist/Word Tierlister.app` on macOS; about 25 MB). It installs
PyInstaller first if it is missing. Add `--check` to start the new program for a moment afterwards. The program
keeps its save next to itself (or in your user data folder when that folder is read-only) and finds the save you
used from source, so switching loses nothing. PyInstaller cannot build for another system: build on each one,
or on GitHub:

- `python tools/build.py --all` builds for Linux, Windows and macOS at once on GitHub's machines (the "Build
  programs" workflow, `.github/workflows/build.yml`, also on the Actions tab's Run workflow button), waits, and
  fetches `word-tierlister-linux`, `word-tierlister-windows.exe` and `word-tierlister-macos.zip` into `dist/`. It needs your commits pushed and GitHub's
  command-line tool logged in (`gh auth login`); without them it says what is missing and builds for this
  computer only. GitHub only starts the workflow once it is on the repository's default branch.
- **Publishing a release** (what the README's download links point to): set `VERSION` in `src/constants.py` and get
  it onto `main`, then on GitHub open Actions > Build programs > **Run workflow**, tick **Publish as a release** and
  run it (it makes the tag `v<VERSION>` itself); or tag and push it: `git tag v1.0.0 && git push origin v1.0.0`. The same workflow builds the three programs,
  starts each once to check it runs, and attaches them to a new release, whose page starts with
  `.github/release-notes.md`. (The macOS one is for Apple Silicon; it is not signed either.)

### Windows notes

- Run with `python tierlist.py`, or double-click it (or `pythonw tierlist.py`). The black console window closes
  by itself a moment after the program starts: it starts itself again with `pythonw.exe` (Python with no
  console window) and the first copy ends, so a double-clicked console closes and a terminal gets its prompt
  back. No `.pyw` file is needed, so the same source runs on Linux and macOS unchanged. Messages that would have
  been printed there go to `tierlist.log` next to your save file. If you want the console back for
  troubleshooting, run `python tierlist.py --console`.
- If something goes wrong, a dialog explains it in plain words (with Show details / Copy details) and the technical trace is added to `tierlist.log`. Your progress is saved after every action, so the program keeps running after most errors.

To see the friendly error dialog on purpose, start with `python tierlist.py --crash-test`: three
seconds after start it raises a fake bug. The dialog appears and the program keeps running.

### Running it on Linux / macOS

- Started from a terminal, the program opens its window and gives the terminal its prompt back: you can
  close the terminal, and the program keeps running. Its messages go to `tierlist.log` next to your save
  (`--console` keeps the terminal attached and prints there). If the window cannot open (no desktop), it
  stays in the terminal and says why.
- **Add to applications menu** (Linux; in File > Source & Updates, in the program, until it is there) puts Word
  Tierlister in your desktop's applications menu, so it starts with no terminal at all. Making the program from
  source has a tick, on to start with, that does the same for the new program; if Word Tierlister is in the menu already, the menu
  moves over to the new program by itself. On Windows it is **Add to Start menu**: a shortcut in your own Start menu (no administrator needed), which starts it
  with no console window and shows its icon (`deps.add_to_start_menu`, made by Windows' own PowerShell).
- The taskbar shows the program's icon: on Linux every start keeps a launcher for it
  (`~/.local/share/applications/word-tierlister.desktop`, out of the menu until you add it), which is how desktops
  such as GNOME know a window's icon.

### Updating

File > Source & Updates... is one panel for updates, making the program and getting the source back. Its
**Updates** section, at the top, says which version you have and which form you are running, and asks GitHub for
the newest release. If a newer one is out, **Update** there updates the form you are running, then starts it again
with the same save:

- **The program** (Windows `.exe`, Linux, macOS `.app`) downloads the new program for this computer beside itself,
  puts it in its place and starts it. The old one is kept as `.old` until the new one has started, which then
  removes it. If the program sits somewhere it cannot write (such as Program Files), it says so; the release page
  has the download. A source folder the program unpacked beside itself is brought up to date too.
- **The source** (`tierlist.py`): a git checkout is updated with `git pull` (git refuses rather than touch your own
  changes, and the dialog shows what it said); any other folder downloads the new source and shows what it would
  change before doing it (only the program's own files; a file you edited is kept as `.bak` first).

At start, at most once a day, it checks quietly too: a newer version is mentioned once, in a short note.

If the check fails, the panel says why. "GitHub said Not Found (404)" almost always means the repository on GitHub
is private: GitHub hides a private repository's releases from anyone not signed in, and the program never signs in.
Updating from inside the program only works while the repository is public.

### Making it a program

Below the Updates section, File > Source & Updates... (when running `tierlist.py`) makes Word Tierlister into one program for this computer:
`word-tierlister` on Linux, `word-tierlister.exe` on Windows, `Word Tierlister.app` on macOS, next to `tierlist.py`,
so it keeps using the same save and no longer needs Python. It takes a minute or two, then starts the new program
and closes this window. First it checks that what the build needs is installed: the builder (PyInstaller, about
15 MB), wordfreq, and nltk if you want offline definitions in the program. Anything missing is offered in one
dialog, a tick box each, as on the first start (untick the optional ones to install only what is needed). Packages
the program never uses (matplotlib, Pillow, numpy and the like) are always left out of the build, even when they
are on your computer, so a broken one cannot stop it. The program carries its
complete source inside it. If nothing has changed since the last build, it offers to start that program instead.

The first time each form starts, it offers the other once, when nothing else is being asked: `tierlist.py` asks
"Make this a standalone program?" (yes builds it and reopens as it). The program does not ask: its first start
unpacks its source into "Word Tierlister source" beside it and says so, unless a copy of the source is there
already (it sits next to `tierlist.py`, or a folder beside it holds one, whatever its name). Both are remembered in
the save and stay in File > Source & Updates. Not done when a program already sits next to `tierlist.py`, nor
with `--no-install`.

Either way that section has a tick box, ticked to start with: **Update to the newest version first** (greyed out
until the Updates section finds a newer version). Ticked and newer than yours, making the program builds
it from that version's source (your files are not changed), and unpacking downloads it and shows what it would
change before doing it, so unpacking is also how you update. Offline, or already the newest: it says so and uses
the version you have. Your save is never touched.

Running from source, the Updates section's **Update** downloads the newer version and brings this folder up to
date with it, without making the program (what it will change is shown first; only the
program's own files change, a file you edited is kept as `.bak` first), then Word Tierlister starts again from the
new source with the same save. In a git checkout it runs `git pull` instead.

In the program, the same panel gives the source back: **Unpack the source code** writes it into a folder
(beside the program, "Word Tierlister source", or one you pick), laid out like this repository. Unpacking into a
folder you unpacked into before brings it up to date: changed files are updated, new ones added and ones the program
no longer has removed. Only the program's own files are touched (your save, its log or a .venv never are), and a
file you edited there is kept as `name.bak` first. What it will do is shown before it does it. Then the folder opens
and it offers to start `tierlist.py` from there (that needs Python on the computer; it uses the same save). Starting
the other form, from either side, closes the one you started it from, so only one of them uses the save at a time,
and the one started never inherits the built program's own settings (its Tcl / Tk folders, which vanish when it
closes), so the unpacked source can build the program again. Making the program from source always asks first
**Clean up behind?**, however the source came to you (a download, a clone, or unpacked from the program):
**Keep the source** (the default) puts the program next to `tierlist.py` as usual; **Zip it** and **Remove it**
put it there too, in the folder where the source is, pack the source into a zip in that folder first (for Zip it),
and the program removes the source's files as it starts, leaving itself, your save and the zip in the folder. Only
the source's own files are removed: anything you added there stays, and so does a git checkout's history (`.git`).
(A source unpacked from a program that sits beside its folder replaces that program instead, and your save moves
next to it.) The program carries its source inside it, so it can always be unpacked again.

### Missing packages
Installing happens in two stages.

1. **In the terminal, before any window.** Only `tkinter` (the window toolkit), since without it there
   is no window to ask in. It asks `Install it now? [Y/n]` (Enter = yes), installs it with your
   system's package manager (apt-get, dnf, pacman, zypper, or Homebrew on macOS; sudo may ask for your
   password) and restarts the program.
2. **In the window.** Every Python package in one dialog, each with its own tick box and its size:
   `wordfreq` (required, marked with a red *, about 70 MB: it ranks the words) and `nltk` (optional,
   about 35 MB with its dictionary data: offline definitions, and the WordNet word list).
   An optional package you leave unticked is not offered again. If your system Python refuses pip
   installs (Debian, Ubuntu, Homebrew), it offers to make a private `.venv` next to the program,
   installs there, and from then on starts with it automatically.

What comes from the system rather than from pip is offered the same way: pip itself (Python's own `ensurepip`
first), Python's `venv` module when the private environment needs it (Debian / Ubuntu keep it apart), and Python
itself when a built program unpacks its source and nothing can run it. From the window your system asks for your
password with its own prompt (`pkexec`); on Windows, Python comes from `winget`. Git is never needed.

It only asks when something is missing. Started without a terminal (pythonw, a shortcut), only the
window stage runs. `--no-install` turns all of it off.

### The log

`tierlist.log` sits next to your save. It keeps everything that goes wrong: errors (with a friendly dialog as well),
a window that stops answering for 10 seconds (and where the program was stuck), a hard crash, and a session that
ended without closing. Each start is marked with the version and the system it runs on. Send it along with a report.

