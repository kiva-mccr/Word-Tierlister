"""How rude a word's meanings are, by rules: points from several sources, no word list (OB-6).

Each meaning (a sense in the Wiktionary download) earns points towards the rude kinds (obscene.RUDE_KINDS) from
these sources, each with its own table below:

    TAG_POINTS      Wiktionary's labels on the meaning ("vulgar", "derogatory", "slur", "childish", ...)
    TOPIC_POINTS    its topics and categories ("sexuality", "anatomy", "Genitalia", "English ethnic slurs", ...)
    WORDING         the words of the definition itself ("sexual intercourse", "a stupid person")
    GROUP           the definition names a group of people ("of * descent", "a trans woman"): with a rude label
    WORDNET_POINTS  WordNet, when nltk and its WordNet data are installed (never downloaded here): the meaning is
                    matched to one of the word's WordNet meanings by the words the two definitions share, and that
                    meaning's place in WordNet's tree ("sexual activity", "body waste", "unpleasant person", ...)
                    and its usage labels ("ethnic slur", "disparagement", "obscenity") add points

A meaning's kind is the kind with the most points, when it has at least MEANING_MIN of them (else clean). A word's
points come from its meanings, its first (most common) meaning counting most (word_points):

    at least WHOLE_MIN       the whole word is smeared while censoring
    less                     only the meanings with at least MEANING_MIN points are smeared, in the definitions

    score_sense(sense, pos) -> {kind: points}        one meaning
    sense_kind(points) -> kind                        its kind ("clean" below MEANING_MIN)
    score_word(senses, pos, word) -> [points]         each meaning's {kind: points}
    word_points(scored, kinds) -> points              the word's, over the kinds that are censored

A second pass (score_words, second_pass) adds what other words say:
    link_points     Wiktionary's synonym lists say which kind a meaning marked as slang or rude belongs to ("banana:
                    (slang) the penis" is listed with the words for the penis). They never make a standard word rude:
                    synonyms share a meaning, not its rudeness ("shitty" lists "bad").
    family_points   a word built from one whose first meaning is rude ("bullshit" from "shit": its etymology, or
                    that word's derived terms) gains FAMILY_POINTS towards its kind.
    forms           a form ("plural of bitch", form_target / FORM_GLOSS) takes its word's points.

In the program: the Wiktionary build keeps each meaning compactly (compact / expand, only for words with
has_signal), and score_saved scores them all, giving results(): the meanings' kinds as KIND_BITS (words.rude), the
whole word smeared or not, and the first GLOSS_KEY characters of the meanings smeared in the definitions. Bump
RUDENESS_VERSION when the rules change: every save scores its words again. No tkinter, no internet.
"""
import json
import re

from obscene import RUDE_KINDS

# a gloss that only says which word this is a form of ("plural of bitch", "present participle of fuck")
FORM_GLOSS = re.compile(r"\b(?:plural|participle|tense|form|spelling|singular|comparative|superlative|gerund|"
                        r"inflection|misspelling)\b.*\bof ([^\s,;:()]+)\s*$", re.I)

MEANING_MIN = 3.0          # points for a meaning to count as rude (of its best kind)
WHOLE_MIN = 3.5            # points for the whole word to be smeared while censoring
FIRST_WEIGHT = 1.0         # how much the first meaning counts towards the word ...
OTHERS_WEIGHT = 0.35       # ... and how much the rest do (their mean, each counted up to OTHERS_CAP: one very rude
OTHERS_CAP = 5.0           # later meaning never smears a word whose usual meaning is clean: "hoo-ha", "bathroom")

# hedges: "sometimes offensive", "mildly vulgar" count for less
HEDGES = {"sometimes": 0.5, "often": 0.8, "mildly": 0.5, "possibly": 0.5, "potentially": 0.5, "occasionally": 0.5}

