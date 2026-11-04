"""Measure the rules in src/rudeness.py against Claude's sorting (OB-6): how often they lead to the same thing.

    python tools/measure_rudeness.py fetch [--sorting word_categories.tsv]    stream kaikki.org's English download
                                                                              (~3 GB, not kept) and keep every
                                                                              lower-case English entry, compactly
    python tools/measure_rudeness.py measure [--policy B] [--show 40] [--no-links] [--no-wordnet] [--no-families]
    python tools/measure_rudeness.py sample [--size 1500] [--out rude_review.jsonl]     words for a review by hand
    python tools/measure_rudeness.py next [--size 300] [--review rude_review.jsonl]   the next words to review
    python tools/measure_rudeness.py answers [--review rude_review.jsonl] [--show 40]  the rules against its answers

OB-9: `sample` picks words for `python tierlist.py --review-rude` (a weighted sample: each main kind the rules
find, words with a clean main meaning and a rude later one, and words found clean with a weak sign of rudeness,
the likely misses), each with the meanings worth asking about and the rules' guesses; `answers` scores the rules
against what the review answered (rude_review_answers.jsonl beside it), meaning by meaning. `next` (active review)
adds the words that teach the rules most to the end of the review file, none reviewed already: a meaning near the
line, signals that disagree, a candidate signal (a topic the rules never read, or a gloss word common in Wiktionary's
rude meanings, on a meaning the rules find clean) and common words with no sign at all (what the rules miss). The answers only test
and tune the rules: the program never reads them.

The compact entries (rudeness_entries.jsonl next to the sorting, about 300 MB) keep each meaning as the program does
(rudeness.compact_entry: the last gloss, the labels, topics and categories the rules read, synonyms, the word it is
a form of, the word family). Every word is kept
because the links between words (the second pass) reach anywhere. The comparison uses the meanings Claude saw (the
first few of each word) and a censoring policy, the same for both sides:
    A   every rude kind is censored (Clinical, Crude, Swear word, Insult, Sexual, Slur)
    B   only Crude, Swear word, Sexual and Slur (Clinical and Insult words shown as they are)
1 in 40 of the other words, never candidates for the sorting, are a control taken to be clean: the share the
rules flag is their false-alarm rate. Never part of the program.
"""
import argparse
import collections
import hashlib
import json
import math
import os
import re
import sys
import urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(ROOT, "src"))
import obscene  # noqa: E402
from constants import REVIEW_FILE, review_answers_path  # noqa: E402
from wordfreq import zipf_frequency  # noqa: E402
import rudeness  # noqa: E402
from wordsource import WIKT_URL  # noqa: E402

POLICIES = {"A": set(obscene.RUDE_KINDS), "B": set(obscene.CENSORED)}
OUTCOMES = ("shown", "some", "smeared", "left out")


def fetch(out, url=WIKT_URL, log=print):
    """Stream the download and keep every lower-case English entry, as the program keeps its rude words'
    (rudeness.compact_entry)."""
    n = kept = 0
    with urllib.request.urlopen(url, timeout=60) as r, open(out, "w", encoding="utf-8") as f:
        for raw in r:
            n += 1
            if n % 200000 == 0:
                log(f"  {n:,} entries read, {kept:,} kept")
            try:
                e = json.loads(raw)
            except ValueError:
                continue
            w = e.get("word", "")
            if e.get("lang_code") != "en" or not w or w != w.lower():
                continue
            senses = rudeness.compact_entry(e)
            if senses:
                f.write(json.dumps({"w": w, "senses": senses}, separators=(",", ":")) + "\n")
                kept += 1
    log(f"Kept {kept:,} of {n:,} entries in {out}.")


def load(path):
    """({word: [sense]} as kaikki.org senses (rudeness.expand), {word: [part of speech of each]}, {word: the words it
    is built from} (rudeness.families))"""
    words, poses = collections.defaultdict(list), collections.defaultdict(list)
    built, derived = collections.defaultdict(list), collections.defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            for c in e["senses"]:
                words[e["w"]].append(rudeness.expand(c))
                poses[e["w"]].append(c.get("pos", ""))
                built[e["w"]] += c.get("e", [])
                derived[e["w"]] += c.get("d", [])
    return words, poses, rudeness.families(built, derived)


