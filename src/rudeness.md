# `src/rudeness.py`

How rude each meaning is, by hand-written rules over Wiktionary's data (OB-6): points per kind from labels, topics, the definition's wording, groups of people, WordNet, links between words and word families; then what a word's scores lead to (`score_saved`: its kinds, smeared whole or not, the meanings smeared in definitions).

- **Uses:** `obscene`
- **Used by:** `app`, `dealing`, `drawer`, `measure_rudeness`, `store`, `tune_rudeness`, `wordsource`
- **Tests:** `_selftest_dealing`, `_selftest_nextreview`, `_selftest_obscene`, `_selftest_review`, `_selftest_rudeness`, `_selftest_tune`, `_selftest_wikt`

The module docstring has the details; this page is the map.

## Public API

- `gloss_of`: A kaikki.org sense's definition: its last gloss (the first ones name the broader meaning it belongs to).
- `wordnet`: nltk's WordNet when it and its data are installed, else None (it is never downloaded from here).
- `wordnet_match`: The WordNet meaning of `word` (same part of speech) whose definition shares the most words with `gloss` (at least one; the word itself does not count: "pig: a pinkish...
- `names_group`: True if a meaning's definition names a group of people (GROUP).
- `slur_marked`: True if a meaning carries a slur marker of its own (SLUR_MARKS, or the category English ethnic slurs).
- `group_name`: True if a meaning is a group's own name, not a slur for it (see SLUR_MARKS): only "sometimes" rude, another letter case of a name (`respelling`), or naming the group...
- `unslur`: A meaning's points without Slur when it is a group's own name (SLUR_MARKS, group_name; `identity`: the word is one).
- `is_identity`: True if a word is a group's own name: one of its meanings names a group plainly (plain_group_name).
- `plain_group_name`: True if a meaning is a group's name with no rude label or points ("gay: a homosexual"): the word is its name.
- `score_sense`: {kind: points} for one meaning (a kaikki.org sense: its "tags", "raw_tags", "topics", "categories", "glosses"); `word`, `wn`: the word and WordNet (or None), for...
- `harsh`: True if Wiktionary marks a meaning vulgar or offensive (HARSH, or a vulgar category): a crude word or an insult so marked is strong language, one not so marked an...
- `fold`: The rules' {kind: points} (RULE_KINDS) as the kinds shown (RUDE_KINDS, OB-12, the user's three): Expletive is the best of Swear, and Crude and Insult when the meaning...
- `sense_kind`: The meaning's kind: its best-scoring kind with at least MEANING_MIN points, else "clean" (ties go to the ruder kind, in RUDE_KINDS' order from the end).
- `sense_points`: A meaning's points towards the given kinds (its best one of them).
- `is_form`: True if a meaning only names another word ("plural of bitch", "alternative spelling of bell end").
- `word_points`: The word's points from its meanings' {kind: points} (in order), counting only `kinds` (the censored ones): its first meaning counts FIRST_WEIGHT, the mean of the rest...
- `score_word`: [{kind: points} for each meaning] of a word's senses (kaikki.org); pos: their part of speech (one per sense, or one for all); word: the word itself (for its WordNet...
- `rude_kinds_of`: {word: the set of kinds of its rude meanings} from the first pass ({word: [{kind: points}]}): words with none left out.
- `incoming_links`: {word: [(kind, definition, from word)]}: each rude meaning (first pass) that lists the word as a synonym.
- `synonyms`: The words a sense lists as its synonyms (kaikki.org's dicts, or plain words in a compact sense).
- `link_points`: [{kind: points}] the links add to a word's meanings: LINK_OUT for a meaning by the share of its synonyms that have a rude meaning of each kind (`rude_kinds`:...
- `family_points`: [{kind: points}] a word's family adds to its meanings: FAMILY_POINTS for each word it is built from whose first real meaning is rude (`parents`: the words its...
- `families`: {word: the words it is built from}: from {word: [the words its etymology names]} and {word: [its derived terms]} (Wiktionary's, both).
- `score_words`: Both passes over many words: {word: [{kind: points} for each meaning]}.
- `second_pass`: A word's meanings' points after the links (link_points), its family (family_points: `parents`) and its alternative forms ("Alternative form of pum-pum" takes...
- `parts_kind`: For a hyphenated word with a rude word among its parts (asked for; measured: one rude part of two is as telling as two of two, once only slang meanings take it), the...
- `form_target`: The word a meaning is a form of ("Alternative form of pum-pum" -> "pum-pum"), or None.
- `compact`: A kaikki.org sense cut down to what the rules read (the save keeps the meanings of about 150,000 words of a million, with their forms).
- `compact_entry`: A kaikki.org entry's glossed senses, each compact(), the first also holding the entry's word family: "e" the words its etymology names (FAMILY_TEMPLATES, no affixes),...
- `expand`: A compact sense back into the shape the rules read.
- `has_signal`: True if a compact sense shows any sign of rudeness the rules read (a label, a topic or category, the wording): only such words are kept and scored.
- `strongly_labelled`: True if Wiktionary marks a meaning plainly rude (STRONG, or a rude category), not only slang; `firm`: and without a hedge ("mildly vulgar", "sometimes offensive" are...
- `meaning_kinds`: Each meaning's kind (sense_kind), except, on a `common` word (COMMON_ZIPF) whose first real meaning is clean, a rude meaning counts only when strongly labelled ("box:...
- `results`: What a word's scores lead to: (words.rude: the bits of its meanings' kinds (KIND_BITS, meaning_kinds; none but clean unless one of them is `censored`), the whole word...
- `mostly_rude`: True for a word mostly used rudely though its first meaning is ordinary (OB-12, the user's choice from the real data: "dick", "bitch", "faggot", "balls"; a word with...
- `main_kind`: What a word is mostly (shown faintly above it on the card, asked for: "bum-fuck" sexual): of the `censored` kinds, the one its meanings give most points to, counted...
- `score_saved`: {word: results(...)} for {word: its compact senses as JSON text} (the save's table rude, filled from the Wiktionary download): both passes, reporting "(NN%)" through...

## Rules and pitfalls (fixed before: keep them fixed)

- Rules only: no fitted weights, no word lists (the user's choice). Measure every change with `tools/measure_rudeness.py`.
- Bump `RUDENESS_VERSION` whenever a rule changes: that is what makes every save score its words again.
- A meaning "refers back" to a word smeared whole only by naming it with an ending (`_refers_to`, `_ENDINGS`), never by its first letters: a prefix match made "pom: ... pomegranate juice", "jock: a disc jockey" and "lav: lavalier microphone" rude.
- Only a word smeared whole keeps rude kinds ("Obscene words" = censored words). One rude meaning among ordinary ones ("can", "come") stays ordinary; that meaning is smeared in the definitions.
- A group's own name is never a slur ("jews", "trans", "gay", "queer"): only a slur / ethnic / vulgar label or the ethnic-slurs category makes one (`SLUR_MARKS`, `IDENTITY`).
- Forms follow their word's first meaning ("did" is "do"); common words (`COMMON_ZIPF`) count only strongly labelled meanings; a hedge ("sometimes") weakens all a meaning's labels (kaikki sorts them).
- Never name a module after a PyPI package (`src/` is first on the path; `packaging` broke pip once).
- `results` returns (bits, whole, smeared, main kind); `main_kind` is the censored kind with the most `word_points`; a forms-only word takes its word's (score_saved). Bump `RUDENESS_VERSION` when it changes too: it is stored (words.rude_main).
- A form or clipping is never left out of the word's points: it counts as its word's first meaning (second_pass gives it those points). Leaving it out made the slang after "plural of boy" the first meaning (boys, teeth, nuts, mayo). A gloss of over `FORM_WORDS` words is never a form ("fairy").
- A WordNet tie goes to the clean meaning ("taco: a Mexican snack food" is not WordNet's slur); a childish or euphemistic meaning softens what its links bring too ("bum"); a hedged label never smears a common word whole ("what the hell").
- OB-12 (the user's three kinds): the tables still score six kinds, and `fold` (the last step of `score_sense`) turns them into Expletive, Sexual and Slur. Crude and Insult count as Expletive only when the meaning is vulgar or offensive (`harsh`); Clinical never shows. Everything after `score_sense` (links, families, forms, the tuner's answers) works in the three. A tie in `main_kind` and `sense_kind` goes to the ruder kind (slur, then sexual).
- `mostly_rude` (OB-12, the user's pick of three versions tried on the real data): at least `MOSTLY_MIN` (3) firmly labelled rude meanings making `MOSTLY_SHARE` (half) of a word's meanings smear it whole. Without the 3, a word with one rude meaning of two ("coconut", "kimchi", "armpit") was smeared; at 35% "gash" and "coconut" were. It added 81 words with their forms; "cock" (1 of 34) and "roger" (3 of 5, so in) are the known cases.
- `fold` keeps a shown kind's key, at 0 if need be, whenever a kind counting towards it has one: the tuner takes a meaning with no keys as one no number can make rude.
- Wording patterns are whole words (`\b` at both ends: "condom" in "condominium"); a list of examples in a gloss ("such as ... semen", `_EXAMPLES`) is not read.
- A hyphenated word's rude part (`parts_kind`) only reaches its slang-labelled meanings: many clean words have a rude-looking part (tit-for-tat, doo-wop, honky-tonk, dung-fly).

## Changing it

- Points tables are at the top (`TAG_POINTS`, `TOPIC_POINTS`, `WORDING`, `GROUP`). Per-meaning logic: `score_sense`; links and families: `second_pass`; the word's outcome: `results` / `score_saved`.
- Add a test line in `tests/_selftest_rudeness.py` for each case a change is for, and one for what it must not break.