TAG_POINTS = {
    "vulgar": {"swear": 3.5, "sexual": 3, "crude": 3},       # (alone: a swear word; the wording decides the rest)
    "offensive": {"insult": 3, "slur": 1},          # (a slur needs a group named, or a slur label: GROUP)
    "derogatory": {"insult": 4, "slur": 2},
    "pejorative": {"insult": 4, "slur": 1},
    "slur": {"slur": 6},
    "ethnic": {"slur": 2},
    "childish": {"crude": 1.5},
    "humorous": {"insult": 0.5},
}

TOPIC_POINTS = {
    "sexuality": {"sexual": 2, "clinical": 2},
    "sex": {"sexual": 2, "clinical": 1.5},
    "anatomy": {"clinical": 1},              # (anatomy alone is not a sensitive word: "antecubital", "foot")
    "genitalia": {"sexual": 2, "clinical": 3},
    "male genitalia": {"sexual": 2, "clinical": 3},
    "female genitalia": {"sexual": 2, "clinical": 3},
    "prostitution": {"sexual": 3},
    "pornography": {"sexual": 3},
    "sexual orientations": {"clinical": 1},
    "lgbtq": {"slur": 0.5},
    "medicine": {"clinical": 0.5},
    "excrement": {"crude": 2, "clinical": 1},
    "bodily functions": {"crude": 2, "clinical": 1},
    "masturbation": {"sexual": 3},
    "sexual activity": {"sexual": 2},
    "feces": {"crude": 2, "clinical": 1},
    "urine": {"crude": 2, "clinical": 1},
    "bodily fluids": {"crude": 1, "clinical": 1},
    "english ethnic slurs": {"slur": 6},
    "english swear words": {"swear": 6},
    "english vulgarities": {"sexual": 2, "swear": 2, "crude": 2},
    "english offensive terms": {"slur": 2, "insult": 2},
    "english derogatory terms": {"insult": 3, "slur": 1},
    "insults": {"insult": 3},
    "personality": {"insult": 0.5},
}

# (pattern, {kind: points}) on the definition's words; each counts once
WORDING = [(re.compile(p, re.I), pts) for p, pts in (
    (r"\b(sexual intercourse|copulat\w*|have sex|having sex|had sex|sex with|sex act|masturbat\w*|orgasm\w*|"
     r"ejaculat\w*|semen|sperm|fellatio|cunnilingus|blowjob|erect(ion|ed) penis|oral sex|anal sex|sodom\w*|"
     r"sexual (act|activity|activities|favou?rs?|position)|sexually (penetrat\w*|suggestive|aroused|stimulat\w*)|"
     r"cybersex|anilingus|rimming|virginity|deflower\w*|erotic\w*|condom|aroused|arousal|lecher\w*|horny|"
     r"pornograph\w*|porn\b|prostitut\w*|brothel|whore|promiscu\w*)", {"sexual": 3, "clinical": 1}),
    (r"\b(penis|vagina|vulva|clitoris|testic\w*|scrotum|genital\w*|anus|rectum)\b", {"sexual": 1.5, "clinical": 2}),
    (r"\b(buttocks|breasts?|nipples?|bottom|backside)\b", {"crude": 1, "clinical": 1, "sexual": 0.5}),
    (r"\b(fec(es|al)|faec(es|al)|excrement|dung|urin(e|ate|ating|ation)|defecat\w*|flatulen\w*|fart\w*|"
     r"vomit\w*|snot|mucus|toilet)\b", {"crude": 2, "clinical": 1}),
    (r"\b(minced oath|euphemistic form of (damn|fuck|shit|hell|god)|euphemism for (damn|fuck|shit|hell))",
     {"swear": 3}),
    (r"\b(used as an? (intensifier|expletive|exclamation|oath)|expletive|intensifier|exclamation of "
     r"(anger|annoyance|frustration|surprise|disgust)|expressing (anger|annoyance|frustration))", {"swear": 3}),
    (r"^(an?|one|someone|somebody|any) (\w+ )?(person|man|woman|individual|people|fellow|guy|girl|boy)?\s*"
     r"(who|that|whose)?\b.*\b(stupid|foolish|idiotic|contemptible|despicable|worthless|obnoxious|annoying|"
     r"incompetent|cowardly|lazy|unpleasant|silly|dull|ignorant|arrogant|mean|nasty|hateful|weak|pathetic)\b",
     {"insult": 3}),
    (r"\b(stupid|foolish|contemptible|despicable|worthless) (person|man|woman|people|fellow)\b", {"insult": 2}),
    (r"\b(medical|medicine|disease|disorder|condition|syndrome|infection|hormone|anatomy|anatomical)\b",
     {"clinical": 0.5}),
)]

