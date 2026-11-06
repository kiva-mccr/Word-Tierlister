# `tools/tune_rudeness.py`

Tunes the numbers the rudeness rules already have (OB-10; a developer tool) against the answers of the review by hand (OB-9), in a window: the error round by round on words held back, each kind before and after, the numbers changed, a guard over every word the program scores, the meanings still wrong; Keep writes the numbers into `src/rudeness.py`. Rules only stays: the program never reads the answers.

- **Uses:** `constants`, `errors`, `fonts`, `measure_rudeness`, `obscene`, `review`, `rudeness`, `startup`, `theme`, `ui_motion`, `ui_style`, `widgets`
- **Used by:** nothing (run directly)
- **Tests:** `_selftest_devtools`, `_selftest_tune`

The module docstring has the details; this page is the map.

## Public API

- `params`: Every number tuned (see SCALARS etc.), as names: "MEANING_MIN", "TAG_POINTS vulgar swear", "TOPIC_POINTS * clinical".
- `snapshot`: The rules' numbers now: {param: value} (a factor is 1.0) and the tables they scale (copied).
- `apply`: Put `values` into the rules (rudeness's globals and tables, changed in place).
- `bounds`: The range a number may move in.
- `fast`: Score fast inside: rudeness's patterns remember their answers, a definition's words are worked out once, and WordNet is read from `wn_matches` ({(word, gloss, pos):...
- `wordnet_tables`: (wn_matches, wn_names) for fast(): each meaning's WordNet match, and what each matched meaning is; progress(share of the words done) now and then.
- `scope`: The words the two passes read for `targets` (measure_rudeness.scope, plus the words they are forms of and the parts of hyphenated ones).
- `score_targets`: {word: [{kind: points}]} for `targets` (both passes), from `data`'s words.
- `answer_pairs`: {word: ([(meaning index, kind answered)], whole answered)} for the answers whose meanings are found.
- `part_of`: Which of the PARTS a word is tested in (fixed: by its letters).
- `tally`: {class: [tp, fp, fn]} over `words_in`: each kind meaning by meaning, and "whole" (smearing the word).
- `error`: 100% minus the average F1 of the classes answered at least once (tally).
- `evaluate`: The error and tally of `values` over `words_in`.
- `say`: A line for whoever started the tuner (the program's Tune the rules bubble reads them for its ring).
- `cost`: The pull towards today's numbers, in error points: PULL for each number moved its own size.
- `tune_round`: One round of the search over `train`: every number a step up and down (in `order`), a change kept when it lowers the error plus the pull towards today's numbers...
- `lower_priority`: This process yields to the window (and to the rest of the computer): the tuner's helper processes call it.
- `Inline`: A stand-in for ProcessPoolExecutor that runs each job at once, in this process (tests; --workers 0).
  - methods: submit, shutdown
- `pool`: Where the parts are tuned: `workers` processes, or this one (0); each number tried is put on `progress` (a multiprocessing queue for processes).
- `read_compact`: {word: [compact sense]} from the compact entries (measure_rudeness fetch); progress(share read) now and then.
- `program_words`: {word: compact senses as JSON text}: the words the program keeps and scores (wordsource.RudeCollector: any sign of rudeness, or only a form of such a word).
- `prepare`: (data for the tuning, the program's words for the guard) from the compact entries and the answers; progress(step, share done or None) for the window's bar.
- `guard`: {"whole": words smeared whole, kind: words with a meaning of that kind}: what the program would show with `values` (rudeness.score_saved over its words).
- `write_back`: Write `values` into rudeness.py at `path` (each number where it stands, comments kept) and bump RUDENESS_VERSION; the file is read back to check every number landed.
- `check`: Run the new rudeness.py's text on its own and check each number reads as `values` say (to 2 decimals).
- `misses`: [(word, gloss, answered, the rules' kind)] of the tested meanings `scored` still gets wrong, commonest first.
- `write_misses`: The misses as text: one meaning a line, the word, your kind, the rules' kind, its definition.
- `changed`: [(param, from, to)] of the numbers that moved (factors shown as their effect: "TOPIC_POINTS * clinical").
- `read_history`: The earlier tunes, oldest first: [{"when", "words", "meanings", "start", "best", "round", "kept"}].
- `write_history`: (no docstring)
- `read_answers`: The answers file's {word: {"kinds": {meaning key: kind}, "whole": bool}} (measure_rudeness.read_answers).
- `Tuning`: The search: every part's rounds in the processes, one round at a time; events go to `events` (a queue) as ("sweep", {round, errors: {part: (train error, test error)},...
  - methods: run, pause, resume, stop
- `noise`: The average's noise: the standard error of the parts' tested errors (points; none from one part).
- `best_round`: The round Keep takes (asked for): the earliest whose average is within the noise of the lowest (a win smaller than the noise is likely luck, and an earlier round has...
- `patience`: Rounds without a real gain before the search stops: longer the noisier the average (asked for).
- `tested_parts`: The parts that hold at least one answered word (in order): only these are tested and averaged.
- `precision_recall`: {class: (precision, recall) in %} from a tally.
- `doubled`: The guard's names that cover more than DOUBLED times the words they do now (from none: any).
- `TuneWindow`: The window (the mock-up agreed): the error round by round, each kind before and after, the numbers changed, the guard, the meanings still wrong; Pause, Discard, Keep...
  - methods: chart_size, show_bar, round_share, start, handle, sweep, listen, close_box, show_again, check_best, draw, span, draw_note, show_tab, current, remember, draw_past, draw_kinds, draw_changes, draw_guard, draw_misses, pause, keep, discard, close
- `pool_for_guard`: The guard's process (or this one: 0).
- `main`: The command line: the window (it reads the entries and starts the search itself).
- `load`: Read the entries in a process of its own (reading them in the window's process froze it for seconds at a time); its progress and its result come back as the window's...

## Rules and pitfalls (fixed before: keep them fixed)

- Started from the program (--from-program), the close box only hides the window while it tunes (`close_box`); `listen` turns stdin's "show" lines into events and its end into "gone" (a hidden tuner then stops). `close` cancels the pending `_poll`: one firing after the window was destroyed printed Tcl errors.
- Never test a word on numbers tuned with it: the 5 parts (`part_of`, fixed by the word's letters) each tune on the other 4; Keep takes the run on every word at the round the tests liked best.
- Every helper process is spawned (`_spawning`), never forked: started by the program (--from-program), the stdin listener thread holds sys.stdin's lock, and a forked child's start-up closes sys.stdin, so the tuning processes hung before round 0 ended (reported).
- The chart's margins are measured from the small font (the axis name, the widest number, the legend's rows): fixed margins overlapped at the user's text size (reported).
- Never read the entries in the window's process (`load` starts a spawned process: reading 3 GB of JSON beside Tk froze the window for up to 2.5 s at a time, longer as the heap grew). The helper processes call `lower_priority`; `Inline` (tests, --workers 0) runs in the window's process and must not.
- The chart is drawn at the canvas's real size (`draw` reads winfo_width / height) and again 60 ms after a resize pauses; its legend is one line under the plot. Stop the moving bar (`_still`) before the window is destroyed, or Tk's progressbar timer complains.
- A few answers leave some parts with no words: only `tested_parts` are run, averaged and summed (averaging every part once added a missing test error, a TypeError under the graph).
- `fast()` must give exactly the rules' own scores (the self-test compares it with `rudeness.score_words` under odd numbers): what it remembers never depends on the numbers, a meaning that scores nothing scores nothing whatever they are, and a meaning's points are remembered for the values of the numbers it was seen to hang on. A new number or table in rudeness.py: add it to PARAMS (`params`, `apply`, `write_back`, `check`) or it stays as it is.
- `rudeness._signals` keeps WordNet's points once worked out: inside `fast()` they are read from the table each time (a tuned WORDNET_POINTS was ignored otherwise).
- The error moves in jumps (a small step often changes no meaning's kind): a step that helps neither way is tried JUMP times as far before it halves.
- Keep writes each number where it stands (comments kept) and runs the new file's text to check every number landed, then bumps RUDENESS_VERSION; read the diff before committing.
- The tuning processes never load WordNet (its matches are worked out first, `wordnet_tables`); the guard's process does, once.
- The window is one size from the start (asked for): every row is built empty in `_build_slots` and only filled in place (`draw_kinds`, `draw_changes`, `draw_guard`, `draw_misses` set text, never add or remove widgets), the info and note keep two lines, and the window's size is set once. A round's results come as one "sweep" event and show together; the guard's first count is held for round 0's sweep.
- The chart gets the height the rest leaves on the screen (`CHART_MIN` at least): reported squished on a 1200 px screen when the empty rows were stacked; kinds, numbers changed and the guard sit side by side, the Keep note on the button row. Every fixed-size label keeps a width (and lines) of its own: a wrapping label with only a wraplength grew wider than its slot and was cut. The rounds axis shows the rounds run plus those it may still wait (`span`), and the % numbers thin out on a short chart.
- Each change pays a pull towards today's numbers (`cost`, PULL): tried on 600 stand-in answers it reached a lower tested error with 3 numbers moved instead of 11. Random kicks after settling were tried and found nothing better in 2.5 times the time (not built). `tune_round` returns the error without the pull: the chart shows plain error.
- Earlier tunes: one line per finished tune in `rude_tune_history.jsonl` beside the answers (`remember` on done, Keep rewrites it kept); the program's review window reads the same file (its keys: when, words, meanings, start, best, round, kept; error %, not agreement).
- The details sit under tabs (asked for: "crowded"; approved from a mock-up): Earlier tunes, Each kind, Numbers changed, Guard, Still wrong, all gridded in one cell (`panels`) so the page is always as tall as the tallest, raised with `tk.Misc.tkraise` (a Canvas's own tkraise raises its items). Numbers changed and Still wrong list everything in a read-only Text (`_list`, LIST_LINES) whose scroll bar shows only while the lines do not all fit (asked for); its column keeps the bar's width.
- The stop allows for noise (asked for): a gain counts only when it beats the last real gain by more than the parts' standard error (`noise`), the wait grows with it (`patience`), and Keep's round is the earliest within the noise of the lowest (`best_round`, picked by the user); its misses come from that round's numbers, not the latest.

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
