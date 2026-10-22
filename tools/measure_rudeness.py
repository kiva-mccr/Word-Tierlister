"""Measure the rules in src/rudeness.py against Claude's sorting (OB-6): how often they lead to the same thing.

    python tools/measure_rudeness.py fetch [--sorting word_categories.tsv]    stream kaikki.org's English download
                                                                              (~3 GB, not kept) and keep every
                                                                              lower-case English entry, compactly
    python tools/measure_rudeness.py measure [--policy B] [--show 40] [--no-links] [--no-wordnet] [--no-families]

The compact entries (rudeness_entries.jsonl next to the sorting, about 300 MB) keep each meaning as the program does
(rudeness.compact_entry: the last gloss, the labels, topics and categories the rules read, synonyms, the word it is
a form of, the word family) plus EXAMPLES of its examples. Every word is kept
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
import re
import os
import sys
import urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(ROOT, "src"))
import obscene  # noqa: E402
import rudeness  # noqa: E402
from wordsource import WIKT_URL  # noqa: E402

POLICIES = {"A": set(obscene.RUDE_KINDS), "B": set(obscene.CENSORED)}
OUTCOMES = ("shown", "some", "smeared", "left out")
EXAMPLES = 2                # examples kept per meaning (rudeness.compact_entry), for trying them as a source


def fetch(out, url=WIKT_URL, log=print):
    """Stream the download and keep every lower-case English entry, as the program keeps its rude words'
    (rudeness.compact_entry), with a few examples per meaning."""
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
            senses = rudeness.compact_entry(e, EXAMPLES)
            if senses:
                f.write(json.dumps({"w": w, "senses": senses}, separators=(",", ":")) + "\n")
                kept += 1
    log(f"Kept {kept:,} of {n:,} entries in {out}.")


def load(path):
    """({word: [sense]} as kaikki.org senses (rudeness.expand), {word: [part of speech of each]}, {word: the words it
    is built from} (rudeness.families), {word: [[examples] of each sense]})"""
    words, poses, examples = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    built, derived = collections.defaultdict(list), collections.defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            for c in e["senses"]:
                words[e["w"]].append(rudeness.expand(c))
                poses[e["w"]].append(c.get("pos", ""))
                examples[e["w"]].append(c.get("x", []))
                built[e["w"]] += c.get("e", [])
                derived[e["w"]] += c.get("d", [])
    return words, poses, rudeness.families(built, derived), examples


def only_forms(senses):
    """True if every meaning of a word only names another word ("plural of bitch")."""
    return all(rudeness.is_form(s) for s in senses)


def control_word(w, sorting):
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


def outcome(scored, censored, senses, ticked=obscene.TICKED):
    """What the rules' points lead to for a word, and its meanings' kinds: "left out" (no clean meaning and none of a
    ticked kind: Store._out_sql), "smeared" whole, "some" meanings smeared, or "shown" (rudeness.results)."""
    kinds = [rudeness.sense_kind(x) for x in scored]
    found = set(kinds) or {"clean"}
    if not ({"clean"} | set(ticked)) & found:
        return "left out", kinds
    _bits, whole, _smeared = rudeness.results("", senses, scored, censored)
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
    sub = {w: words[w] for w in need if w in words}
    if links:
        return rudeness.score_words(sub, {w: poses[w] for w in sub}, wn, family)
    return {w: rudeness.score_word(s, poses[w], w, wn) for w, s in sub.items()}


# ---- trying each meaning's examples as a source (the user's idea; not part of the program unless it helps) --------
_TOKEN = re.compile(r"[a-z]+(?:['-][a-z]+)*")
_RUDE_TAGS = {"vulgar", "derogatory", "offensive", "slur", "pejorative"}


def rude_neighbours(words, poses, wn):
    """{word: its rude kinds} for the words with a rude label anywhere (first pass only): what an example's other
    words may be."""
    sub = {w: s for w, s in words.items() if any(_RUDE_TAGS & set(x.get("tags", [])) for x in s)}
    return rudeness.rude_kinds_of({w: rudeness.score_word(s, poses[w], w, wn) for w, s in sub.items()})


def example_points(word, senses, examples, rude, which, vader=None):
    """[{kind: points}] a word's meanings gain from their examples. `which`: "n" other rude words in the example
    (towards their kinds), "p" patterns of use ("you ___", "what a ___": an insult; "what the ___", "___ off", the
    word alone with "!": a swear word), "v" a hostile example by VADER (the word itself taken out): towards Insult;
    "m" only on meanings marked as slang or rude (REGISTER)."""
    stem = re.escape(word.lower())
    w_ = rf"{stem}\w*"
    insult = re.compile(rf"\b(you|what an?|such an?|you're an?|you are an?|stupid|little|fucking|bloody) ({w_})\b")
    swear = re.compile(rf"(\bwhat the {w_}\b|\b{w_} (off|it|you|me|this|that)\b|^\W*{w_}\W*!|\b{w_}!)")
    added = [{} for _ in senses]
    for p, sense, xs in zip(added, senses, examples):
        labels = {lab for lab, _w in rudeness._hedged(list(sense.get("tags", [])))}
        if "m" in which and not labels & rudeness.REGISTER:
            continue
        for x in xs:
            low = x.lower()
            if "n" in which:
                kinds = set()
                for t in set(_TOKEN.findall(low)):
                    if not t.startswith(word.lower()[:4]):
                        kinds |= rude.get(t, set())
                for k in kinds:
                    p[k] = max(p.get(k, 0.0), 1.5)
            if "p" in which:
                if insult.search(low):
                    p["insult"] = max(p.get("insult", 0.0), 2.0)
                if swear.search(low):
                    p["swear"] = max(p.get("swear", 0.0), 2.0)
            if "v" in which and vader is not None:
                if vader.polarity_scores(re.sub(w_, "", low))["compound"] <= -0.5:
                    p["insult"] = max(p.get("insult", 0.0), 1.5)
    return added


def measure(sorting, entries, policy="B", show=0, log=print, wn=None, links=True, families=True, examples=""):
    censored = POLICIES[policy]
    words, poses, family, ex = load(entries)
    family = family if families else {}
    claude = read_sorting(sorting)
    order = {w: i for i, w in enumerate(claude)}
    base = [w for w, v in claude.items() if not v[3].startswith("form of ") and w in words and not only_forms(words[w])]
    control = [w for w in words if control_word(w, claude) and not only_forms(words[w])]
    scored = score(words, poses, scope(set(base) | set(control), words, family), links, wn, family)
    if examples:
        vader = None
        if "v" in examples:
            from nltk.sentiment.vader import SentimentIntensityAnalyzer
            vader = SentimentIntensityAnalyzer()
        rude = rude_neighbours(words, poses, wn) if "n" in examples else {}
        for w in set(base) | set(control):
            for p, a in zip(scored[w], example_points(w, words[w], ex[w], rude, examples, vader)):
                rudeness._add(p, a)
    table, tp, fp, fn = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    agree = common = common_agree = 0
    diffs = []
    for w in base:
        kind, _conf, meanings = claude[w][:3]
        ref = claude_outcome(kind, meanings, censored)
        k = max(1, len(meanings))
        got, kinds = outcome(scored[w][:k], censored, words[w][:k])
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
        f"{', examples ' + examples if examples else ''}"
        f": {len(base):,} of the sorting's "
        "words have Wiktionary entries.")
    log(f"Same outcome: {agree / len(base):.1%} (the commonest 5,000 of the sorting: {common_agree / max(1, common):.1%})")
    log("Rows: Claude's answers; columns: the rules.  " + "  ".join(f"{o:>9}" for o in OUTCOMES))
    for r in OUTCOMES:
        log(f"  {r:>9}" + "".join(f"{table[r, c]:>11,}" for c in OUTCOMES))
    log("Each kind (a word has it): precision / recall")
    for k in obscene.RUDE_KINDS:
        log(f"  {k:9} {tp[k] / max(1, tp[k] + fp[k]):6.1%} / {tp[k] / max(1, tp[k] + fn[k]):6.1%}"
            f"   ({tp[k] + fn[k]:,} words have it by Claude)")
    flagged = collections.Counter(outcome(scored[w], censored, words[w])[0] for w in control)
    log(f"Control words ({len(control):,}, taken to be clean): " +
        ", ".join(f"{o} {flagged[o] / max(1, len(control)):.1%}" for o in OUTCOMES))
    for _i, w, ref, got in sorted(diffs)[:show]:
        log(f"  {w}: Claude {ref}, rules {got}")
    return agree / len(base)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Measure the rudeness rules against Claude's sorting.")
    ap.add_argument("command", choices=("fetch", "measure"))
    ap.add_argument("--sorting", default=os.path.join(ROOT, "word_categories.tsv"))
    ap.add_argument("--policy", choices=sorted(POLICIES), default="B")
    ap.add_argument("--show", type=int, default=0, help="list this many words where the two differ (commonest)")
    ap.add_argument("--no-wordnet", action="store_true", help="leave WordNet out (it is used when installed)")
    ap.add_argument("--no-links", action="store_true", help="leave out the links between words (the second pass)")
    ap.add_argument("--no-families", action="store_true", help="leave out word families (etymology, derived terms)")
    ap.add_argument("--examples", default="", help="try the meanings' examples: n (rude words in them), p (patterns of "
                                                   "use), v (VADER, needs nltk's vader_lexicon), m (marked meanings only)")
    args = ap.parse_args(argv)
    entries = os.path.join(os.path.dirname(os.path.abspath(args.sorting)), "rudeness_entries.jsonl")
    if args.command == "fetch":
        fetch(entries)
    else:
        measure(args.sorting, entries, args.policy, args.show, wn=None if args.no_wordnet else rudeness.wordnet(),
                links=not args.no_links, families=not args.no_families, examples=args.examples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