# a group of people (race, nationality, religion, sexuality, gender, disability): with a rude label, a slur
GROUP = [re.compile(r"\b(of (\w+ )?(\w+ )?(descent|origin|ancestry|extraction|heritage)|black (person|people|man|"
                    r"woman)|jew(s|ish)?\b|homosexual|gay (man|men|person)|lesbian|bisexual|trans(gender)? (woman|"
                    r"man|person|people)|transgender|effeminate|disabled|mentally|(half|quarter)[- ]caste|mixed[- ]"
                    r"race|caucasian|immigrants?\b)", re.I),
         re.compile(r"(^|\b([Aa]n?|[Tt]he) )[A-Z][a-z]+ (person|people|man|woman|men|women)\b"),  # "An Italian person"
         re.compile(r"\b(a|the) native of\b|\bnatives of\b", re.I)]
GROUP_POINTS = {"slur": 5}

# WordNet (optional): points for a matched meaning that is, or is a kind of, one of these; and for its usage labels
WORDNET_POINTS = {
    "sexual_activity.n.01": {"sexual": 2, "clinical": 1},
    "copulate.v.01": {"sexual": 2, "clinical": 1}, "sleep_together.v.01": {"sexual": 2, "clinical": 1},
    "masturbate.v.01": {"sexual": 2, "clinical": 1}, "masturbate.v.02": {"sexual": 2, "clinical": 1},
    "genitalia.n.01": {"sexual": 1, "clinical": 2}, "erectile_organ.n.01": {"sexual": 1, "clinical": 2},
    "reproductive_organ.n.01": {"sexual": 1, "clinical": 2},
    "body_waste.n.01": {"crude": 2, "clinical": 1}, "excrete.v.01": {"crude": 2, "clinical": 1},
    "prostitute.n.01": {"sexual": 2},
    "unpleasant_person.n.01": {"insult": 2.5}, "unwelcome_person.n.01": {"insult": 1}, "bad_person.n.01": {"insult": 2},
    "simpleton.n.01": {"insult": 2.5},
    # usage labels
    "ethnic_slur.n.01": {"slur": 5}, "disparagement.n.01": {"insult": 1.5, "slur": 1},
    "obscenity.n.02": {"swear": 2, "sexual": 1.5, "crude": 1.5}, "vulgarism.n.01": {"swear": 2, "sexual": 1.5, "crude": 1.5},
}
WORDNET_SLANG = {"slang.n.02", "colloquialism.n.01", "euphemism.n.01"}     # (not the proper word: see slangy)
WORDNET_POS = {"noun": "n", "verb": "v", "adj": "a", "adv": "r"}
_STOP = set("a an the of to in on or and for with by as at from that this which who whom whose is are be been being "
            "it its one someone something any some person thing used especially usually often like kind type sort "
            "also called other family member members part various form".split())
_WORD = re.compile(r"[a-z]+")

RUDE_CATEGORIES = {"english vulgarities", "english swear words", "english ethnic slurs", "english offensive terms",
                   "english derogatory terms"}         # (as good as a rude label)

SWEAR_POS = {"intj"}       # an interjection with a rude label is most likely a swear word


def _label(text):
    """A label, topic or category as the tables name it: lower case, hyphens as spaces."""
    return str(text).lower().replace("-", " ")


def gloss_of(sense):
    """A kaikki.org sense's definition: its last gloss (the first ones name the broader meaning it belongs to)."""
    return str((sense.get("glosses") or [""])[-1])


def _hedged(labels):
    """[(label, weight)] for a meaning's labels: a hedge ("sometimes", "mildly") weakens the label after it."""
    out, weight = [], 1.0
    for lab in labels:
        lab = _label(lab).strip()
        if lab in HEDGES:
            weight = HEDGES[lab]
            continue
        out.append((lab, weight))
        weight = 1.0
    return out


