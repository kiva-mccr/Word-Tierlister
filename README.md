# Word Tier List

Tier-list every English word (S / A / B / C / D / F). Progress autosaves to SQLite after every
action and resumes automatically, even if you replace these files.

    python tierlist.py                 # options: python tierlist.py --help

On the first start it asks in the terminal to install what it needs (see "Missing packages"), or
install them yourself first: `pip install -r requirements.txt`.

See the docstring at the top of `tierlist.py` for how it works and the full code map; the UI
redesign plan (UI-0 .. UI-26, ticked as built) is the comment block right under it.

## Files (keep them all in one folder; run `tierlist.py`)

| File | Job |
|---|---|
| `tierlist.py` | Entry point: command-line options, start-up sequence, `main()`. Also holds the roadmap. |
| `constants.py` | Tier names, modes, ranking defaults. No dependencies. |
| `store.py` | `Store`: the SQLite save. Tiers, Elo duels, undo, queue order, conflicts, merging. |
| `wordsource.py` | Building the word list (WordNet, Wiktionary), compound detection, queue prep. |
| `saves.py` | Finding / remembering your earlier save; export. |
| `definitions.py` | Background definition lookup (WordNet offline, dictionaryapi.dev online). |
| `theme.py` | Colour palette. |
| `fonts.py` | Typography: font family and named size roles. |
| `ui_style.py` | ttk / tk styling (applies the palette and fonts to every widget). |
| `check_release.py` | Pre-hand-off checks (packages vs requirements, docs, tests listed); `--tests`, `--zip`. See CHECKLIST.md. |
| `deps.py` | Required packages: finds missing ones and installs them; the terminal install stage (no tkinter). |
| `problems.py` | Plain-language error text (`describe`), `SetupError`, log helpers. No tkinter. |
| `errors.py` | Friendly error dialog, global error handlers, `run_guarded` (the whole program runs inside it). |
| `sizing.py` | Screen/dpi-aware window sizing: usable area (xrandr on X11), `fit_size`, centring, dialog placement. |
| `ui_motion.py` | Easing, colour blending and the `Animator` (animations run on the Tk event loop). |
| `startup.py` | First-run progress window: runs set-up on a worker thread and shows what it is doing. |
| `widgets.py` | `RoundButton` (rounded pastel buttons with hover, press and key hints), `WordCard` (the big word on its card), `TierRow` (the S..F pills), `DuelCards` (the two duel cards with Tie / Skip), `AnchorLadder` (the S..F strip while comparing), the header pieces (`SegmentedControl` mode switch, `HeaderMenus` + `DropMenu`) and other small widgets. |
| `browser.py` | The Browse / edit window. |
| `app.py` | The main window and all four modes. |

Layers, lowest first: `constants`, `problems`, `deps` -> `store` -> `wordsource` / `saves` / `definitions` -> `theme`,
`fonts`, `sizing`, `ui_style`, `errors`, `ui_motion`, `widgets`, `startup` -> `browser` -> `app` -> `tierlist`. A file only imports from files
earlier in that list. Only the UI files import `tkinter`.

## Where to change things

- A rule about ranking, duels, undo or the queue: `store.py`.
- Colours: `theme.py`. Fonts and sizes: `fonts.py`. How widgets look: `ui_style.py`.
- What a key or button does, what appears on screen: `app.py` (`on_key`, `_show_place`, `_show_pair`).
- The menus (File / Edit / View / Settings): `App._menu_items` in `app.py`.
- Anything that must survive a restart: save it through a `Store` method (it commits).

## Tests

`sh run_tests.sh` runs everything (`_selftest*.py`). Window tests need tkinter and run headless
under `xvfb-run` when there is no display.

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

1. **In the terminal, before any window.** Only what the program cannot start without: `tkinter` (the
   window toolkit) and `wordfreq`. It lists them, asks `Install them now? [Y/n]` (Enter = yes), installs
   tkinter with your system's package manager (apt-get, dnf, pacman, zypper, or Homebrew on macOS; sudo
   may ask for your password) and wordfreq with pip, then says "Opening the window..." and the window
   opens (on Windows the console window closes). If your system Python refuses pip installs (Debian,
   Ubuntu, Homebrew), it offers to make a private `.venv` next to the program and uses it from then on.
2. **In the window.** Optional extras, today `nltk` (offline definitions, and the WordNet word list),
   are offered with "Install now / Not now". A "Not now" is remembered.

It only asks when something is missing. Started without a terminal (pythonw, a shortcut), the window
asks about everything instead. `--no-install` turns all of it off.
