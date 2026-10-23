# `src/definitions.py`

Definitions: offline WordNet, the online dictionaryapi.dev fallback, splitting stored text into senses, and finding the word a meaning only names ("Alternative spelling of jail": `form_target`, F-3).

- **Uses:** `constants`
- **Used by:** `tierlist`, `widgets`
- **Tests:** `_selftest`, `_selftest_widgets2`

The module docstring has the details; this page is the map.

## Public API

- `parse_definition`: Split stored definition text into senses for display (UI-12): [{"num": "1", "pos": "noun", "text": "...", "example": "..." or None, "labels": [...], "gloss": "..."},...
- `form_target`: The word a meaning only names ("Alternative form of bull dyke." -> "bull dyke"), or None.
- `main_sense`: A definition's first sense that is not itself only a form of another word (parse_definition), or None.
- `Definitions`: Threaded definition lookup.
  - methods: request, drain

## Rules and pitfalls (fixed before: keep them fixed)

- Lookups run on one worker thread; the UI polls `drain()`. The worker never touches tkinter.
- Never goes online with `OFFLINE_ENV` set (the tests set it).

## Changing it

- Text formats it understands: `parse_definition` (WordNet's numbered lines and the Wiktionary build's bullets).
