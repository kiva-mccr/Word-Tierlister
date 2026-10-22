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

## Folders

```
tierlist.py        run this. Your save (tierlist.db), its log and exports stay next to it.
requirements.txt   the Python packages (the program offers to install them itself)
src/               the program's modules
tests/             the self-tests and run_tests.sh
tools/             check_release.py (pre-hand-off checks, builds the zip), layout_trace.py (layout jitter finder),
                   bundle.py (the data a built program carries), build.py + hooks/ (build it as a program),
                   measure_rudeness.py (measures the rudeness rules)
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
| `src/obscene.py` | The kinds of rude meaning (Clinical, Crude, Swear word, Insult, Sexual, Slur), which start ticked and which are censored; Wiktionary's rude labels; a short list chosen by hand (the stand-in until a save has Wiktionary's meanings, and for a word added by hand). No tkinter, no internet. |
| `src/rudeness.py` | How rude each meaning is, by rules, no word list (OB-6): points towards each kind (Clinical, Crude, Swear word, Insult, Sexual, Slur) from Wiktionary's labels, its topics and categories, the definition's wording, the word itself and, when nltk's WordNet is installed, the matching WordNet meaning's place in its tree and its usage labels; a second pass over Wiktionary's synonym lists says which kind a slang meaning is; a meaning's kind; the word's points, its first meaning counting most (enough of them: the whole word smeared); word families (a word built from a rude one: its etymology, or that word's derived terms) add a little; what a word's scores lead to (`score_saved`: the kinds of its meanings, smeared whole, the meanings smeared); how the program keeps meanings compactly (`compact_entry`, `expand`, `has_signal`). No tkinter, no internet. |
| `src/keymap.py` | The keyboard shortcuts (UI-48): every action with a key, its view and default keys, your changes on top (saved in the save); key presses to key names. No tkinter. |
| `src/store.py` | `Store`: the SQLite save. Tiers, anchors (they follow their tier), Elo duels, undo, queue order, which words are dealt (kinds of word and of rude meaning, the ones left out; ST-6, OB-5), the meanings the rudeness rules read and what they found (OB-6), conflicts, boundary swaps, the progress shelf's tallies, merging. |
| `src/wordsource.py` | Building the word list (WordNet, Wiktionary; each word's parts of speech), compound detection, word frequencies (for the coverage tag), kinds for an older save (from its definitions), the meanings the rudeness rules read (`RudeCollector`, kept at the Wiktionary build; `fetch_rude_senses` for an older save, in the background) and scoring them (`find_rude`), queue prep. |
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
| `src/dealing.py` | Settings > How words are dealt... (ST-6): the order (Most common first, or a little shuffled with its shape, spread, seed), which kinds of words (a tick box each, with counts; obscene words too, with a tick box per kind of rude meaning under it, OB-5) and Censor obscene words; on the first start the same in three steps. |
| `src/shortcuts.py` | Settings > Keyboard shortcuts...: change any key (click it, press the new one), add or remove keys, swap on a clash; the 1-6 placing keys move as a set. |
| `src/filepicker.py` | Import / Export file choosing on Linux (UI-42): what it found first (other saves, exports), a themed folder browser behind it; Windows and macOS keep their own dialogs. |
| `src/browser.py` | The Browse / edit window: search, Show (a tier, unplaced words, or the placed words of a kind) / Sort (or click a column heading; again to turn it round; its arrow fills as the rows load), rows in soft tier colours (a censored word reads b•••••d), Move to, Unplace (or the Delete key; Ctrl+Z undoes), definition; it opens complete and in its place, like the other windows, and remembers what it showed. |
| `src/app.py` | The main window and all four modes. |
| `tools/check_release.py` | Pre-hand-off checks (packages vs requirements, docs, tests listed, files in the right folder); `--tests`, `--zip`. See `.claude/CHECKLIST.md`. |
| `tools/bundle.py` | What a built program carries besides its code (T-2): wordfreq's English word lists only (1.6 of its 60 MB), langcodes' registry, nltk's VERSION; `python tools/bundle.py` lists them. WordNet stays an optional download. |
| `tools/measure_rudeness.py` | Measures `src/rudeness.py`'s rules against an earlier sorting by Claude (OB-6; developers): `fetch` keeps every lower-case English entry of the Wiktionary download compactly (with its word family: the words its etymology names, its derived terms), `measure` says how often both lead to the same thing, per censoring policy, with or without each source (`--no-links`, `--no-wordnet`, `--no-families`). |
| `tools/build.py` | Builds the program for this system with PyInstaller (T-3): `python tools/build.py` (installs PyInstaller if missing; `--check` then runs the new program for a moment). Linux / Windows: one file, no console; macOS: an app bundle. Into `dist/`. |
| `tools/hooks/hook-nltk.py` | Replaces PyInstaller's nltk hook, which would pack the build machine's WordNet data into the program. |
| `tools/layout_trace.py` | Debugging: places words fast in a throwaway save and reports widgets that moved when they should not, one-frame spikes, and anything over the tier buttons (`--reduce-motion`, `--every`, `--zoom`, `--csv`). |

Layers, lowest first: `constants`, `obscene`, `rudeness`, `problems`, `deps`, `keymap` -> `store` -> `wordsource` / `saves` / `definitions` -> `theme`,
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
- **Which words:** nouns, verbs, adjectives, adverbs, obscene words, other, each a tick box with how many
  words it holds (point at one to see what it covers). Every kind starts ticked except "Obscene words".
  Ticking it opens a tick box per kind of rude meaning: Clinical, Crude, Swear words and Insults start ticked,
  Sexual and Slurs do not ("Obscene words" shows a minus while only some are). A word comes up if one of its
  meanings is of a ticked rude kind, or it has a clean meaning and its kind of word is ticked; a word whose
  meanings are all rude of unticked kinds is left out.
  Unticked ones are left out of the queue, never deleted; untick every kind of word but "Obscene words" to
  sort only those.
- **Censor obscene words** ("blurred, except on hover"): a word is smeared sideways on the cards until the pointer
  is over it, and reads b•••••d in messages and Browse, when its first (most common) meaning is rude enough;
  inside the definitions (the drawer and Browse's pane) each rude meaning is smeared, un-smearing under the
  pointer. Only Crude, Swear word, Sexual and Slur meanings are smeared, never Clinical or Insult. Exports keep
  the real words.

What is rude is decided by rules, not a list (`src/rudeness.py`, OB-6): every meaning earns points towards the
six kinds from Wiktionary's labels, its topics and categories, the wording of the definition, WordNet when it is
installed, the links between words (Wiktionary's synonym lists) and word families ("bullshit" is built from
"shit"); its kind is the one with
the most points, if it has enough. A word's points come mostly from its first meaning: enough of them and the whole
word is smeared, otherwise only its rude meanings are. A plural or other form goes with its word's first meaning
("did" is "do", not its slang meaning), and a Clinical meaning only counts when the word is about it ("penis",
not "take"). A very common word (about the 3,000 commonest, by wordfreq) is rarely meant rudely: only meanings
Wiktionary labels plainly rude count for it ("box: (vulgar) the vagina", not "top: (slang) fellatio").
The Wiktionary build keeps the meanings the rules read (about 150,000 words of a million, in the save's `rude`
table) and scores them once at the end of setting up (about a minute; again only when the rules change).
A save from before this, or one made from a word list, reads them from the Wiktionary download in the background
while you sort (once, resumable; until then its earlier flags and a short list chosen by hand in
`src/obscene.py` stand in). `tools/measure_rudeness.py` measures the rules against an earlier sorting by Claude
(78% the same outcome, 80% for the commonest words). That earlier way, Claude sorting the words and a review tab
to check them, is archived (see the roadmap's OB-3 / OB-4).

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
