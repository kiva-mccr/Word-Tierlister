# `src/definitions.py`

Definitions: offline WordNet, the online dictionaryapi.dev fallback, splitting stored text into senses, and finding the word a meaning only names ("Alternative spelling of jail": `form_target`, F-3).

- **Uses:** `constants`
- **Used by:** `app`, `speed_check`, `tierlist`, `widgets`
- **Tests:** `_selftest`, `_selftest_lookup`, `_selftest_tabswitch`, `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `wiktionary_url`: The English section of `word`'s Wiktionary page.
- `Online`: Whether Wiktionary can be reached, checked on a worker thread now and every EVERY seconds (never from the window: it only reads `online`).
  - methods: start, stop
- `parse_definition`: Split stored definition text into senses for display (UI-12): [{"num": "1", "pos": "noun", "text": "...", "example": "..." or None, "labels": [...], "gloss": "..."},...
- `form_target`: The word a meaning only names ("Alternative form of bull dyke." -> "bull dyke"), or None.
- `main_sense`: A definition's first sense that is not itself only a form of another word (parse_definition), or None.
- `Definitions`: Threaded definition lookup.
  - methods: request, drain

## Rules and pitfalls (fixed before: keep them fixed)

- Lookups run on one worker thread; the UI polls `drain()`. The worker never touches tkinter.
- Never goes online with `OFFLINE_ENV` set (the tests set it).
- WordNet is read in at the first word not cached, not at start (reading it competed with building the main window: 5.5 s instead of 1.3 s on a big save).

## Changing it

- Text formats it understands: `parse_definition` (WordNet's numbered lines and the Wiktionary build's bullets).
- `Online` (UI-67) only ever runs on a worker thread and never with WORD_TIERLIST_OFFLINE; the window just reads `online`.
