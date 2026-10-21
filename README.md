# Word Tier List

Tier-list every English word (S / A / B / C / D / F). Progress autosaves to SQLite after every
action and resumes automatically, even if you replace these files.

    python tierlist.py                 # options: python tierlist.py --help

On the first start it offers to install what it needs (see "Missing packages"), or install it yourself
first: `pip install -r requirements.txt`.

See the docstring at the top of `tierlist.py` for how it works and the full code map; the roadmap
(UI, start-up and packaging steps, ticked as built) is the comment block right under it.

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
| `--no-install` | Never offer to install missing packages. |
| `--review-obscene` | (Developers) a tab for checking the words flagged as obscene, one by one. |

## Folders

```
tierlist.py        run this. Your save (tierlist.db), its log and exports stay next to it.
requirements.txt   the Python packages (the program offers to install them itself)
src/               the program's modules
tests/             the self-tests and run_tests.sh
tools/             check_release.py (pre-hand-off checks, builds the zip), layout_trace.py (layout jitter finder),
                   bundle.py (the data a built program carries), build.py + hooks/ (build it as a program),
                   classify_obscene.py (sorts the rude words into kinds with Claude; developers only)
.claude/           notes for Claude Code: CLAUDE.md (project notes) and CHECKLIST.md
```

`tierlist.py` stays at the top on purpose: the save is found "next to the script", so moving or
replacing the other folders never loses your list. A built program (`tools/build.py`) keeps it next to
the program instead (on macOS next to the .app), or, if that folder is read-only, in your user data folder
(`%APPDATA%\Word Tier List`, `~/Library/Application Support/Word Tier List`, `~/.local/share/word-tierlist`);
either way the save you used last is found again, so switching between the two loses nothing.

## Files