def _add(points, table, weight=1.0):
    for kind, p in table.items():
        points[kind] = points.get(kind, 0.0) + p * weight


_wordnet = []                  # [the wordnet module, or None], once looked for


def wordnet():
    """nltk's WordNet when it and its data are installed, else None (it is never downloaded from here)."""
    if not _wordnet:
        try:
            from nltk.corpus import wordnet as wn
            wn.synsets("dog")
            _wordnet.append(wn)
        except Exception:                    # (not installed, or its data missing: LookupError)
            _wordnet.append(None)
    return _wordnet[0]


_signals = {}                  # synset name -> (its WORDNET_POINTS together, slang?)


def _synset_signals(syn):
    """The WORDNET_POINTS of a WordNet meaning (itself, what it is a kind of, its usage labels), and whether WordNet
    calls it slang; worked out once per meaning."""
    name = syn.name()
    if name not in _signals:
        points, names = {}, {name}
        for path in syn.hypernym_paths():
            names.update(h.name() for h in path)
        usage = {d.name() for d in syn.usage_domains()}
        for n in names | usage:
            if n in WORDNET_POINTS:
                _add(points, WORDNET_POINTS[n])
        _signals[name] = (points, bool(usage & WORDNET_SLANG))
    return _signals[name]


def _content(text):
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


def wordnet_match(word, gloss, pos, wn):
    """The WordNet meaning of `word` (same part of speech) whose definition shares the most words with `gloss` (at
    least one; the word itself does not count: "pig: a pinkish colour, like that of a pig" is not the animal), or
    whose synonyms are the whole of a short gloss ("Penis.", "To urinate."), or None."""
    if wn is None or not word:
        return None
    try:
        syns = wn.synsets(word.replace(" ", "_").replace("-", "_"), WORDNET_POS.get(pos))
    except Exception:
        return None
    if not syns:
        return None
    want = _content(gloss) - _content(word.replace("-", " "))
    best, best_n = None, 0
    for syn in syns:
        names = {p for n in syn.lemma_names() for p in n.lower().split("_")}
        n = len(want & (_content(syn.definition()) - _content(word.replace("-", " "))))
        if want and want <= names:
            n = max(n, len(want) + 1)                   # the gloss is just a synonym
        if n > best_n:
            best, best_n = syn, n
    return best


def score_sense(sense, pos="", word="", wn=None):
    """{kind: points} for one meaning (a kaikki.org sense: its "tags", "raw_tags", "topics", "categories",
    "glosses"); `word`, `wn`: the word and WordNet (or None),
    for WORDNET_POINTS."""
    points = {}
    labels = list(sense.get("tags", [])) + list(sense.get("raw_tags", []))
    rude_label = False
    for lab, w in _hedged(labels):
        if lab in TAG_POINTS:
            _add(points, TAG_POINTS[lab], w)
            rude_label = rude_label or lab in ("vulgar", "offensive", "derogatory", "pejorative", "slur")
    names = [_label(t) for t in sense.get("topics", [])]
    names += [(c.get("name") if isinstance(c, dict) else str(c)).lower() for c in sense.get("categories", [])]
    rude_label = rude_label or bool(RUDE_CATEGORIES & set(names))
    for name in set(names):
        if name in TOPIC_POINTS:
            _add(points, TOPIC_POINTS[name])
    gloss = gloss_of(sense)
    for pattern, table in WORDING:
        if pattern.search(gloss):
            _add(points, table)
    if rude_label and any(g.search(gloss) for g in GROUP):
        _add(points, GROUP_POINTS)
    wn_slang = False
    syn = wordnet_match(word, gloss, pos, wn)
    if syn is not None:
        wn_points, wn_slang = _synset_signals(syn)
        _add(points, wn_points)
    if pos in SWEAR_POS and rude_label:
        _add(points, {"swear": 3})
    slangy = wn_slang or rude_label or any(lab in ("slang", "informal", "colloquial", "euphemistic", "childish")
                                           for lab, _w in _hedged(labels))
    if slangy and points.get("clinical"):    # a rude or slang label is never the neutral, proper word: its
        moved = points["clinical"] * 0.7     # points go to Sexual (Crude for bodily waste)
        points["clinical"] -= moved
        _add(points, {"crude" if points.get("crude", 0) > points.get("sexual", 0) else "sexual": moved})
    elif not slangy and points.get("sexual"):    # and plain words about sex are the proper ones ("male: produces
        moved = points["sexual"] * 0.7           # sperm", "pin-up"): Clinical, not Sexual
        points["sexual"] -= moved
        _add(points, {"clinical": moved})
    return points


