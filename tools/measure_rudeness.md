# `tools/measure_rudeness.py`

Measuring the rudeness rules against an earlier sorting by Claude (a yardstick only, never shipped): agreement, per-kind precision and recall, false alarms on a control sample. OB-9: `sample` writes a review file for `tierlist.py --review-rude`, and `answers` scores the rules against what the review answered, meaning by meaning.

- **Uses:** `constants`, `obscene`, `rudeness`, `wordsource`
- **Used by:** `tune_rudeness`
- **Tests:** `_selftest_nextreview`, `_selftest_review`

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
- `candidates`: Signals the rules may be missing, mined from Wiktionary's own rude labels (RUDE_LABELS) as a stand-in for the answers: ({topic: share of its meanings with a rude...
- `next_reasons`: {group: (why, the meaning's index or None, what it shares with others: spread over, see _spread)} for the groups of NEXT_SHARES a word is in.
- `pick_next`: {word: (why, [meaning index to ask about])}: the words of NEXT_SHARES, none of `skip` (words reviewed already).
- `reviewed`: The words a review file and its answers already hold.
- `make_next`: Add the next words to review (pick_next) to the end of the review file, commonest first: the review window goes on from the first word not yet answered.
- `make_sample`: Write a review file (JSON lines, commonest first) for `python tierlist.py --review-rude`.
- `read_answers`: {word: {"kinds": {meaning key: kind}, "whole": bool}} from a review's answers file (the last answer for a word wins).
- `score_answers`: How often the rules agree with the answers: meaning by meaning, per kind (precision / recall), and on smearing the whole word.
- `main`: The command line: fetch, measure, sample, next or answers.

## Rules and pitfalls (fixed before: keep them fixed)

- It compares meaning by meaning, so rules that only change which words are listed (not which meanings are rude) leave it unchanged.
- `next` appends to the review file and skips every word already in it or in its answers: never rewrite the file
  (the answers and the window's place follow its words). The meaning a word was picked for is always shown
  (`shown_meanings(also=...)`): a candidate topic is no signal the rules read, so it would be left out otherwise.
- `next`'s candidates come from Wiktionary's own rude labels, a stand-in for the answers: leads to check, never
  rules. Each group is spread over what its words share (`_spread`: a candidate, PER_CANDIDATE each; a pair of kinds;
  the points near the line): unspread, "swear 3.5, sexual 3.0" (one link rule) and "woman" filled their groups. Function
  words and affixes ("of", "an-") are never asked about for having no sign.

## Changing it

- `fetch` streams kaikki.org's download into compact entries; `measure` scores them (`--show N` lists differences).