| File | Job |
|---|---|
| `tierlist.py` | Entry point: command-line options, start-up sequence, `main()`. Also holds the roadmap. |
| `src/constants.py` | Tier names, modes, ranking defaults, the kinds of words (ST-6) and the masked text of a censored word. No dependencies. |
| `src/obscene.py` | Which words are obscene (ST-6): most or the first of a word's meanings rude, read from Wiktionary's labels (the download's tags or a page's wikitext); a short list chosen by hand stands in until a save has them. No tkinter, no internet. |
| `src/keymap.py` | The keyboard shortcuts (UI-48): every action with a key, its view and default keys, your changes on top (saved in the save); key presses to key names. No tkinter. |
| `src/store.py` | `Store`: the SQLite save. Tiers, anchors (they follow their tier), Elo duels, undo, queue order, which words are dealt (kinds, obscene words, the ones left out; ST-6), conflicts, boundary swaps, the progress shelf's tallies, merging. |
| `src/wordsource.py` | Building the word list (WordNet, Wiktionary; each word's parts of speech), compound detection, word frequencies (for the coverage tag), kinds for an older save (from its definitions), the obscene words (from the download's labels, or Wiktionary's pages for an older save), queue prep. |
| `src/saves.py` | Where the save lives (`app_dir`: tierlist.py's folder, or a built program's own, T-1); finding / remembering your earlier save; export. |
| `src/definitions.py` | Background definition lookup (WordNet offline, dictionaryapi.dev online); splitting it into senses. |
| `src/theme.py` | Colour palette, tier colours (and the softer Browse row tints). |
| `src/fonts.py` | Typography: font family and named size roles. |
| `src/ui_style.py` | ttk / tk styling (applies the palette and fonts to every widget; draws the tick boxes). |
| `src/deps.py` | Packages: finds missing ones and installs them (measuring the download for a real speed and time left); the terminal stage, the private `.venv`; each package's size, purpose and web page; giving the terminal back and the applications-menu launcher (ST-5) (no tkinter). |
| `src/problems.py` | Plain-language error text (`describe`), `SetupError`, log helpers. No tkinter. |
| `src/errors.py` | Friendly error dialog, plain messages and question dialogs (all on `StyledDialog`; tick-box choices can link to a web page), global error handlers, `run_guarded` (the whole program runs inside it). |
| `src/sizing.py` | Screen/dpi-aware window sizing: usable area (xrandr on X11), `fit_size`, centring, dialog placement. |
| `src/ui_motion.py` | Easing, colour blending and the `Animator` (animations run on the Tk event loop). |
| `src/startup.py` | First-run progress window (set-up on a worker thread; time left, "Step i of n") and the window's package install step. |
| `src/smooth.py` | Smooth (anti-aliased) rounded shapes and curves for the canvases: drawn as small images, since Tk's own canvas shapes have jagged edges (worst on Windows). |
| `src/widgets.py` | `Tooltip` (hover notes), `RoundButton` (rounded pastel buttons with hover, press and key hints), `WordCard` (the big word on its card; its magnifier looks up any word to sort it now; a censored word is smeared sideways and un-smears under the pointer, `smear_items` / `Unsmear`), `TierRow` (the S..F pills), `TierChip` (a tier label drawn like a pill), `DuelCards` (the two duel cards with Tie / Skip), `AnchorLadder` (the S..F strip while comparing), the header pieces (`TabBar` mode tabs, which show only once they have work, `HeaderMenus` + `DropMenu`), `ChoiceButton` (drop-down choices), `Toast` (messages), `EmptyCard` (friendly "nothing to do" panels), `ShapeCard` (a queue shape and its curve, in How words are dealt), `StyledDialog` (the shared dialog frame), `DefinitionDrawer` (the definitions pane: it opens tall enough to show every sense when the screen has room), `FileList` (the file picker's list) and other small widgets. |
| `src/ui_chart.py` | Each tab's own view at the top right: the tier chart (Place new words), `SettledChart` (Refine), `ConflictCard` (Conflicts); `Bookshelf`, the progress shelf under the status line (a hovered spine lifts, its neighbours less; in the duel tabs a little triangle in each word's tier colour marks the spines the two words come from). |
| `src/dealing.py` | Settings > How words are dealt... (ST-6): the order (Most common first, or a little shuffled with its shape, spread, seed), which kinds of words (a tick box each, with counts; obscene words too) and Censor obscene words; on the first start the same in three steps. |
| `src/shortcuts.py` | Settings > Keyboard shortcuts...: change any key (click it, press the new one), add or remove keys, swap on a clash; the 1-6 placing keys move as a set. |
| `src/filepicker.py` | Import / Export file choosing on Linux (UI-42): what it found first (other saves, exports), a themed folder browser behind it; Windows and macOS keep their own dialogs. |
| `src/browser.py` | The Browse / edit window: search, Show (a tier, unplaced words, or the placed words of a kind) / Sort (or click a column heading; again to turn it round; its arrow fills as the rows load), rows in soft tier colours (a censored word reads b•••••d), Move to, Unplace (or the Delete key; Ctrl+Z undoes), definition; it opens complete and in its place, like the other windows, and remembers what it showed. |
| `src/app.py` | The main window and all four modes. |
| `tools/check_release.py` | Pre-hand-off checks (packages vs requirements, docs, tests listed, files in the right folder); `--tests`, `--zip`. See `.claude/CHECKLIST.md`. |
| `tools/bundle.py` | What a built program carries besides its code (T-2): wordfreq's English word lists only (1.6 of its 60 MB), langcodes' registry, nltk's VERSION; `python tools/bundle.py` lists them. WordNet stays an optional download. |
| `tools/classify_obscene.py` | Sorts the rude words into kinds with Claude, meaning by meaning, with a confidence (OB-3; developers only, not part of the program): `estimate`, `try`, `run`, `status`; writes `word_categories.tsv` next to the save. |
| `tools/build.py` | Builds the program for this system with PyInstaller (T-3): `python tools/build.py` (installs PyInstaller if missing; `--check` then runs the new program for a moment). Linux / Windows: one file, no console; macOS: an app bundle. Into `dist/`. |
| `tools/hooks/hook-nltk.py` | Replaces PyInstaller's nltk hook, which would pack the build machine's WordNet data into the program. |
| `tools/layout_trace.py` | Debugging: places words fast in a throwaway save and reports widgets that moved when they should not, one-frame spikes, and anything over the tier buttons (`--reduce-motion`, `--every`, `--zoom`, `--csv`). |

Layers, lowest first: `constants`, `obscene`, `problems`, `deps`, `keymap` -> `store` -> `wordsource` / `saves` / `definitions` -> `theme`,
`fonts`, `sizing`, `ui_style`, `ui_motion`, `smooth`, `widgets`, `errors`, `startup` -> `ui_chart`, `browser`, `filepicker`, `shortcuts`, `dealing` -> `app` -> `tierlist`. A file only imports from files
earlier in that list. Only the UI files import `tkinter`.

## Where to change things

- A rule about ranking, duels, undo or the queue: `store.py`.
- Colours: `theme.py`. Fonts and sizes: `fonts.py`. How widgets look: `ui_style.py`.
- What a key or button does, what appears on screen: `app.py` (`on_key`, `_key_target`, `next_tab` for Tab, `_show_place`, `_show_pair`).
- The menus (File / Edit / View / Settings): `App._menu_items` in `app.py`.
- The order words come in, which kinds, censoring: Settings > How words are dealt (`dealing.py`; the data in
  `Store.deal_settings` / `set_deal`, `Store.reshuffle`).
- Zoom: View > Zoom in / out / Actual size, or Ctrl + / Ctrl - / Ctrl 0 (`App.set_zoom` / `zoom_step`, saved;
  what fits the screen: `App._fit_window`). Browse has its own (`Browser.zoom_by`).
- Contents growing with a bigger window (UI-25): `App._grow_for` / `App._apply_grow` (`GROW_MAX`, `GROW_STEP`).
- Anything that must survive a restart: save it through a `Store` method (it commits).

## Tests

`sh tests/run_tests.sh` runs everything (`tests/_selftest*.py`), from any folder. Window tests need
tkinter and run headless under `xvfb-run` when there is no display. A single test runs on its own too:
`python tests/_selftest_ui.py`. Before handing work over: `python tools/check_release.py --tests`.

## How words are dealt

The first start asks three short questions (any time later: Settings > How words are dealt...):

- **Order:** "Most common first" (strictly by how common a word is) or "Mostly common, a little shuffled"
  (the default: its shape, spread and seed decide how much).
- **Which words:** nouns, verbs, adjectives, adverbs, other, obscene words, each a tick box with how many
  words it holds (point at one to see what it covers). Every kind starts ticked except "Obscene words" (for
  now: telling which words are obscene is still being worked on). Unticked ones are left out of the queue, never deleted; untick everything but "Obscene
  words" to sort only those.
- **Censor obscene words** ("blurred, except on hover"): they are smeared sideways on the cards until the pointer is over them, and read
  b•••••d in messages and Browse. Exports keep the real words.

A word is flagged as obscene if most of its meanings, or its first, are labelled vulgar, offensive, derogatory or
a slur on Wiktionary, and its plural and other forms follow it.
Going through the flagged words by hand decides: `python tierlist.py --review-obscene` adds a "Review obscene
words" tab (developers; it is not shown otherwise) with each flagged word, commonest first, its definitions, and
Not obscene / Obscene / Swear word (keys 1, 2, 3; Backspace goes back one), a percentage bar, and "Save answers to
a file" (`obscene_review.txt` next to the save). Your answers are kept in the save and always win.
With Censor obscene words on, a meaning Wiktionary labels vulgar, offensive, derogatory or a slur is also smeared
inside the definitions (the drawer and Browse's pane), un-smearing while the pointer is over it. A save from before this learns each word's kinds from its stored definitions,
and reads the meanings of the words Wiktionary files as rude from Wiktionary once (on a start with the
internet; until then a short list chosen by hand in `src/obscene.py` stands in).

For developers, `tools/classify_obscene.py` sorts the rude words into kinds with Claude (clean, double meaning,
clinical, crude, swear word, sexual, insult, slur), judging each meaning, with a confidence for each word; the
ones it is unsure of are for checking by hand. `estimate` shows which words would go and about what it costs,
`try word ...` answers a few words at once, `run` sends them all through the Message Batches API (it asks first,
and picks up where it was if stopped) and writes `word_categories.tsv` next to the save. It needs `pip install
anthropic` and an Anthropic API key, and only reads the save.

## Building a program

`python tools/build.py` turns the source into a program for the system it runs on (`dist/word-tierlist` on
Linux, `dist/word-tierlist.exe` on Windows, `dist/Word Tier List.app` on macOS; about 22 MB). It installs
PyInstaller first if it is missing. Add `--check` to start the new program for a moment afterwards. The program
keeps its save next to itself (or in your user data folder when that folder is read-only) and finds the save you
used from source, so switching loses nothing. PyInstaller cannot build for another system: build on each one
(or see the roadmap's T-8 for building on GitHub).

## Windows notes

- Run with `python tierlist.py` (or `pythonw tierlist.py`). The black console window is closed
  automatically once the program starts, so closing it can no longer end the app. Messages that
  would have been printed there go to `tierlist.log` next to your save file. If you want the console
  back for troubleshooting, run `python tierlist.py --console`.
- If something goes wrong, a dialog explains it in plain words (with Show details / Copy details) and the technical trace is added to `tierlist.log`. Your progress is saved after every action, so the program keeps running after most errors.

To see the friendly error dialog on purpose, start with `python tierlist.py --crash-test`: three
seconds after start it raises a fake bug. The dialog appears and the program keeps running.

## Running it on Linux / macOS

- Started from a terminal, the program opens its window and gives the terminal its prompt back: you can
  close the terminal, and the program keeps running. Its messages go to `tierlist.log` next to your save
  (`--console` keeps the terminal attached and prints there). If the window cannot open (no desktop), it
  stays in the terminal and says why.
- File > Add to applications menu (Linux) puts Word Tier List in your desktop's applications menu, so it
  starts with no terminal at all. Anything that must be installed is then asked in the window.

## Missing packages
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

It only asks when something is missing. Started without a terminal (pythonw, a shortcut), only the
window stage runs. `--no-install` turns all of it off.