def sense_kind(points):
    """The meaning's kind: its best-scoring kind with at least MEANING_MIN points, else "clean" (ties go to the
    ruder kind, in RUDE_KINDS' order from the end)."""
    best = max(RUDE_KINDS[::-1], key=lambda k: points.get(k, 0.0))
    return best if points.get(best, 0.0) >= MEANING_MIN else "clean"


def sense_points(points, kinds=RUDE_KINDS):
    """A meaning's points towards the given kinds (its best one of them)."""
    return max((points.get(k, 0.0) for k in kinds), default=0.0)


def is_form(sense):
    """True if a meaning only names another word ("plural of bitch", "alternative spelling of bell end")."""
    gloss = gloss_of(sense)
    return bool(sense.get("form_of") or sense.get("alt_of") or FORM_GLOSS.search(gloss))


def word_points(scored, kinds=RUDE_KINDS, forms=None):
    """The word's points from its meanings' {kind: points} (in order), counting only `kinds` (the censored ones):
    its first real meaning counts FIRST_WEIGHT, the mean of the rest OTHERS_WEIGHT (each up to OTHERS_CAP).
    `forms` ([bool] per meaning: is_form) leaves out the meanings that only name another word, unless every
    one does."""
    pts = [sense_points(p, kinds) for p in scored]
    if forms and not all(forms):
        pts = [p for p, f in zip(pts, forms) if not f]
    if not pts:
        return 0.0
    rest = [min(p, OTHERS_CAP) for p in pts[1:]]
    return FIRST_WEIGHT * pts[0] + (OTHERS_WEIGHT * sum(rest) / len(rest) if rest else 0.0)


def score_word(senses, pos="", word="", wn=None):
    """[{kind: points} for each meaning] of a word's senses (kaikki.org); pos: their part of speech (one per
    sense, or one for all); word: the word itself (for its WordNet meanings); wn: WordNet (wordnet()), or None for
    none."""
    poses = pos if isinstance(pos, (list, tuple)) else [pos] * len(senses)
    return [score_sense(s, p, word, wn) for s, p in zip(senses, poses)]


# ---- the links between words: a second pass over the first scores (Wiktionary's synonym lists) -------------------
LINK_OUT = 2.5             # a meaning whose synonyms are mostly of a kind: up to this many points towards it
LINK_IN = 2.0              # a word listed as a synonym of a rude meaning: towards that kind, on its matching meaning
LINK_IN_MAX = 5.0          # (however many rude meanings list it)
LINK_MIN = 2               # synonyms a meaning needs before they count
# Synonyms share a meaning, not its rudeness ("shitty" lists "bad", "fuck" lists "company"): the links only count on
# a meaning Wiktionary marks as not standard English, to say which kind of rude word it is ("banana: (slang) penis")
REGISTER = {"slang", "euphemistic", "vulgar", "derogatory", "pejorative", "offensive", "childish", "slur",
            "dysphemistic"}        # (not "informal", "colloquial", "humorous": thesaurus pages mix those with rude ones)


def rude_kinds_of(scored_words):
    """{word: the set of kinds of its rude meanings} from the first pass ({word: [{kind: points}]}): words with
    none left out."""
    out = {}
    for w, scored in scored_words.items():
        kinds = {sense_kind(p) for p in scored} - {"clean"}
        if kinds:
            out[w] = kinds
    return out