def zipf(word):
    """How common a word is (wordfreq's Zipf scale: 7 "the", 5 common, 3 rare, 0 never seen)."""
    return zipf_frequency(word, "en")


def only_forms(senses):
    """True if every meaning of a word only names another word ("plural of bitch")."""
    return all(rudeness.is_form(s) for s in senses)


def control_word(w, sorting):
    """True for 1 in 40 of the words Claude never sorted: the control sample, taken to be clean."""
    return w not in sorting and int(hashlib.md5(w.encode()).hexdigest(), 16) % 40 == 0


def scope(targets, words, family):
    """The words the two passes need for `targets`: themselves, their synonyms, the words they are built from, and
    the words whose meanings list them."""
    need = set(targets)
    for w in targets:
        need.update(family.get(w, ()))
        for s in words.get(w, ()):
            need.update(rudeness.synonyms(s))
    for w, senses in words.items():
        if any(t in targets for s in senses for t in rudeness.synonyms(s)):
            need.add(w)
    return need


def outcome(scored, censored, senses, ticked=obscene.TICKED, common=False):
    """What the rules' points lead to for a word, and its meanings' kinds: "left out" (no clean meaning and none of a
    ticked kind: Store._out_sql), "smeared" whole, "some" meanings smeared, or "shown" (rudeness.results)."""
    kinds = rudeness.meaning_kinds(senses, scored, common)
    found = set(kinds) or {"clean"}
    if not ({"clean"} | set(ticked)) & found:
        return "left out", kinds
    _bits, whole, _smeared, _main = rudeness.results("", senses, scored, censored, common)
    if whole:
        return "smeared", kinds
    return ("some" if found & censored else "shown"), kinds


def read_sorting(path):
    """Claude's sorting (word_categories.tsv from the archived tools/classify_obscene.py, kept only as a yardstick):
    {word: (kind, confidence, [meaning kinds], note)}."""
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            w, kind, conf, senses, note = (line.rstrip("\n").split("\t") + [""] * 5)[:5]
            out[w] = (kind, int(conf or 0), [x for x in senses.split(",") if x], note)
    return out


def claude_kinds(kind, meanings):
    """A word's kinds by Claude: its meanings', plus its own when no meaning shows its rude use."""
    found = set(meanings) or {"clean"}
    if kind in obscene.RUDE_KINDS and not (found - {"clean"}):
        found.add(kind)
    return found


def claude_outcome(kind, meanings, censored, ticked=obscene.TICKED):
    """What Claude's answers lead to under the same rules: dealt if any meaning is clean or ticked; the whole word
    smeared when its first meaning, or every one, is of a censored kind (or its rude use is the one missing)."""
    found = claude_kinds(kind, meanings)
    if not ({"clean"} | set(ticked)) & found:
        return "left out"
    listed = set(meanings) or {"clean"}
    if (meanings and meanings[0] in censored) or listed <= censored or (kind in censored and listed == {"clean"}):
        return "smeared"
    return "some" if found & censored else "shown"


def score(words, poses, need, links, wn, family):
    """{word: [{kind: points}]} for the words in `need`: both passes, or the first alone (no links)."""
    sub = {w: words[w] for w in need if w in words}
    if links:
        return rudeness.score_words(sub, {w: poses[w] for w in sub}, wn, family)
    return {w: rudeness.score_word(s, poses[w], w, wn) for w, s in sub.items()}


