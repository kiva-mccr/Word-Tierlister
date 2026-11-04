# `tools/tune_rudeness.py`

Tunes the numbers the rudeness rules already have (OB-10; a developer tool) against the answers of the review by hand (OB-9), in a window: the error round by round on words held back, each kind before and after, the numbers changed, a guard over every word the program scores, the meanings still wrong; Keep writes the numbers into `src/rudeness.py`. Rules only stays: the program never reads the answers.

- **Uses:** `constants`, `errors`, `fonts`, `measure_rudeness`, `obscene`, `review`, `rudeness`, `theme`, `ui_motion`, `ui_style`, `widgets`
- **Used by:** nothing (run directly)
- **Tests:** `_selftest_tune`

The module docstring has the details; this page is the map.

## Public API

- `params`: Every number tuned (see SCALARS etc.), as names: "MEANING_MIN", "TAG_POINTS vulgar swear", "TOPIC_POINTS * clinical".
- `snapshot`: The rules' numbers now: {param: value} (a factor is 1.0) and the tables they scale (copied).
- `apply`: Put `values` into the rules (rudeness's globals and tables, changed in place).
- `bounds`: The range a number may move in.
- `fast`: Score fast inside: rudeness's patterns remember their answers, a definition's words are worked out once, and WordNet is read from `wn_matches` ({(word, gloss, pos):...
- `wordnet_tables`: (wn_matches, wn_names) for fast(): each meaning's WordNet match, and what each matched meaning is.
- `scope`: The words the two passes read for `targets` (measure_rudeness.scope, plus the words they are forms of and the parts of hyphenated ones).
- `score_targets`: {word: [{kind: points}]} for `targets` (both passes), from `data`'s words.
- `answer_pairs`: {word: ([(meaning index, kind answered)], whole answered)} for the answers whose meanings are found.
- `part_of`: Which of the PARTS a word is tested in (fixed: by its letters).
- `tally`: {class: [tp, fp, fn]} over `words_in`: each kind meaning by meaning, and "whole" (smearing the word).
- `error`: 100% minus the average F1 of the classes answered at least once (tally).
- `evaluate`: The error and tally of `values` over `words_in`.
- `tune_round`: One round of the search over `train`: every number a step up and down (in `order`), a change kept when it lowers the error, a step that helps neither way halved.
- `Inline`: A stand-in for ProcessPoolExecutor that runs each job at once, in this process (tests; --workers 0).
  - methods: submit, shutdown
- `pool`: Where the parts are tuned: `workers` processes, or this one (0).
- `read_compact`: {word: [compact sense]} from the compact entries (measure_rudeness fetch).
- `program_words`: {word: compact senses as JSON text}: the words the program keeps and scores (wordsource.RudeCollector: any sign of rudeness, or only a form of such a word).
- `prepare`: (data for the tuning, the program's words for the guard) from the compact entries and the answers.
- `guard`: {"whole": words smeared whole, kind: words with a meaning of that kind}: what the program would show with `values` (rudeness.score_saved over its words).
- `write_back`: Write `values` into rudeness.py at `path` (each number where it stands, comments kept) and bump RUDENESS_VERSION; the file is read back to check every number landed.
- `check`: Run the new rudeness.py's text on its own and check each number reads as `values` say (to 2 decimals).
- `misses`: [(word, gloss, answered, the rules' kind)] of the tested meanings `scored` still gets wrong, commonest first.
- `write_misses`: The misses as text: one meaning a line, the word, your kind, the rules' kind, its definition.
- `changed`: [(param, from, to)] of the numbers that moved (factors shown as their effect: "TOPIC_POINTS * clinical").
- `read_answers`: The answers file's {word: {"kinds": {meaning key: kind}, "whole": bool}} (measure_rudeness.read_answers).
- `Tuning`: The search: every part's rounds in the processes, one round at a time; events go to `events` (a queue) as ("round", n, {part: (train error, test error)}, average test...
  - methods: run, pause, resume, stop
- `precision_recall`: {class: (precision, recall) in %} from a tally.
- `doubled`: The guard's names that cover more than DOUBLED times the words they do now (from none: any).
- `TuneWindow`: The window (the mock-up agreed): the error round by round, each kind before and after, the numbers changed, the guard, the meanings still wrong; Pause, Discard, Keep...
  - methods: start, handle, check_best, draw, draw_note, draw_kinds, draw_changes, draw_guard, draw_misses, pause, keep, discard, close
- `pool_for_guard`: The guard's process (or this one: 0).
- `main`: The command line: the window (it reads the entries and starts the search itself).

## Rules and pitfalls (fixed before: keep them fixed)

- Never test a word on numbers tuned with it: the 5 parts (`part_of`, fixed by the word's letters) each tune on the other 4; Keep takes the run on every word at the round the tests liked best.
- `fast()` must give exactly the rules' own scores (the self-test compares it with `rudeness.score_words` under odd numbers): what it remembers never depends on the numbers, a meaning that scores nothing scores nothing whatever they are, and a meaning's points are remembered for the values of the numbers it was seen to hang on. A new number or table in rudeness.py: add it to PARAMS (`params`, `apply`, `write_back`, `check`) or it stays as it is.
- `rudeness._signals` keeps WordNet's points once worked out: inside `fast()` they are read from the table each time (a tuned WORDNET_POINTS was ignored otherwise).
- The error moves in jumps (a small step often changes no meaning's kind): a step that helps neither way is tried JUMP times as far before it halves.
- Keep writes each number where it stands (comments kept) and runs the new file's text to check every number landed, then bumps RUDENESS_VERSION; read the diff before committing.
- The tuning processes never load WordNet (its matches are worked out first, `wordnet_tables`); the guard's process does, once.

## Changing it

- Run: `python tools/tune_rudeness.py` (needs `rudeness_entries.jsonl` from `measure_rudeness.py fetch` and the review's answers); `--workers 0` runs everything in one process.

## Public API

- `params`: Every number tuned (see SCALARS etc.), as names: "MEANING_MIN", "TAG_POINTS vulgar swear", "TOPIC_POINTS * clinical".
- `snapshot`: The rules' numbers now: {param: value} (a factor is 1.0) and the tables they scale (copied).
- `apply`: Put `values` into the rules (rudeness's globals and tables, changed in place).
- `bounds`: The range a number may move in.
- `fast`: Score fast inside: rudeness's patterns remember their answers, a definition's words are worked out once, and WordNet is read from `wn_matches` ({(word, gloss, pos):...
- `wordnet_tables`: (wn_matches, wn_names) for fast(): each meaning's WordNet match, and what each matched meaning is.
- `scope`: The words the two passes read for `targets` (measure_rudeness.scope, plus the words they are forms of and the parts of hyphenated ones).
- `score_targets`: {word: [{kind: points}]} for `targets` (both passes), from `data`'s words.
- `answer_pairs`: {word: ([(meaning index, kind answered)], whole answered)} for the answers whose meanings are found.
- `part_of`: Which of the PARTS a word is tested in (fixed: by its letters).
- `tally`: {class: [tp, fp, fn]} over `words_in`: each kind meaning by meaning, and "whole" (smearing the word).
- `error`: 100% minus the average F1 of the classes answered at least once (tally).
- `evaluate`: The error and tally of `values` over `words_in`.
- `tune_round`: One round of the search over `train`: every number a step up and down (in `order`), a change kept when it lowers the error, a step that helps neither way halved.
- `Inline`: A stand-in for ProcessPoolExecutor that runs each job at once, in this process (tests; --workers 0).
  - methods: submit, shutdown
- `pool`: Where the parts are tuned: `workers` processes, or this one (0).
- `read_compact`: {word: [compact sense]} from the compact entries (measure_rudeness fetch).
- `program_words`: {word: compact senses as JSON text}: the words the program keeps and scores (wordsource.RudeCollector: any sign of rudeness, or only a form of such a word).
- `prepare`: (data for the tuning, the program's words for the guard) from the compact entries and the answers.
- `guard`: {"whole": words smeared whole, kind: words with a meaning of that kind}: what the program would show with `values` (rudeness.score_saved over its words).
- `write_back`: Write `values` into rudeness.py at `path` (each number where it stands, comments kept) and bump RUDENESS_VERSION; the file is read back to check every number landed.
- `check`: Run the new rudeness.py's text on its own and check each number reads as `values` say (to 2 decimals).
- `misses`: [(word, gloss, answered, the rules' kind)] of the tested meanings `scored` still gets wrong, commonest first.
- `write_misses`: The misses as text: one meaning a line, the word, your kind, the rules' kind, its definition.
- `changed`: [(param, from, to)] of the numbers that moved (factors shown as their effect: "TOPIC_POINTS * clinical").
- `read_answers`: The answers file's {word: {"kinds": {meaning key: kind}, "whole": bool}} (measure_rudeness.read_answers).
- `Tuning`: The search: every part's rounds in the processes, one round at a time; events go to `events` (a queue) as ("round", n, {part: (train error, test error)}, average test...
  - methods: run, pause, resume, stop
- `precision_recall`: {class: (precision, recall) in %} from a tally.
- `doubled`: The guard's names that cover more than DOUBLED times the words they do now (from none: any).
- `TuneWindow`: The window (the mock-up agreed): the error round by round, each kind before and after, the numbers changed, the guard, the meanings still wrong; Pause, Discard, Keep...
  - methods: start, handle, check_best, draw, draw_note, draw_kinds, draw_changes, draw_guard, draw_misses, pause, keep, discard, close
- `pool_for_guard`: The guard's process (or this one: 0).
- `main`: The command line: the window, or (no window) the search printed round by round.