def incoming_links(words, scored_words):
    """{word: [(kind, definition, from word)]}: each rude meaning (first pass) that lists the word as a synonym.
    `words`: {word: [sense]} (kaikki.org senses, with "synonyms")."""
    out = {}
    for w, senses in words.items():
        for sense, points in zip(senses, scored_words.get(w, [])):
            kind = sense_kind(points)
            if kind == "clean":
                continue
            gloss = gloss_of(sense)
            for syn in synonyms(sense):
                if syn != w:
                    out.setdefault(syn, []).append((kind, gloss, w))
    return out


def synonyms(sense):
    """The words a sense lists as its synonyms (kaikki.org's dicts, or plain words in a compact sense)."""
    return [s.get("word") if isinstance(s, dict) else s for s in sense.get("synonyms", []) if s]


def link_points(word, senses, rude_kinds, incoming):
    """[{kind: points}] the links add to a word's meanings: LINK_OUT for a meaning by the share of its synonyms that
    have a rude meaning of each kind (`rude_kinds`: rude_kinds_of), LINK_IN for each rude meaning elsewhere that
    lists the word, on the meaning of this word whose definition shares a word with it (none if no meaning does:
    "banana" in a list of words for the penis gains nothing on the fruit). Only meanings marked as not standard
    English (REGISTER) gain anything."""
    added = [{} for _ in senses]
    marked = [any(lab in REGISTER for lab, _w in _hedged(list(s.get("tags", [])) + list(s.get("raw_tags", []))))
              for s in senses]
    for i, sense in enumerate(senses):
        syns = [s for s in synonyms(sense) if s != word]
        if marked[i] and len(syns) >= LINK_MIN:
            for kind in RUDE_KINDS:
                share = sum(1 for s in syns if kind in rude_kinds.get(s, ())) / len(syns)
                if share >= 0.3:
                    _add(added[i], {kind: LINK_OUT * share})
    glosses = [_content(gloss_of(s)) for s in senses]
    for kind, gloss, source in incoming.get(word, ()):
        want = _content(gloss) | _content(source.replace("-", " "))
        best, best_n = None, 0
        for i, have in enumerate(glosses):
            n = len(want & have) if marked[i] else 0
            if n > best_n:
                best, best_n = i, n
        if best is not None and added[best].get(kind, 0.0) < LINK_IN_MAX:
            _add(added[best], {kind: min(LINK_IN, LINK_IN_MAX - added[best].get(kind, 0.0))})
    return added


FAMILY_POINTS = 2.0        # a word built from a rude word (its etymology, or that word's derived terms)


def family_points(word, senses, parents, first):
    """[{kind: points}] a word's family adds to its meanings: FAMILY_POINTS for each word it is built from whose
    first real meaning is rude (`parents`: the words its etymology names, and those listing it as derived:
    "bullshit" from "shit"; `first`: the first pass), towards the parent's kind. A booster: on its own it never
    makes a meaning rude (measured: it replaces the hand-picked list's roots, with a little more agreement)."""
    added = [{} for _ in senses]
    for parent in parents:
        scored = first.get(parent)
        if not scored or parent == word:
            continue
        kind = sense_kind(scored[0])
        if kind == "clean":
            continue
        for p, sense in zip(added, senses):
            if not is_form(sense):
                _add(p, {kind: FAMILY_POINTS})
    return added


def families(built_from, derived):
    """{word: the words it is built from}: from {word: [the words its etymology names]} and {word: [its derived
    terms]} (Wiktionary's, both)."""
    out = {w: set(ps) for w, ps in built_from.items()}
    for parent, kids in derived.items():
        for kid in kids:
            out.setdefault(kid, set()).add(parent)
    return out


def score_words(words, pos=None, wn=None, family=None):
    """Both passes over many words: {word: [{kind: points} for each meaning]}. `words`: {word: [sense]} (kaikki.org
    senses), `pos`: {word: [part of speech of each sense]}; wn: WordNet or None; `family`: families(...) or None.
    The first pass scores each meaning on its own; the second adds the links between words (link_points) and
    word families (family_points)."""
    pos, family = pos or {}, family or {}
    first = {w: score_word(senses, pos.get(w, ""), w, wn) for w, senses in words.items()}
    rude, incoming = rude_kinds_of(first), incoming_links(words, first)
    return {w: second_pass(w, words[w], first, rude, incoming, family.get(w, ())) for w in first}


