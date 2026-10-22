"""Measure the rules in src/rudeness.py against Claude's sorting (OB-6): how often they lead to the same thing.

    python tools/measure_rudeness.py fetch [--sorting word_categories.tsv]    stream kaikki.org's English download
                                                                              (~3 GB, not kept) and keep every
                                                                              lower-case English entry, compactly
    python tools/measure_rudeness.py measure [--policy B] [--show 40] [--no-links] [--no-wordnet]

The compact entries (rudeness_entries.jsonl next to the sorting, about 400 MB) keep per meaning only what the
rules read: the last gloss, labels, topics, categories, synonyms and the word it is a form of. Every word is kept
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
import os
import sys
import urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(ROOT, "src"))
import obscene  # noqa: E402
import rudeness  # noqa: E402
from wordsource import WIKT_URL  # noqa: E402

POLICIES = {"A": set(obscene.RUDE_KINDS), "B": {"crude", "swear", "sexual", "slur"}}
OUTCOMES = ("shown", "some", "smeared", "left out")
# labels about grammar, and categories about the page rather than the meaning: not kept
GRAMMAR = {"countable", "uncountable", "transitive", "intransitive", "not-comparable", "plural", "singular",
           "ambitransitive", "participle", "past", "present", "comparable", "in-plural", "plural-only",
           "plural-normally", "attributive", "collective", "form-of", "alt-of"}
PAGE_CATEGORIES = ("Pages", "English entries", "Terms with", "Requests", "English terms with", "English lemmas",
                   "English nouns", "English verbs", "English adjectives", "English adverbs", "English countable",
                   "English uncountable", "English links", "Entries", "Translation", "Quotation", "Rhymes",
                   "English multiword", "English compound", "English 1", "English 2", "English 3", "English 4",
                   "English heteronyms", "English undefined", "English plurals", "English words", "English pluralia")


def compact(e):
    """One kaikki.org entry, cut down to what the rules read, or None."""
    w = e.get("word", "")
    if e.get("lang_code") != "en" or not w or w != w.lower():
        return None
    senses = []
    for s in e.get("senses", []):
        g = (s.get("glosses") or [""])[-1]
        if not g:
            continue
        r = {"g": g[:160]}
        t = [x for x in s.get("tags", []) + s.get("raw_tags", []) if x not in GRAMMAR]
        c = [c.get("name") if isinstance(c, dict) else c for c in s.get("categories", [])]
        c = [x for x in c if x and not x.startswith(PAGE_CATEGORIES) and " terms " not in x]
        syn = [x.get("word") for x in s.get("synonyms", []) if x.get("word")]
        f = (s.get("form_of") or s.get("alt_of") or [{}])[0].get("word")
        for key, val in (("t", t), ("p", s.get("topics")), ("c", c), ("s", syn), ("f", f)):
            if val:
                r[key] = val
        senses.append(r)
    return {"w": w, "pos": e.get("pos"), "senses": senses} if senses else None


def fetch(out, url=WIKT_URL, log=print):
    """Stream the download and keep every lower-case English entry, compactly."""
    n = kept = 0
    with urllib.request.urlopen(url, timeout=60) as r, open(out, "w", encoding="utf-8") as f:
        for raw in r:
            n += 1
            if n % 200000 == 0:
                log(f"  {n:,} entries read, {kept:,} kept")
            try:
                rec = compact(json.loads(raw))
            except ValueError:
                continue
            if rec:
                f.write(json.dumps(rec, separators=(",", ":")) + "\n")
                kept += 1
    log(f"Kept {kept:,} of {n:,} entries in {out}.")


def load(path):
    """({word: [sense]} as kaikki.org senses, {word: [part of speech of each]})"""
    words, poses = collections.defaultdict(list), collections.defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            for r in e["senses"]:
                words[e["w"]].append({"glosses": [r["g"]], "tags": r.get("t", []), "topics": r.get("p", []),
                                      "categories": r.get("c", []), "synonyms": r.get("s", []),
                                      **({"form_of": [{"word": r["f"]}]} if "f" in r else {})})
                poses[e["w"]].append(e.get("pos") or "")
    return words, poses


def is_form(senses):
    return all(s.get("form_of") for s in senses)


def control_word(w, sorting):
    return w not in sorting and int(hashlib.md5(w.encode()).hexdigest(), 16) % 40 == 0


def scope(targets, words):
    """The words the two passes need for `targets`: themselves, their synonyms, and the words whose meanings list
    them."""
    need = set(targets)
    for w in targets:
        for s in words.get(w, ()):
            need.update(rudeness.synonyms(s))
    for w, senses in words.items():
        if any(t in targets for s in senses for t in rudeness.synonyms(s)):
            need.add(w)
    return need


def outcome(scored, censored, senses=(), ticked=obscene.TICKED):
    """What the rules' points lead to for a word, and its meanings' kinds."""
    kinds = [rudeness.sense_kind(x) for x in scored]
    found = set(kinds) or {"clean"}
    if not ({"clean"} | set(ticked)) & found:
        return "left out", kinds
    forms = [rudeness.is_form(s) for s in senses] if senses else None
    if rudeness.word_points(scored, censored, forms) >= rudeness.WHOLE_MIN:
        return "smeared", kinds
    return ("some" if found & censored else "shown"), kinds


def claude_outcome(kind, meanings, censored, ticked=obscene.TICKED):
    """What Claude's answers lead to under the same policy (obscene.outcome's rules, only `censored` smeared)."""
    found = obscene.word_kinds(kind, meanings)
    if not ({"clean", obscene.UNSURE} | set(ticked)) & found:
        return "left out"
    listed = set(meanings) or {"clean"}
    if (meanings and meanings[0] in censored) or listed <= censored or (kind in censored and listed == {"clean"}):
        return "smeared"
    return "some" if found & censored else "shown"


def score(words, poses, need, links, wn):
    sub = {w: words[w] for w in need if w in words}
    if links:
        return rudeness.score_words(sub, {w: poses[w] for w in sub}, wn)
    return {w: rudeness.score_word(s, poses[w], w, wn) for w, s in sub.items()}


def measure(sorting, entries, policy="B", show=0, log=print, wn=None, links=True):
    censored = POLICIES[policy]
    words, poses = load(entries)
    claude = obscene.read_categories(sorting)
    order = {w: i for i, w in enumerate(claude)}
    base = [w for w, v in claude.items() if not v[3].startswith("form of ") and w in words and not is_form(words[w])]
    control = [w for w in words if control_word(w, claude) and not is_form(words[w])]
    scored = score(words, poses, scope(set(base) | set(control), words), links, wn)
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
        want, have = obscene.word_kinds(kind, meanings) - {"clean"}, set(kinds) - {"clean"}
        for k in obscene.RUDE_KINDS:
            tp[k] += k in want and k in have
            fp[k] += k not in want and k in have
            fn[k] += k in want and k not in have
        if ref != got:
            diffs.append((order[w], w, ref, got))
    log(f"Policy {policy}{', WordNet' if wn else ''}{', links' if links else ''}: {len(base):,} of the sorting's "
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
    args = ap.parse_args(argv)
    entries = os.path.join(os.path.dirname(os.path.abspath(args.sorting)), "rudeness_entries.jsonl")
    if args.command == "fetch":
        fetch(entries)
    else:
        measure(args.sorting, entries, args.policy, args.show,
                wn=None if args.no_wordnet else rudeness.wordnet(), links=not args.no_links)
    return 0


if __name__ == "__main__":
    sys.exit(main())
