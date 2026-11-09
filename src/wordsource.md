# `src/wordsource.py`

Where the words come from and getting them ready: the WordNet list, the Wiktionary download and parse (resumable), compound detection, word frequencies, kinds of words, marking the obscene words (from the list, OB-14), and the queue order.

- **Uses:** `constants`, `obscene`, `problems`
- **Used by:** `launch`, `tierlist`
- **Tests:** `_selftest`, `_selftest_errors`, `_selftest_obscene`, `_selftest_startup`

The module docstring has the details; this page is the map.

## Public API

- `build_word_list`: Return dictionary words, most common first.
- `download_resumable`: Download `url` to `dest`, resuming a partial `.part` file after interruptions.
- `build_wiktionary`: Load every English Wiktionary word into `store`, most common first.
- `compute_penalties`: Flag compounds so they are demoted in the queue (pen: 1 = closed compound, 2 = hyphenated).
- `frequency`: wordfreq's frequency of `w` (`fd`: its get_frequency_dict("en")): hyphenated / spaced forms, which that dictionary lacks, are estimated by wordfreq; any other word it...
- `fill_frequencies`: Store each word's wordfreq frequency (for the progress bar's coverage tag, UI-14).
- `fill_kinds`: Each word's kinds from its stored definition (every source writes "(noun) ..." lines: the Wiktionary build's, WordNet's, dictionaryapi.dev's), else from WordNet...
- `wiktionary_steps`: The main steps build_wiktionary will report, for the progress window's "Step 2 of 5" (plan_line).
- `queue_steps`: The main steps prepare_queue will report (see wiktionary_steps).
- `hyphens_left`: True while a save made before W-3 may still hold hyphenated words to leave out (Store.leave_out_hyphenated): once per save, never for a list of the user's own (--words).
- `prepare_queue`: Make sure every unplaced word has a queue position.

## Rules and pitfalls (fixed before: keep them fixed)

- Every stage is resumable and never touches existing progress.
- Keep `wiktionary_steps` / `queue_steps` in step with the stage lines they predict (the "Step i of n" corner).
- A word is one part (`_WORD_RE`: letters, apostrophes allowed): hyphenated entries and phrases are never read (W-3, asked for: wordfreq scores "what-have-you" like the phrase, so they crowded the front). An older save loses its untouched ones once (`hyphens_left`, meta `hyphens_done`); a `--words` list of the user's own is never touched.
- A Wiktionary build stores the frequencies it ranked by (`frequency`, the same as fill_frequencies) and the kinds, inside one `bulk_write`; `queue_steps(by_wiktionary=True)` then predicts neither step.

## Changing it

- A new preparation step: `prepare_queue`, its step name in `queue_steps`, and a check in `tests/_selftest_queue.py`.