def measure(sorting, entries, policy="B", show=0, log=print, wn=None, links=True, families=True,
            common_zipf=rudeness.COMMON_ZIPF):
    """Score the sorting's words and the control words, and report how often the rules lead where Claude's answers
    do (returns that share)."""
    censored = POLICIES[policy]
    words, poses, family = load(entries)
    family = family if families else {}
    claude = read_sorting(sorting)
    order = {w: i for i, w in enumerate(claude)}
    base = [w for w, v in claude.items() if not v[3].startswith("form of ") and w in words and not only_forms(words[w])]
    control = [w for w in words if control_word(w, claude) and not only_forms(words[w])]
    scored = score(words, poses, scope(set(base) | set(control), words, family), links, wn, family)
    table, tp, fp, fn = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    agree = common = common_agree = 0
    diffs = []
    for w in base:
        kind, _conf, meanings = claude[w][:3]
        ref = claude_outcome(kind, meanings, censored)
        k = max(1, len(meanings))
        got, kinds = outcome(scored[w][:k], censored, words[w][:k], common=zipf(w) >= common_zipf)
        table[ref, got] += 1
        agree += ref == got
        if order[w] < 5000:
            common += 1
            common_agree += ref == got
        want, have = claude_kinds(kind, meanings) - {"clean"}, set(kinds) - {"clean"}
        for k in obscene.RUDE_KINDS:
            tp[k] += k in want and k in have
            fp[k] += k not in want and k in have
            fn[k] += k in want and k not in have
        if ref != got:
            diffs.append((order[w], w, ref, got))
    log(f"Policy {policy}{', WordNet' if wn else ''}{', links' if links else ''}{', families' if family else ''}"
        f", common from Zipf {common_zipf:g}: {len(base):,} of the sorting's "
        "words have Wiktionary entries.")
    log(f"Same outcome: {agree / len(base):.1%} (the commonest 5,000 of the sorting: {common_agree / max(1, common):.1%})")
    log("Rows: Claude's answers; columns: the rules.  " + "  ".join(f"{o:>9}" for o in OUTCOMES))
    for r in OUTCOMES:
        log(f"  {r:>9}" + "".join(f"{table[r, c]:>11,}" for c in OUTCOMES))
    log("Each kind (a word has it): precision / recall")
    for k in obscene.RUDE_KINDS:
        log(f"  {k:9} {tp[k] / max(1, tp[k] + fp[k]):6.1%} / {tp[k] / max(1, tp[k] + fn[k]):6.1%}"
            f"   ({tp[k] + fn[k]:,} words have it by Claude)")
    flagged = collections.Counter(outcome(scored[w], censored, words[w], common=zipf(w) >= common_zipf)[0]
                                  for w in control)
    log(f"Control words ({len(control):,}, taken to be clean): " +
        ", ".join(f"{o} {flagged[o] / max(1, len(control)):.1%}" for o in OUTCOMES))
    for _i, w, ref, got in sorted(diffs)[:show]:
        log(f"  {w}: Claude {ref}, rules {got}")
    return agree / len(base)


# ---- a review by hand (OB-9) ---------------------------------------------------------------------------------
SHOWN_MAX = 8                 # meanings asked about per word: the main one and up to seven with a sign of rudeness
WEAK = ("slang", "informal", "colloquial", "euphemistic", "childish", "vulgar", "derogatory", "offensive")


def _signal(sense, points):
    """True if a meaning is worth asking about: it has points of any kind, or a sign the rules read."""
    return any(v > 0 for v in points.values()) or rudeness.has_signal(rudeness.compact(sense))


def shown_meanings(senses, scored, also=()):
    """The indexes of the meanings a review asks about: the main (first real) one, then those with a sign of
    rudeness, at most SHOWN_MAX; meanings that only name another word are left out. `also`: meanings to ask about
    whatever they show (the one `next` picked the word for), in their place among the rest."""
    real = [i for i, s in enumerate(senses) if not rudeness.is_form(s)]
    if not real:
        return []
    main = real[0]
    extra = [i for i in also if i != main and i in real]
    rest = [i for i in real[1:] if i not in extra and _signal(senses[i], scored[i])][:SHOWN_MAX - 1 - len(extra)]
    return [main] + sorted(extra + rest)


def review_item(word, senses, scored, why, pos=(), censored=obscene.CENSORED, also=()):
    """One word of a review file: its meanings to ask about, each with the rules' guess (rudeness.sense_kind),
    and whether the rules smear it whole. `pos`: each meaning's part of speech; `also`: see shown_meanings."""
    common = zipf(word) >= rudeness.COMMON_ZIPF
    _bits, whole, _smeared, _main = rudeness.results(word, senses, scored, censored, common)
    rows = []
    for i in shown_meanings(senses, scored, also):
        s = senses[i]
        rows.append({"key": rudeness.gloss_of(s)[:rudeness.GLOSS_KEY], "pos": pos[i] if i < len(pos) else "",
                     "labels": [rudeness._label(x) for x in s.get("tags", []) + s.get("raw_tags", [])],
                     "gloss": rudeness.gloss_of(s), "guess": rudeness.sense_kind(scored[i])})
    return {"w": word, "why": why, "whole": bool(whole), "senses": rows}


