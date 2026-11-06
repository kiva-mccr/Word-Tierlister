# `src/launch.py`

Start-up's stages: `stages` decides which stages this start needs (a word list from a file, the Wiktionary build or upgrade, WordNet's list, the queue, a `--seed` reshuffle) and returns each as its step names with its work; `set_up` logs the plan line ("Step i of n") from those names, then runs the work. main() in tierlist.py calls it on the progress window's worker thread.

- **Uses:** `constants`, `problems`, `wordsource`
- **Used by:** `tierlist`
- **Tests:** `_selftest_launch`

The module docstring has the details; this page is the map.

## Public API

- `builds_wiktionary`: True when this start builds (or upgrades to) the full Wiktionary list: no --wordlist, not a custom list, Wiktionary asked for and not built yet.
- `stages`: The stages this start needs, in order: [(step names for the plan line, work(log))].
- `set_up`: Get the save ready: log the plan (every stage's step names), then run each stage.

## Rules and pitfalls (fixed before: keep them fixed)

- A stage's names and its work stay together in `stages`: never work out the plan in one place and run it in another (main() used to walk the same if / elif chain twice).
- The names are worked out before any work runs (queue_steps must see the save as it is before words are added), and the `--seed` reshuffle checks the seed again when it runs (the queue's own shuffle comes first).
- A custom list (`--wordlist`, meta source "custom") is never replaced. No tkinter here: it runs on a worker thread.
