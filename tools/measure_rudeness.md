# `tools/measure_rudeness.py`

Measuring the rudeness rules against an earlier sorting by Claude (a yardstick only, never shipped): agreement, per-kind precision and recall, false alarms on a control sample. OB-9: `sample` writes a review file for `tierlist.py --review-rude`, and `answers` scores the rules against what the review answered, meaning by meaning.

- **Uses:** `constants`, `obscene`, `rudeness`, `wordsource`
- **Used by:** `tune_rudeness`
- **Tests:** `_selftest_review`

The module docstring has the details; this page is the map.

## Public API

- `fetch`: Stream the download and keep every lower-case English entry, as the program keeps its rude words' (rudeness.compact_entry).
- `load`: ({word: [sense]} as kaikki.org senses (rudeness.expand), {word: [part of speech of each]}, {word: the words it is built from} (rudeness.families))
- `zipf`: How common a word is (wordfreq's Zipf scale: 7 "the", 5 common, 3 rare, 0 never seen).
- `only_forms`: True if every meaning of a word only names another word ("plural of bitch").
- `control_word`: True for 1 in 40 of the words Claude never sorted: the control sample, taken to be clean.
- `scope`: The words the two passes need for `targets`: themselves, their synonyms, the words they are built from, and the words whose meanings list them.
- `outcome`: What the rules' points lead to for a word, and its meanings' kinds: "left out" (no clean meaning and none of a ticked kind: Store._out_sql), "smeared" whole, "some"...
- `read_sorting`: Claude's sorting (word_categories.tsv from the archived tools/classify_obscene.py, kept only as a yardstick): {word: (kind, confidence, [meaning kinds], note)}.
- `claude_kinds`: A word's kinds by Claude: its meanings', plus its own when no meaning shows its rude use.
- `claude_outcome`: What Claude's answers lead to under the same rules: dealt if any meaning is clean or ticked; the whole word smeared when its first meaning, or every one, is of a...
- `score`: {word: [{kind: points}]} for the words in `need`: both passes, or the first alone (no links).
- `measure`: Score the sorting's words and the control words, and report how often the rules lead where Claude's answers do (returns that share).
- `shown_meanings`: The indexes of the meanings a review asks about: the main (first real) one, then those with a sign of rudeness, at most SHOWN_MAX; meanings that only name another...
- `review_item`: One word of a review file: its meanings to ask about, each with the rules' guess (rudeness.sense_kind), and whether the rules smear it whole.
- `pick_sample`: {word: why it was picked}: about size / 10 words of each main kind the rules find, a fifth with a clean main meaning and a rude later one, and a fifth found clean...
- `weak_signs`: Words with a weak sign of rudeness among their first three meanings (a slang or rude label, a body or insult word), common enough to matter: the ones to check for misses.
- `make_sample`: Write a review file (JSON lines, commonest first) for `python tierlist.py --review-rude`.
- `read_answers`: {word: {"kinds": {meaning key: kind}, "whole": bool}} from a review's answers file (the last answer for a word wins).
- `score_answers`: How often the rules agree with the answers: meaning by meaning, per kind (precision / recall), and on smearing the whole word.
- `main`: The command line: fetch, measure, sample or answers.

## Rules and pitfalls (fixed before: keep them fixed)

- It compares meaning by meaning, so rules that only change which words are listed (not which meanings are rude) leave it unchanged.

## Changing it

- `fetch` streams kaikki.org's download into compact entries; `measure` scores them (`--show N` lists differences).