def second_pass(word, senses, first, rude, incoming, parents=()):
    """A word's meanings' points after the links (link_points), its family (family_points: `parents`) and its
    alternative forms ("Alternative form of pum-pum" takes pum-pum's points); `first`: every word's first-pass
    points, `rude` / `incoming` from them."""
    added = link_points(word, senses, rude, incoming)
    out = [dict(p) for p in first[word]]
    for p, a, f in zip(out, added, family_points(word, senses, parents, first)):
        _add(p, a)
        _add(p, f)
    for p, sense in zip(out, senses):
        target = form_target(sense)
        if target and target != word and target in first:      # an alternative form takes its word's points
            best = max(first[target], key=sense_points, default={})
            for k, v in best.items():
                p[k] = max(p.get(k, 0.0), v)
    return out


def form_target(sense):
    """The word a meaning is a form of ("Alternative form of pum-pum" -> "pum-pum"), or None."""
    f = (sense.get("form_of") or sense.get("alt_of") or [{}])[0]
    if isinstance(f, dict) and f.get("word"):
        return f["word"]
    m = FORM_GLOSS.search(gloss_of(sense))
    return m.group(1).lower().strip(".'\"") if m else None


# ---- in the program (OB-6): what is kept in the save, and what the scores lead to --------------------------------
RUDENESS_VERSION = "2"     # bumped when the rules change: every save scores its words again (prepare_queue)
KIND_BITS = {"clean": 1, **{k: 2 << i for i, k in enumerate(RUDE_KINDS)}}     # words.rude: the kinds of its meanings
LISTED = (KIND_BITS["swear"], True, [])     # results() for a word on the hand-picked list, when no meanings are known
GLOSS_KEY = 40             # a meaning is told apart in the definitions by its first characters
_SIGNAL_TAGS = set(TAG_POINTS) | REGISTER | set(HEDGES)
_SIGNAL_NAMES = set(TOPIC_POINTS) | RUDE_CATEGORIES
_KEPT_TAGS = _SIGNAL_TAGS | {"informal", "colloquial"}     # (read by score_sense's slangy: kept, but no sign alone)
_ANY_WORDING = re.compile("|".join(f"(?:{p.pattern})" for p, _t in WORDING), re.I)    # (one search: a million words)


def compact(sense, pos=""):
    """A kaikki.org sense cut down to what the rules read (the save keeps the meanings of about 150,000 words of a
    million, with their forms)."""
    out = {"g": gloss_of(sense)[:160]}
    tags = [t for t in list(sense.get("tags", [])) + list(sense.get("raw_tags", []))
            if _label(t) in _KEPT_TAGS or t in ("form-of", "alt-of")]
    cats = [(c.get("name") if isinstance(c, dict) else str(c)) for c in sense.get("categories", [])]
    cats = [c for c in cats if c and c.lower() in _SIGNAL_NAMES]
    target = form_target(sense)
    for key, val in (("t", tags), ("p", list(sense.get("topics", []))), ("c", cats), ("s", synonyms(sense)),
                     ("f", target), ("pos", pos)):
        if val:
            out[key] = val
    return out


# etymology templates that name the words a word is built from ("compound|en|mother|fucker", "suffix|en|bitch|y")
FAMILY_TEMPLATES = {"compound", "com", "affix", "af", "suffix", "suf", "prefix", "pre", "blend", "confix", "con",
                    "surf", "univerbation", "univ", "clipping", "clip", "back-formation", "bf", "rhyming slang"}


