"""Measure the rules in src/rudeness.py against Claude's sorting (OB-6): how often they lead to the same thing.

    python tools/measure_rudeness.py fetch [--sorting word_categories.tsv]     stream kaikki.org's English download
                                                                               (~3 GB, not kept) and keep only
                                                                               those words' entries, and 1 in 40
                                                                               other words as a control
    python tools/measure_rudeness.py measure [--policy B] [--show 40]          the rules against the sorting

Kept in rudeness_entries.jsonl next to the sorting (about 80 MB). The comparison uses the meanings Claude saw (the
first few of each word) and a censoring policy, the same for both sides:
    A   every rude kind is censored (Clinical, Crude, Swear word, Insult, Sexual, Slur)
    B   only Crude, Swear word, Sexual and Slur (Clinical and Insult words shown as they are)
The control words were never candidates for the sorting, so they are taken to be clean: the share the rules flag
is their false-alarm rate. Never part of the program.
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


def fetch(sorting, out, url=WIKT_URL, log=print):
    """Stream the download and keep the sorting's words (and 1 in 40 other lower-case words, marked control)."""
    words = set(obscene.read_categories(sorting))
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
            control = w not in words and int(hashlib.md5(w.encode()).hexdigest(), 16) % 40 == 0
            if w not in words and not control:
                continue
            senses = [{k: s[k] for k in ("glosses", "tags", "raw_tags", "topics", "categories", "form_of", "alt_of")
                       if k in s} for s in e.get("senses", [])]
            f.write(json.dumps({"word": w, "pos": e.get("pos"), "control": control, "senses": senses}) + "\n")
            kept += 1
    log(f"Kept {kept:,} of {n:,} entries in {out}.")


def load(path):
    """({word: [(sense, pos)] with glosses, in order}, {control words})"""
    words, control = collections.defaultdict(list), set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            words[e["word"]] += [(s, e.get("pos") or "") for s in e["senses"] if s.get("glosses")]
            if e["control"]:
                control.add(e["word"])
    return words, control


def is_form(senses):
    return all(s.get("form_of") or s.get("alt_of") for s, _p in senses)


def rules_outcome(word, senses, censored, ticked=obscene.TICKED):
    """What the rules lead to for a word, and its meanings' kinds."""
    scored = rudeness.score_word([s for s, _ in senses], [p for _, p in senses], word)
    kinds = [rudeness.sense_kind(x) for x in scored]
    found = set(kinds) or {"clean"}
    if not ({"clean"} | set(ticked)) & found:
        return "left out", kinds
    if rudeness.word_points(scored, censored) >= rudeness.WHOLE_MIN:
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


def measure(sorting, entries, policy="B", show=0, log=print):
    censored = POLICIES[policy]
    words, control = load(entries)
    claude = obscene.read_categories(sorting)
    order = {w: i for i, w in enumerate(claude)}
    base = [w for w, v in claude.items() if not v[3].startswith("form of ") and w in words and not is_form(words[w])]
    table, tp, fp, fn = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    agree = common = common_agree = 0
    diffs = []
    for w in base:
        kind, _conf, meanings = claude[w][:3]
        ref = claude_outcome(kind, meanings, censored)
        got, kinds = rules_outcome(w, words[w][:max(1, len(meanings))], censored)
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
    log(f"Policy {policy}: {len(base):,} of the sorting's words have Wiktionary entries.")
    log(f"Same outcome: {agree / len(base):.1%} (the commonest 5,000 of the sorting: {common_agree / max(1, common):.1%})")
    log("Rows: Claude's answers; columns: the rules.  " + "  ".join(f"{o:>9}" for o in OUTCOMES))
    for r in OUTCOMES:
        log(f"  {r:>9}" + "".join(f"{table[r, c]:>11,}" for c in OUTCOMES))
    log("Each kind (a word has it): precision / recall")
    for k in obscene.RUDE_KINDS:
        log(f"  {k:9} {tp[k] / max(1, tp[k] + fp[k]):6.1%} / {tp[k] / max(1, tp[k] + fn[k]):6.1%}"
            f"   ({tp[k] + fn[k]:,} words have it by Claude)")
    flagged = collections.Counter(rules_outcome(w, words[w], censored)[0] for w in control if not is_form(words[w]))
    total = sum(flagged.values())
    log(f"Control words ({total:,}, taken to be clean): " +
        ", ".join(f"{o} {flagged[o] / max(1, total):.1%}" for o in OUTCOMES))
    for _i, w, ref, got in sorted(diffs)[:show]:
        log(f"  {w}: Claude {ref}, rules {got}")
    return agree / len(base)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Measure the rudeness rules against Claude's sorting.")
    ap.add_argument("command", choices=("fetch", "measure"))
    ap.add_argument("--sorting", default=os.path.join(ROOT, "word_categories.tsv"))
    ap.add_argument("--policy", choices=sorted(POLICIES), default="B")
    ap.add_argument("--show", type=int, default=0, help="list this many words where the two differ (commonest)")
    args = ap.parse_args(argv)
    entries = os.path.join(os.path.dirname(os.path.abspath(args.sorting)), "rudeness_entries.jsonl")
    if args.command == "fetch":
        fetch(args.sorting, entries)
    else:
        measure(args.sorting, entries, args.policy, args.show)
    return 0


if __name__ == "__main__":
    sys.exit(main())
