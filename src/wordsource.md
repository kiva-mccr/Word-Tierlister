# `src/wordsource.py`

Where the words come from and getting them ready: the WordNet list, the Wiktionary download and parse (resumable), compound detection, word frequencies, kinds of words, the rude meanings, and the queue order.

- **Uses:** `constants`, `obscene`, `problems`, `rudeness`
- **Used by:** `app`, `measure_rudeness`, `tierlist`
- **Tests:** `_selftest`, `_selftest_errors`, `_selftest_obscene`, `_selftest_startup`

The module docstring has the details; this page is the map.

## Public API

- `build_word_list`: Return dictionary words, most common first.
- `download_resumable`: Download `url` to `dest`, resuming a partial `.part` file after interruptions.
- `RudeCollector`: Picks out, from the Wiktionary download's entries, the meanings the rudeness rules read (OB-6): every meaning (rudeness.compact) of a word with any sign of rudeness...
  - methods: add, finish
- `build_wiktionary`: Load every English Wiktionary word into `store`, most common first.
- `compute_penalties`: Flag compounds so they are demoted in the queue (pen: 1 = closed compound, 2 = hyphenated).
- `frequency`: wordfreq's frequency of `w` (`fd`: its get_frequency_dict("en")): hyphenated / spaced forms, which that dictionary lacks, are estimated by wordfreq; any other word it...
- `fill_frequencies`: Store each word's wordfreq frequency (for the progress bar's coverage tag, UI-14).
- `fill_kinds`: Each word's kinds from its stored definition (every source writes "(noun) ..." lines: the Wiktionary build's, WordNet's, dictionaryapi.dev's), else from WordNet...
- `rude_version`: What words.rude should be scored from: RUDENESS_VERSION once the save keeps Wiktionary's meanings (a Wiktionary build, or read later by fetch_rude_senses), else...
- `find_rude`: {word: rudeness.results} for the words of a save: the rules over the meanings it keeps (`saved`: {word: compact JSON}).
- `wants_rude_fetch`: True if the save has no Wiktionary meanings to score yet (a save from before OB-6, or from a word list), so the App reads them in the background (fetch_rude_senses),...
- `read_rude_senses`: {word: compact JSON} (RudeCollector) for the words in `keep`, from a downloaded kaikki.org file.
- `fetch_rude_senses`: Download English Wiktionary next to the save (resumable, like the first run's), keep the meanings the rules read for the words in `keep`, and remove the download.
- `wiktionary_steps`: The main steps build_wiktionary will report, for the progress window's "Step 2 of 5" (plan_line).
- `queue_steps`: The main steps prepare_queue will report (see wiktionary_steps).
- `prepare_queue`: Make sure every unplaced word has a queue position.

## Rules and pitfalls (fixed before: keep them fixed)

- Every stage is resumable and never touches existing progress.
- Keep `wiktionary_steps` / `queue_steps` in step with the stage lines they predict (the "Step i of n" corner).
- The background read of rude meanings honours `OFFLINE_ENV` and retries only after `RUDE_RETRY_S`.
- A Wiktionary build stores the frequencies it ranked by (`frequency`, the same as fill_frequencies) and the kinds, inside one `bulk_write`; `queue_steps(by_wiktionary=True)` then predicts neither step.

## Changing it

- A new preparation step: `prepare_queue`, its step name in `queue_steps`, and a check in `tests/_selftest_queue.py`.