def compact_entry(entry, examples=0):
    """A kaikki.org entry's glossed senses, each compact(), the first also holding the entry's word family: "e" the
    words its etymology names (FAMILY_TEMPLATES, no affixes), "d" its derived terms. `examples`: keep that many of
    each sense's examples ("x", for tools/measure_rudeness.py)."""
    pos = entry.get("pos") or ""
    out = []
    for s in entry.get("senses", []):
        if s.get("glosses"):
            c = compact(s, pos)
            x = [str(e.get("text", ""))[:200] for e in s.get("examples", [])[:examples] if e.get("text")]
            if x:
                c["x"] = x
            out.append(c)
    if out:
        built = []
        for t in entry.get("etymology_templates", []):
            if t.get("name") in FAMILY_TEMPLATES:
                args = t.get("args", {})
                for k in sorted((k for k in args if k.isdigit() and k != "1"), key=int):
                    v = str(args[k]).strip().lower()
                    if v and v[0] != "-" and v[-1] != "-" and v not in built:
                        built.append(v)
        derived = sorted({d.get("word") for d in entry.get("derived", []) if d.get("word")})
        for key, val in (("e", built), ("d", derived)):
            if val:
                out[0][key] = val
    return out


def expand(c):
    """A compact sense back into the shape the rules read."""
    out = {"glosses": [c.get("g", "")], "tags": c.get("t", []), "topics": c.get("p", []),
           "categories": c.get("c", []), "synonyms": c.get("s", [])}
    if c.get("f"):
        out["form_of"] = [{"word": c["f"]}]
    return out


def has_signal(c):
    """True if a compact sense shows any sign of rudeness the rules read (a label, a topic or category, the
    wording): only such words are kept and scored."""
    if {_label(t) for t in c.get("t", [])} & _SIGNAL_TAGS:
        return True
    if {_label(n) for n in c.get("p", []) + c.get("c", [])} & _SIGNAL_NAMES:
        return True
    return bool(_ANY_WORDING.search(c.get("g", "")))


def results(word, senses, scored, censored):
    """What a word's scores lead to: (words.rude: the bits of its meanings' kinds (KIND_BITS), the whole word smeared
    while censoring, [the first GLOSS_KEY characters of each meaning of a `censored` kind]: smeared in the
    definitions). `senses`: the kaikki.org-shaped senses that were scored."""
    kinds = [sense_kind(p) for p in scored]
    bits = 0
    for k in kinds or ["clean"]:
        bits |= KIND_BITS[k]
    forms = [is_form(s) for s in senses]
    whole = word_points(scored, censored, forms) >= WHOLE_MIN
    smeared = [gloss_of(s)[:GLOSS_KEY] for s, k in zip(senses, kinds) if k in censored]
    return bits, whole, smeared


def score_saved(saved, censored, wn=None, log=None):
    """{word: results(...)} for {word: its compact senses as JSON text} (the save's table rude, filled from the
    Wiktionary download): both passes, reporting "(NN%)" through `log` as it goes (under a minute for 150,000 words)."""
    compacts = {w: json.loads(text) for w, text in saved.items()}
    words = {w: [expand(c) for c in cs] for w, cs in compacts.items()}
    pos = {w: [c.get("pos", "") for c in cs] for w, cs in compacts.items()}
    family = families({w: [p for c in cs for p in c.get("e", ())] for w, cs in compacts.items()},
                      {w: [k for c in cs for k in c.get("d", ())] for w, cs in compacts.items()})
    total, step = 2 * len(words) + 1, max(1, len(words) // 20)

    def tell(i):
        if log and i % step == 0:
            log(f"  scored {i // 2:,} of {len(words):,} words ({100 * i // total}%)")
    first = {}
    for i, (w, senses) in enumerate(words.items()):
        tell(i)
        first[w] = score_word(senses, pos[w], w, wn)
    rude, incoming = rude_kinds_of(first), incoming_links(words, first)
    out = {}
    for i, w in enumerate(words, len(words)):
        tell(i)
        out[w] = results(w, words[w], second_pass(w, words[w], first, rude, incoming, family.get(w, ())), censored)
    for w, senses in words.items():          # a word that is only forms of one other is smeared whole as that one is
        targets = {form_target(s) for s in senses}
        if len(targets) == 1 and all(is_form(s) for s in senses) and (t := targets.pop()) in out and t != w:
            out[w] = (out[w][0], out[t][1], out[w][2])
    return out