ONE_PART = re.compile(r"[a-z][a-z']*")     # a review asks only about one-part words (asked for, as the word list):
                                          # no hyphenated or spaced entries; contractions ("don't") stay


def pick_sample(words, scored, size=1500, seed=7, weak_words=()):
    """{word: why it was picked}: about size / 10 words of each main kind the rules find, a fifth with a clean main
    meaning and a rude later one, and a fifth found clean with a weak sign (`weak_words`: the likely misses). Half of
    each group comes from its commonest words, half from the rest."""
    import random
    rng = random.Random(seed)
    groups = collections.defaultdict(list)
    for w, sc in scored.items():
        if not ONE_PART.fullmatch(w):
            continue
        kinds = [rudeness.sense_kind(p) for p in sc]
        idx = shown_meanings(words[w], sc)
        if not idx:
            continue
        main = kinds[idx[0]]
        if main != "clean":
            groups[f"the rules say {main}"].append(w)
        elif any(k != "clean" for k in kinds):
            groups["a clean main meaning, a rude later one"].append(w)
    groups["found clean, with a weak sign"] = [w for w in weak_words if w in scored and ONE_PART.fullmatch(w)
                                                and all(rudeness.sense_kind(p) == "clean" for p in scored[w])]
    share = {g: (size // 10 if g.startswith("the rules say") else size // 5) for g in groups}
    picked = {}
    for g in sorted(groups):
        picked.update((w, g) for w in _half_common(set(groups[g]) - set(picked), share[g], rng))
    return picked


def _half_common(words, n, rng):
    """n of `words`: half from the commonest (the top 3n), the rest from all the others."""
    pool = sorted(words, key=lambda w: (-zipf(w), w))
    n = min(n, len(pool))
    top = pool[:n * 3]
    got = rng.sample(top, min(n // 2, len(top)))
    taken = set(got)
    rest = [w for w in pool if w not in taken]
    return got + rng.sample(rest, min(n - len(got), len(rest)))


def weak_signs(words, limit_zipf=2.5):
    """Words with a weak sign of rudeness among their first three meanings (a slang or rude label, a body or
    insult word), common enough to matter: the ones to check for misses."""
    sign = re.compile(r"\b(buttocks|genital|urin|sex|excrement|idiot|stupid|fool)", re.I)
    out = []
    for w, senses in words.items():
        if zipf(w) < limit_zipf or not re.fullmatch(r"[a-z][a-z'-]*", w):
            continue
        for s in senses[:3]:
            if set(s.get("tags", [])) & set(WEAK) or sign.search(rudeness.gloss_of(s)):
                out.append(w)
                break
    return out


# ---- the next review: the words that teach the rules most (active review) -----------------------------------
NEXT_SHARES = (("a candidate signal", 0.3), ("signals disagree", 0.2), ("near the line", 0.3),
               ("no sign at all", 0.2))  # (picked in this order: a word goes to the first group it is in)
NEAR = 1.0                # points from MEANING_MIN (or WHOLE_MIN) that count as near the line
DISAGREE_MIN = 1.5        # both kinds need this many points ...
DISAGREE_SHARE = 0.6      # ... and the second at least this share of the first
RUDE_LABELS = {"vulgar", "derogatory", "offensive", "pejorative", "slur", "ethnic"}   # (Wiktionary's own)
CANDIDATE_MIN = 30        # meanings with a rude label a candidate needs (a topic: meanings in all)
CANDIDATE_SHARE = 0.10    # an unread topic: at least this share of its meanings have a rude label
CANDIDATE_Z = 15.0        # a gloss word: at least this far towards rude meanings (log-odds z-score) ...
CANDIDATE_WORD_SHARE = 0.10   # ... and at least this share of the meanings it is in have a rude label
CANDIDATE_WORDS = 60      # at most this many gloss words
PER_CANDIDATE = 4         # words asked about per candidate signal
PRIOR = 500.0             # the informative prior's size (Monroe et al., "Fightin' Words")
NO_SIGN_ZIPF = 2.5        # a word with no sign at all is asked about only if at least this common


def _labels(sense):
    return {rudeness._label(t) for t in list(sense.get("tags", [])) + list(sense.get("raw_tags", []))}


def _topics(sense):
    return {rudeness._label(t) for t in sense.get("topics", [])}


def _gloss_words(sense):
    return set(re.findall(r"[a-z]+", rudeness.gloss_of(sense).lower())) - rudeness._STOP


def candidates(words):
    """Signals the rules may be missing, mined from Wiktionary's own rude labels (RUDE_LABELS) as a stand-in for the
    answers: ({topic: share of its meanings with a rude label} for topics the rules never read, {gloss word: how far
    it leans to rude meanings} for the words likeliest in a rude meaning, by log-odds with an informative prior)."""
    top_n, top_r, w_r, w_c = (collections.Counter() for _ in range(4))
    for senses in words.values():
        for s in senses:
            if rudeness.is_form(s):
                continue
            rude = bool(_labels(s) & RUDE_LABELS)
            for t in _topics(s):
                top_n[t] += 1
                top_r[t] += rude
            (w_r if rude else w_c).update(_gloss_words(s))
    read = set(rudeness.TOPIC_POINTS) | rudeness.RUDE_CATEGORIES
    topics = {t: top_r[t] / n for t, n in top_n.items()
              if n >= CANDIDATE_MIN and t not in read and top_r[t] / n >= CANDIDATE_SHARE}
    r_all, c_all = sum(w_r.values()), sum(w_c.values())
    total = r_all + c_all
    lean = {}
    for w, n in w_r.items():
        if n < CANDIDATE_MIN:
            continue
        a = PRIOR * (n + w_c[w]) / total
        d = (math.log((n + a) / (r_all + PRIOR - n - a)) -
             math.log((w_c[w] + a) / (c_all + PRIOR - w_c[w] - a)))
        z = d / math.sqrt(1 / (n + a) + 1 / (w_c[w] + a))
        if z >= CANDIDATE_Z and n / (n + w_c[w]) >= CANDIDATE_WORD_SHARE:
            lean[w] = z
    return topics, dict(sorted(lean.items(), key=lambda kv: -kv[1])[:CANDIDATE_WORDS])


def _near(points, line):
    return 0 < points and abs(points - line) <= NEAR


def next_reasons(word, senses, scored, topics, lean, censored=obscene.CENSORED):
    """{group: (why, the meaning's index or None, what it shares with others: spread over, see _spread)} for the
    groups of NEXT_SHARES a word is in."""
    out = {}
    real = [i for i, s in enumerate(senses) if not rudeness.is_form(s)]
    if not real:
        return out
    shown = shown_meanings(senses, scored)
    for i in real[:SHOWN_MAX]:
        if rudeness.sense_kind(scored[i]) != "clean":
            continue
        hit = sorted(_topics(senses[i]) & set(topics)) or sorted(_gloss_words(senses[i]) & set(lean),
                                                                  key=lambda w: -lean[w])
        if hit:
            what = f'the topic "{hit[0]}"' if hit[0] in topics else f'"{hit[0]}" in the meaning'
            out["a candidate signal"] = (f"a candidate signal: {what}", i, hit[0])
            break
    for i in shown:
        pts = sorted(scored[i].values(), reverse=True)
        if len(pts) > 1 and pts[1] >= DISAGREE_MIN and pts[1] >= DISAGREE_SHARE * pts[0]:
            k1, k2 = sorted(scored[i], key=lambda k: -scored[i][k])[:2]
            why = f"signals disagree: {k1} {scored[i][k1]:.1f}, {k2} {scored[i][k2]:.1f}"
            out["signals disagree"] = (why, i, why)
            break
    for i in shown:
        pts = rudeness.sense_points(scored[i])
        if _near(pts, rudeness.MEANING_MIN):
            out["near the line"] = (f"near the line: {pts:.1f} points, {rudeness.MEANING_MIN:g} counts", i,
                                    (rudeness.sense_kind({k: v + NEAR for k, v in scored[i].items()}), round(pts, 1)))
            break
    else:
        pts = rudeness.word_points(scored, censored)
        if _near(pts, rudeness.WHOLE_MIN):
            out["near the line"] = (f"near the line for the whole word: {pts:.1f} points, "
                                    f"{rudeness.WHOLE_MIN:g} smears it", None, ("whole", round(pts, 1)))
    if (not any(any(v > 0 for v in p.values()) for p in scored) and ONE_PART.fullmatch(word)
            and len(word) > 1 and word not in rudeness._STOP
            and not any(rudeness.has_signal(rudeness.compact(s)) for s in senses)
            and zipf(word) >= NO_SIGN_ZIPF):
        out["no sign at all"] = ("no sign at all (to count what the rules miss)", None)
    return out


def pick_next(words, scored, size=300, skip=(), seed=11):
    """{word: (why, [meaning index to ask about])}: the words of NEXT_SHARES, none of `skip` (words reviewed
    already). Each group's share is spread over what its words share (a candidate signal: PER_CANDIDATE words each
    at most; two kinds disagreeing; points near the line), and a group short of words hands its share on."""
    import random
    rng = random.Random(seed)
    topics, lean = candidates(words)
    groups = collections.defaultdict(dict)
    skip = set(skip)
    for w, sc in scored.items():
        if w not in skip and ONE_PART.fullmatch(w):
            for g, why in next_reasons(w, words[w], sc, topics, lean).items():
                groups[g][w] = why
    picked, owed = {}, 0
    for g, share in NEXT_SHARES:
        pool = {w: why for w, why in groups[g].items() if w not in picked}
        n = round(size * share) + owed
        by = collections.defaultdict(list)
        for w, why in pool.items():
            by[why[2] if len(why) > 2 else None].append(w)
        got = _spread(by, n, PER_CANDIDATE if g == "a candidate signal" else n, rng)
        owed = n - len(got)                   # (a group short of words hands its share on)
        picked.update((w, (pool[w][0], [] if pool[w][1] is None else [pool[w][1]])) for w in got)
    return picked


def _spread(by, n, cap, rng):
    """n words from {what they share: [word]}, taken in turn from each (its commonest half first, _half_common), at
    most `cap` from one: "swear 3.5, sexual 3.0" or the gloss word "woman" never fills a group alone."""
    lists = [_half_common(by[k], cap, rng) for k in sorted(by, key=lambda k: (-len(by[k]), str(k)))]
    got = []
    for i in range(cap):
        for ws in lists:
            if i < len(ws) and len(got) < n:
                got.append(ws[i])
    return got


def reviewed(review):
    """The words a review file and its answers already hold."""
    out = set()
    for path in (review, review_answers_path(review)):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        out.add(json.loads(line)["w"])
                    except (ValueError, KeyError, TypeError):
                        continue
        except OSError:
            pass
    return out


def make_next(entries, review, size=300, wn=None, log=print):
    """Add the next words to review (pick_next) to the end of the review file, commonest first: the review window
    goes on from the first word not yet answered."""
    words, poses, family = load(entries)
    scored = rudeness.score_words(words, poses, wn, family)
    picked = pick_next(words, scored, size, skip=reviewed(review))
    with open(review, "a", encoding="utf-8") as f:
        for w in sorted(picked, key=lambda w: (-zipf(w), w)):
            why, also = picked[w]
            f.write(json.dumps(review_item(w, words[w], scored[w], why, poses[w], also=also),
                               ensure_ascii=False) + "\n")
    groups = collections.Counter(why.split(":")[0].split(" (")[0] for why, _a in picked.values())
    log(f"Added {len(picked):,} words to {review}: " + ", ".join(f"{g} {n}" for g, n in sorted(groups.items())))


def make_sample(entries, out, size=1500, wn=None, log=print):
    """Write a review file (JSON lines, commonest first) for `python tierlist.py --review-rude`."""
    words, poses, family = load(entries)
    scored = rudeness.score_words(words, poses, wn, family)
    picked = pick_sample(words, scored, size, weak_words=weak_signs(words))
    with open(out, "w", encoding="utf-8") as f:
        for w in sorted(picked, key=lambda w: (-zipf(w), w)):
            f.write(json.dumps(review_item(w, words[w], scored[w], picked[w], poses[w]), ensure_ascii=False) + "\n")
    log(f"Wrote {len(picked):,} words to {out}: " + ", ".join(
        f"{g} {n}" for g, n in sorted(collections.Counter(picked.values()).items())))


def read_answers(path):
    """{word: {"kinds": {meaning key: kind}, "whole": bool}} from a review's answers file (the last answer for a
    word wins)."""
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                a = json.loads(line)
                out[a["w"]] = {"kinds": dict(zip(a["keys"], a["kinds"])), "whole": bool(a["whole"])}
    return out


def score_answers(answers, words, scored, censored=obscene.CENSORED, show=0, log=print):
    """How often the rules agree with the answers: meaning by meaning, per kind (precision / recall), and on
    smearing the whole word. Returns the share of meanings that agree."""
    agree = total = whole_agree = 0
    tp, fp, fn = collections.Counter(), collections.Counter(), collections.Counter()
    diffs = []
    for w, a in answers.items():
        if w not in words:
            continue
        senses, sc = words[w], scored[w]
        keys = [rudeness.gloss_of(s)[:rudeness.GLOSS_KEY] for s in senses]
        for key, want in a["kinds"].items():
            if key not in keys:
                continue
            got = rudeness.sense_kind(sc[keys.index(key)])
            total += 1
            agree += got == want
            for k in obscene.RUDE_KINDS:
                tp[k] += got == k == want
                fp[k] += got == k != want
                fn[k] += want == k != got
            if got != want:
                diffs.append((-zipf(w), w, key, want, got))
        common = zipf(w) >= rudeness.COMMON_ZIPF
        whole_agree += bool(rudeness.results(w, senses, sc, censored, common)[1]) == a["whole"]
    log(f"{len(answers):,} words answered, {total:,} meanings: the rules agree on {agree / max(1, total):.1%} of "
        f"the meanings, and on smearing the whole word for {whole_agree / max(1, len(answers)):.1%} of the words.")
    log("Each kind: precision / recall (meanings)")
    for k in obscene.RUDE_KINDS:
        log(f"  {k:9} {tp[k] / max(1, tp[k] + fp[k]):6.1%} / {tp[k] / max(1, tp[k] + fn[k]):6.1%}"
            f"   ({tp[k] + fn[k]:,} meanings answered {k})")
    for _z, w, key, want, got in sorted(diffs)[:show]:
        log(f"  {w}: \"{key}\" answered {want}, rules {got}")
    return agree / max(1, total)


def main(argv=None):
    """The command line: fetch, measure, sample, next or answers."""
    ap = argparse.ArgumentParser(description="Measure the rudeness rules against Claude's sorting.")
    ap.add_argument("command", choices=("fetch", "measure", "sample", "next", "answers"))
    ap.add_argument("--size", type=int, default=None, help="sample (1500) / next (300): how many words")
    ap.add_argument("--out", default=os.path.join(ROOT, REVIEW_FILE), help="sample: the review file")
    ap.add_argument("--review", default=os.path.join(ROOT, REVIEW_FILE),
                    help="answers / next: the review file (its answers are rude_review_answers.jsonl beside it)")
    ap.add_argument("--sorting", default=os.path.join(ROOT, "word_categories.tsv"))
    ap.add_argument("--policy", choices=sorted(POLICIES), default="B")
    ap.add_argument("--show", type=int, default=0, help="list this many words where the two differ (commonest)")
    ap.add_argument("--no-wordnet", action="store_true", help="leave WordNet out (it is used when installed)")
    ap.add_argument("--no-links", action="store_true", help="leave out the links between words (the second pass)")
    ap.add_argument("--no-families", action="store_true", help="leave out word families (etymology, derived terms)")
    ap.add_argument("--common", type=float, default=rudeness.COMMON_ZIPF,
                    help="how common a word must be (Zipf) for only strongly labelled meanings to count; 99: never")
    args = ap.parse_args(argv)
    entries = os.path.join(os.path.dirname(os.path.abspath(args.sorting)), "rudeness_entries.jsonl")
    wn = None if args.no_wordnet else rudeness.wordnet()
    if args.command == "fetch":
        fetch(entries)
    elif args.command == "sample":
        make_sample(entries, args.out, args.size or 1500, wn=wn)
    elif args.command == "next":
        make_next(entries, args.review, args.size or 300, wn=wn)
    elif args.command == "answers":
        answers = read_answers(review_answers_path(args.review))
        words, poses, family = load(entries)
        scored = score(words, poses, scope(set(answers), words, family), not args.no_links, wn, family)
        score_answers(answers, words, scored, show=args.show)
    else:
        measure(args.sorting, entries, args.policy, args.show, wn=None if args.no_wordnet else rudeness.wordnet(),
                links=not args.no_links, families=not args.no_families, common_zipf=args.common)
    return 0


if __name__ == "__main__":
    sys.exit(main())
