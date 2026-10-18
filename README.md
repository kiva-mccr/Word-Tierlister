# Word Tier List

Tier-list every English word (S / A / B / C / D / F). Progress autosaves to SQLite after every
action and resumes automatically, even if you replace these files.

    python tierlist.py                 # options: python tierlist.py --help

On the first start it offers to install what it needs (see "Missing packages"), or install it yourself
first: `pip install -r requirements.txt`.

See the docstring at the top of `tierlist.py` for how it works and the full code map; the roadmap
(UI, start-up and packaging steps, ticked as built) is the comment block right under it.

## Folders

```
tierlist.py        run this. Your save (tierlist.db), its log and exports stay next to it.
requirements.txt   the Python packages (the program offers to install them itself)
src/               the program's modules
tests/             the self-tests and run_tests.sh
tools/             check_release.py (pre-hand-off checks, builds the zip)
.claude/           notes for Claude Code: CLAUDE.md (project notes) and CHECKLIST.md
```

`tierlist.py` stays at the top on purpose: the save is found "next to the script", so moving or
replacing the other folders never loses your list.

## Files

| File | Job |
|---|---|
| `tierlist.py` | Entry point: command-line options, start-up sequence, `main()`. Also holds the roadmap. |
| `src/constants.py` | Tier names, modes, ranking defaults. No dependencies. |
| `src/store.py` | `Store`: the SQLite save. Tiers, anchors (they follow their tier), Elo duels, undo, queue order, conflicts, boundary swaps, progress tallies, merging. |
| `src/wordsource.py` | Building the word list (WordNet, Wiktionary), compound detection, word frequencies (for the coverage tag), queue prep. |
| `src/saves.py` | Finding / remembering your earlier save; export. |
| `src/definitions.py` | Background definition lookup (WordNet offline, dictionaryapi.dev online); splitting it into senses. |
| `src/theme.py` | Colour palette, tier colours (and the softer Browse row tints). |
| `src/fonts.py` | Typography: font family and named size roles. |
| `src/ui_style.py` | ttk / tk styling (applies the palette and fonts to every widget; draws the tick boxes). |
| `src/deps.py` | Packages: finds missing ones and installs them; the terminal stage, the private `.venv`; each package's size, purpose and web page (no tkinter). |
| `src/problems.py` | Plain-language error text (`describe`), `SetupError`, log helpers. No tkinter. |
| `src/errors.py` | Friendly error dialog, plain messages and question dialogs (all on `StyledDialog`; tick-box choices can link to a web page), global error handlers, `run_guarded` (the whole program runs inside it). |
| `src/sizing.py` | Screen/dpi-aware window sizing: usable area (xrandr on X11), `fit_size`, centring, dialog placement. |
| `src/ui_motion.py` | Easing, colour blending and the `Animator` (animations run on the Tk event loop). |
| `src/startup.py` | First-run progress window (set-up on a worker thread) and the window's package install step. |
| `src/widgets.py` | `Tooltip` (hover notes), `RoundButton` (rounded pastel buttons with hover, press and key hints), `WordCard` (the big word on its card), `TierRow` (the S..F pills), `TierChip` (a tier label drawn like a pill), `DuelCards` (the two duel cards with Tie / Skip), `AnchorLadder` (the S..F strip while comparing), the header pieces (`TabBar` mode tabs, which show only once they have work, `HeaderMenus` + `DropMenu`), `ChoiceButton` (drop-down choices), `Toast` (messages), `EmptyCard` (friendly "nothing to do" panels), `StyledDialog` (the shared dialog frame), `DefinitionDrawer` and other small widgets. |
| `src/ui_chart.py` | Each tab's own view at the top right: the tier chart (Place new words), `SettledChart` (Refine), `SwapStrip` (Boundary), `ConflictCard` (Conflicts); `SegmentBar`, the progress bar under the status line. |
| `src/browser.py` | The Browse / edit window: search, Show / Sort, rows in soft tier colours, Move to, definition. |
| `src/app.py` | The main window and all four modes. |
| `tools/check_release.py` | Pre-hand-off checks (packages vs requirements, docs, tests listed, files in the right folder); `--tests`, `--zip`. See `.claude/CHECKLIST.md`. |

Layers, lowest first: `constants`, `problems`, `deps` -> `store` -> `wordsource` / `saves` / `definitions` -> `theme`,
`fonts`, `sizing`, `ui_style`, `ui_motion`, `widgets`, `errors`, `startup` -> `ui_chart`, `browser` -> `app` -> `tierlist`. A file only imports from files
earlier in that list. Only the UI files import `tkinter`.

## Where to change things

- A rule about ranking, duels, undo or the queue: `store.py`.
- Colours: `theme.py`. Fonts and sizes: `fonts.py`. How widgets look: `ui_style.py`.
- What a key or button does, what appears on screen: `app.py` (`on_key`, `_key_target`, `next_tab` for Tab, `_show_place`, `_show_pair`).
- The menus (File / Edit / View / Settings): `App._menu_items` in `app.py`.
- Zoom: View > Zoom in / out / Actual size, or Ctrl + / Ctrl - / Ctrl 0 (`App.set_zoom` / `zoom_step`, saved;
  what fits the screen: `App._fit_window`). Browse has its own (`Browser.zoom_by`).
- Contents growing with a bigger window (UI-25): `App._grow_for` / `App._apply_grow` (`GROW_MAX`, `GROW_STEP`).
- Anything that must survive a restart: save it through a `Store` method (it commits).

## Tests

`sh tests/run_tests.sh` runs everything (`tests/_selftest*.py`), from any folder. Window tests need
tkinter and run headless under `xvfb-run` when there is no display. A single test runs on its own too:
`python tests/_selftest_ui.py`. Before handing work over: `python tools/check_release.py --tests`.

## Windows notes

- Run with `python tierlist.py` (or `pythonw tierlist.py`). The black console window is closed
  automatically once the program starts, so closing it can no longer end the app. Messages that
  would have been printed there go to `tierlist.log` next to your save file. If you want the console
  back for troubleshooting, run `python tierlist.py --console`.
- If something goes wrong, a dialog explains it in plain words (with Show details / Copy details) and the technical trace is added to `tierlist.log`. Your progress is saved after every action, so the program keeps running after most errors.

To see the friendly error dialog on purpose, start with `python tierlist.py --crash-test`: three
seconds after start it raises a fake bug. The dialog appears and the program keeps running.

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
