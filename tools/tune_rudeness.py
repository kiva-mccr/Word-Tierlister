"""Tune the numbers in src/rudeness.py against the review's answers (OB-10, a developer tool; asked for: "can it
also optimize the rules statistically?"; the window picked from mock-ups).

    python tools/tune_rudeness.py [--review rude_review.jsonl] [--entries rudeness_entries.jsonl] [--rounds 60]

Rules only stays: the program never reads the answers. This only changes the numbers the rules already have (the
points a label, topic, wording or WordNet meaning gives, the thresholds and weights: PARAMS), and Keep writes them
into src/rudeness.py for a person to read over and commit.

How it works:
  * the answered words (rude_review_answers.jsonl beside the review file) are split into 5 parts; for each part the
    numbers are tuned on the other 4 and tested on it, so every answered word is tested once, never by numbers
    tuned on it; a sixth run tunes on every answered word: Keep takes its numbers at the round the tests liked best;
  * a round tries every number a step up and a step down (then JUMP steps), keeping a change when it lowers the
    error on the words tuned on (coordinate descent); a step that helps no way halves, so the search settles;
  * the error is 100% minus the average F1 of the kinds (Clean and each rude kind, meaning by meaning, as
    rudeness.sense_kind gives them) and of smearing the whole word (rudeness.results): Clinical counts as much as
    Clean, though most meanings are clean;
  * the guard scores every word the program scores (rudeness.score_saved on the words with a sign of rudeness) with
    the rules now and with the best numbers: how many words each kind and smearing whole would cover; a kind more
    than doubling is marked, and Keep asks first;
  * "still wrong": the tested meanings the best numbers still get wrong (no number fixes those: ideas for new
    rules), all written to rude_tune_misses.txt beside the answers.

Scoring is made fast (Fast): what does not depend on the numbers (WordNet's matches, the regular expressions, the
words of a definition) is worked out once; the second pass runs only for the answered words. The words whose first
pass the second needs (their synonyms, families, forms, parts, the words listing them) are scored every time.
"""
import argparse
import collections
import contextlib
import copy
import hashlib
import json
import os
import queue
import re
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, TOOLS)
import obscene  # noqa: E402
import rudeness  # noqa: E402
from constants import REVIEW_FILE, review_answers_path  # noqa: E402

KINDS = ("clean",) + tuple(obscene.RUDE_KINDS)
PARTS = 5                       # the answered words are tested in this many parts
ALL = PARTS                     # (the run that tunes on every answered word)
STEP = 0.2                      # a number's first step: 20% of it (a factor's: 0.2)
MIN_STEP = 0.02                 # a step this small is settled
JUMP = 4                        # a step that helps neither way is tried this many times as far before it halves
                                # (the error moves in jumps: a small step often changes no meaning's kind)
DOUBLED = 2.0                   # the guard marks a kind that covers this many times the words it does now
MISSES_FILE = "rude_tune_misses.txt"

# the numbers tuned: plain numbers (name), one entry of a table (table, key, kind), or a factor on every entry of a
# kind in a table (table, "*", kind: its entries scaled together, written back one by one)
SCALARS = ("MEANING_MIN", "WHOLE_MIN", "OTHERS_WEIGHT", "OTHERS_CAP", "CATEGORY_ALONE", "SOFTENED", "LINK_OUT",
           "LINK_IN", "LINK_IN_MAX", "FAMILY_POINTS", "SLANG_BODY", "COMMON_ZIPF")
SHARES = {"OTHERS_WEIGHT", "CATEGORY_ALONE", "SOFTENED"}          # (never above 1)
FACTOR_TABLES = ("TOPIC_POINTS", "WORDING", "WORDNET_POINTS")
FACTOR_RANGE = (0.25, 4.0)


def _table_kinds(name):
    """The kinds a table gives points to, in RUDE_KINDS' order."""
    tables = _tables(name)
    have = {k for t in tables for k in t}
    return [k for k in obscene.RUDE_KINDS if k in have]


def _tables(name):
    """The {kind: points} dicts of a table, in order (WORDING's sit beside their patterns)."""
    table = getattr(rudeness, name)
    return [t for _p, t in table] if name == "WORDING" else list(table.values())


def params():
    """Every number tuned (see SCALARS etc.), as names: "MEANING_MIN", "TAG_POINTS vulgar swear",
    "TOPIC_POINTS * clinical"."""
    out = list(SCALARS)
    for tag, table in rudeness.TAG_POINTS.items():
        out += [f"TAG_POINTS {tag} {k}" for k in table]
    out += [f"{name} * {k}" for name in FACTOR_TABLES for k in _table_kinds(name)]
    out += [f"GROUP_POINTS {k}" for k in rudeness.GROUP_POINTS]
    return out


def snapshot():
    """The rules' numbers now: {param: value} (a factor is 1.0) and the tables they scale (copied)."""
    values = {}
    for p in params():
        parts = p.split(" ")
        if len(parts) == 1:
            values[p] = float(getattr(rudeness, p))
        elif parts[1] == "*":
            values[p] = 1.0
        elif parts[0] == "TAG_POINTS":
            values[p] = float(rudeness.TAG_POINTS[parts[1]][parts[2]])
        else:
            values[p] = float(getattr(rudeness, parts[0])[parts[1]])
    base = {name: copy.deepcopy(_tables(name)) for name in FACTOR_TABLES}
    return values, base


_applied = {}                   # the numbers apply() last put in (read by fast()'s memory of each meaning's points)


def apply(values, base):
    """Put `values` into the rules (rudeness's globals and tables, changed in place)."""
    _applied.update(values)
    for p, v in values.items():
        parts = p.split(" ")
        if len(parts) == 1:
            setattr(rudeness, p, v)
        elif parts[1] == "*":
            for table, orig in zip(_tables(parts[0]), base[parts[0]]):
                if parts[2] in orig:
                    table[parts[2]] = orig[parts[2]] * v
        elif parts[0] == "TAG_POINTS":
            rudeness.TAG_POINTS[parts[1]][parts[2]] = v
        else:
            getattr(rudeness, parts[0])[parts[1]] = v


def bounds(p, start):
    """The range a number may move in."""
    if " * " in p:
        return FACTOR_RANGE
    if p == "COMMON_ZIPF":
        return 3.0, 7.0
    if p in SHARES:
        return 0.0, 1.0
    if p in ("MEANING_MIN", "WHOLE_MIN"):
        return 1.0, 8.0
    return 0.0, max(2 * start, start + 3)


# ---- fast scoring -------------------------------------------------------------------------------------------------
class _Memo:
    """A compiled pattern whose answers are remembered (they never depend on the numbers)."""
    def __init__(self, pattern):
        self.pattern, self.flags, self._p, self._seen = pattern.pattern, pattern.flags, pattern, {}

    def _ask(self, how, text, *extra):
        key = (how, text, extra)
        if key not in self._seen:
            self._seen[key] = getattr(self._p, how)(*extra, text) if how == "sub" else getattr(self._p, how)(text)
        return self._seen[key]

    def search(self, text):
        return self._ask("search", text)

    def match(self, text):
        return self._ask("match", text)

    def sub(self, repl, text):
        return self._ask("sub", text, repl)


class _Syn:
    """A WordNet meaning by name (the tuning processes never load WordNet: its matches are worked out first)."""
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


_dead = {}                      # (inside fast(): the words none of whose meanings can score, as scored: never again)
_PATTERNS = ("_EXAMPLES", "_NOT_A_PERSON", "IDENTITY", "_RESPELLING", "_BODY", "_WASTE", "_LEAD", "FORM_GLOSS")


@contextlib.contextmanager
def fast(wn_matches=None, wn_names=None, words=None, poses=None, data=None):
    """Score fast inside: rudeness's patterns remember their answers, a definition's words are worked out once, and
    WordNet is read from `wn_matches` ({(word, gloss, pos): synset name or None}) and `wn_names` ({synset name:
    (the WORDNET_POINTS names it is or is a kind of, WordNet calls it slang)}) instead of WordNet (none: no WordNet).
    The points are always read from the tables as they are now (rudeness._signals keeps them: bypassed). `words`
    ({word: [sense]}, `poses` beside them): a meaning of theirs that scores nothing now scores nothing whatever the
    numbers (every point comes from a table entry, and an entry always leaves its kind behind, if only at 0), so it
    is not scored again: most meanings. `data` (its "start" numbers and "base" tables): which numbers each other
    meaning's points hang on is found by moving each number on its own, and its points are remembered for the values
    of those (a round moves one number at a time: only the meanings that number reaches are scored again)."""
    saved = {n: getattr(rudeness, n) for n in _PATTERNS + ("WORDING", "GROUP", "_content", "_hedged",
                                                           "wordnet_match", "_synset_signals", "score_sense", "sense_kind",
                                                           "plain_group_name", "incoming_links", "rude_kinds_of")}
    content, hedged = {}, {}
    content_of, hedged_of = rudeness._content, rudeness._hedged

    def _content(text):
        if text not in content:
            content[text] = frozenset(content_of(text))
        return content[text]

    def _hedged(labels):
        key = tuple(labels)
        if key not in hedged:
            hedged[key] = hedged_of(key)
        return hedged[key]

    def wordnet_match(word, gloss, pos, _wn):
        name = (wn_matches or {}).get((word, gloss, pos))
        return _Syn(name) if name else None

    def _synset_signals(syn):
        names, slang = (wn_names or {}).get(syn.name(), ((), False))
        points = {}
        for n in names:
            rudeness._add(points, rudeness.WORDNET_POINTS[n])
        return points, slang
    try:
        for n in _PATTERNS:
            setattr(rudeness, n, _Memo(saved[n]))
        rudeness.WORDING = [(_Memo(p), t) for p, t in saved["WORDING"]]
        rudeness.GROUP = [_Memo(p) for p in saved["GROUP"]]
        rudeness._content, rudeness._hedged = _content, _hedged
        rudeness.wordnet_match, rudeness._synset_signals = wordnet_match, _synset_signals
        if words:
            score_sense = saved["score_sense"]
            wn = "wn" if wn_matches else None
            nothing = {id(s) for w, senses in words.items()
                       for s, pos in zip(senses, poses.get(w, [""] * len(senses))) if not score_sense(s, pos, w, wn)}

            sense_kind, plain_group_name, plain = saved["sense_kind"], saved["plain_group_name"], {}

            deps, memory = {}, {}
            if data is not None:
                start, base = data["start"], data["base"]
                apply(start, base)
                scorable = [(s, pos, w) for w, senses in words.items()
                            for s, pos in zip(senses, poses.get(w, [""] * len(senses))) if id(s) not in nothing]
                was = {id(s): score_sense(s, pos, w, wn) for s, pos, w in scorable}
                deps = {id(s): [] for s, _p, _w in scorable}
                for p, v in start.items():
                    apply({p: v * 1.37 + 0.11}, base)
                    for s, pos, w in scorable:
                        if score_sense(s, pos, w, wn) != was[id(s)]:
                            deps[id(s)].append(p)
                    apply({p: v}, base)

            def quick(sense, pos="", word="", wn=None, identity=False):
                key = id(sense)
                if key in nothing:
                    return {}
                if key not in deps:
                    return score_sense(sense, pos, word, wn, identity)
                at = (identity,) + tuple(_applied[p] for p in deps[key])
                seen = memory.setdefault(key, {})
                if at not in seen:
                    if len(seen) > 8:
                        seen.clear()
                    seen[at] = score_sense(sense, pos, word, wn, identity)
                return dict(seen[at])

            def quick_kind(points):
                return sense_kind(points) if points else "clean"

            def quick_plain(sense, points):           # (with no points it hangs on the meaning alone)
                if points:
                    return plain_group_name(sense, points)
                if id(sense) not in plain:
                    plain[id(sense)] = plain_group_name(sense, points)
                return plain[id(sense)]
            live = [w for w, senses in words.items() if any(id(s) not in nothing for s in senses)]
            linkers = [(w, i, rudeness.gloss_of(s), rudeness.synonyms(s)) for w in live
                       for i, s in enumerate(words[w]) if id(s) not in nothing and rudeness.synonyms(s)]

            def rude_kinds_of(first):                 # (as rudeness's, over the words that can score at all)
                out = {}
                for w in live:
                    kinds = {quick_kind(p) for p in first[w]} - {"clean"}
                    if kinds:
                        out[w] = kinds
                return out

            def incoming_links(_words, first):        # (as rudeness's, over the meanings that can score at all)
                out = {}
                for w, i, gloss, syns in linkers:
                    kind = quick_kind(first[w][i])
                    if kind != "clean":
                        for syn in syns:
                            if syn != w:
                                out.setdefault(syn, []).append((kind, gloss, w))
                return out
            rudeness.score_sense, rudeness.sense_kind, rudeness.plain_group_name = quick, quick_kind, quick_plain
            rudeness.rude_kinds_of, rudeness.incoming_links = rude_kinds_of, incoming_links
            alive = set(live)
            _dead.update({w: [{} for _ in senses] for w, senses in words.items() if w not in alive})
        yield
    finally:
        for n, v in saved.items():
            setattr(rudeness, n, v)
        _dead.clear()


def wordnet_tables(words, poses, wn, progress=None):
    """(wn_matches, wn_names) for fast(): each meaning's WordNet match, and what each matched meaning is;
    progress(share of the words done) now and then."""
    matches, names = {}, {}
    if wn is None:
        return matches, names
    wanted = set(rudeness.WORDNET_POINTS)
    step = max(1, len(words) // 200)
    for i, (w, senses) in enumerate(words.items()):
        if progress and i % step == 0:
            progress(i / max(1, len(words)))
        for s, pos in zip(senses, poses.get(w, [""] * len(senses))):
            gloss = rudeness.gloss_of(s)
            syn = rudeness.wordnet_match(w, gloss, pos, wn)
            if syn is None:
                continue
            matches[(w, gloss, pos)] = syn.name()
            if syn.name() not in names:
                kinds = {syn.name()}
                for path in syn.hypernym_paths():
                    kinds.update(h.name() for h in path)
                usage = {d.name() for d in syn.usage_domains()}
                names[syn.name()] = (tuple(sorted((kinds | usage) & wanted)), bool(usage & rudeness.WORDNET_SLANG))
    return matches, names


def scope(targets, words, family):
    """The words the two passes read for `targets` (measure_rudeness.scope, plus the words they are forms of and the
    parts of hyphenated ones)."""
    import measure_rudeness
    need = measure_rudeness.scope(targets, words, family)
    for w in targets:
        need.update(t for s in words.get(w, ()) if (t := rudeness.form_target(s)))
        if "-" in w and " " not in w:
            need.update(p for p in w.split("-") if p)
    return {w for w in need if w in words}


def score_targets(data, targets):
    """{word: [{kind: points}]} for `targets` (both passes), from `data`'s words."""
    words, poses = data["words"], data["poses"]
    wn = "wn" if data["wn_matches"] else None
    first = {w: _dead[w] if w in _dead else rudeness.score_word(s, poses[w], w, wn) for w, s in words.items()}
    rude, incoming = rudeness.rude_kinds_of(first), rudeness.incoming_links(words, first)
    return {w: rudeness.second_pass(w, words[w], first, rude, incoming, data["family"].get(w, ())) for w in targets}


# ---- the answers and the error ------------------------------------------------------------------------------------
def answer_pairs(answers, words):
    """{word: ([(meaning index, kind answered)], whole answered)} for the answers whose meanings are found."""
    out = {}
    for w, a in answers.items():
        if w not in words:
            continue
        keys = [rudeness.gloss_of(s)[:rudeness.GLOSS_KEY] for s in words[w]]
        pairs = [(keys.index(k), kind) for k, kind in a["kinds"].items() if k in keys and kind in KINDS]
        if pairs:
            out[w] = (pairs, bool(a["whole"]))
    return out


def part_of(word):
    """Which of the PARTS a word is tested in (fixed: by its letters)."""
    return int(hashlib.md5(word.encode()).hexdigest(), 16) % PARTS


def tally(data, scored, words_in):
    """{class: [tp, fp, fn]} over `words_in`: each kind meaning by meaning, and "whole" (smearing the word)."""
    t = {c: [0, 0, 0] for c in KINDS + ("whole",)}
    for w in words_in:
        pairs, whole = data["answers"][w]
        sc = scored[w]
        for i, want in pairs:
            got = rudeness.sense_kind(sc[i])
            if got == want:
                t[got][0] += 1
            else:
                t[got][1] += 1
                t[want][2] += 1
        common = data["zipf"].get(w, 0.0) >= rudeness.COMMON_ZIPF
        got = bool(rudeness.results(w, data["words"][w], sc, obscene.CENSORED, common)[1])
        if got and whole:
            t["whole"][0] += 1
        elif got:
            t["whole"][1] += 1
        elif whole:
            t["whole"][2] += 1
    return t


def error(t):
    """100% minus the average F1 of the classes answered at least once (tally)."""
    f1 = [2 * tp / (2 * tp + fp + fn) for tp, fp, fn in t.values() if tp + fn]
    return 100.0 * (1 - sum(f1) / len(f1)) if f1 else 0.0


def evaluate(data, values, words_in):
    """The error and tally of `values` over `words_in`."""
    apply(values, data["base"])
    t = tally(data, score_targets(data, words_in), words_in)
    return error(t), t


def say(line):
    """A line for whoever started the tuner (the program's Tune the rules bubble reads them for its ring)."""
    try:
        print(line, flush=True)
    except (OSError, ValueError, AttributeError):     # (no stdout, or nobody reading it any more)
        pass


def tune_round(data, values, steps, train, order, progress=None):
    """One round of the search over `train`: every number a step up and down (in `order`), a change kept when it
    lowers the error, a step that helps neither way halved; progress(numbers tried, of) after each number. Returns
    (values, steps, error on train)."""
    values, steps = dict(values), dict(steps)
    best, _t = evaluate(data, values, train)
    for i, p in enumerate(order, 1):
        if progress:
            progress(i - 1, len(order))
        if steps[p] < MIN_STEP:
            continue
        lo, hi = data["bounds"][p]
        size = steps[p] * (1.0 if " * " in p else max(abs(data["start"][p]), 0.5))
        moved = False
        for v in (values[p] + size, values[p] - size, values[p] + JUMP * size, values[p] - JUMP * size):
            v = round(min(hi, max(lo, v)), 4)
            if v == values[p]:
                continue
            err, _t = evaluate(data, {**values, p: v}, train)
            if err < best - 1e-9:
                best, values[p], moved = err, v, True
                break
        steps[p] = steps[p] if moved else steps[p] / 2
    if progress:
        progress(len(order), len(order))
    apply(values, data["base"])
    return values, steps, best


# ---- the tuning processes ------------------------------------------------------------------------------------------
_data = {}


def lower_priority():
    """This process yields to the window (and to the rest of the computer): the tuner's helper processes call it."""
    try:
        if hasattr(os, "nice"):
            os.nice(10)
        elif sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # below normal
    except (OSError, AttributeError):
        pass


def _start(data, progress=None):
    """A tuning process's start: at a lower priority, then _keep; `progress` (a queue) hears each number tried."""
    lower_priority()
    _keep(data)
    _data["_progress"] = progress


def _keep(data):
    """Keep the data, make scoring fast for good (a tuning process, or this one for Inline)."""
    _data.update(data)
    _data["_fast"] = fast(data["wn_matches"], data["wn_names"], _data["words"], _data["poses"], _data)
    _data["_fast"].__enter__()


def _run_part(part, values, steps, rnd):
    """One round of one part's search (in a tuning process): (part, values, steps, train error, test error, test
    tally). The part ALL tunes on every answered word and has no test."""
    words = sorted(_data["answers"])
    train = [w for w in words if part == ALL or part_of(w) != part]
    test = [] if part == ALL else [w for w in words if part_of(w) == part]
    order = sorted(values, key=lambda p: hashlib.md5(f"{p}{rnd}{part}".encode()).hexdigest())
    out = _data.get("_progress")
    tell = (lambda i, n: out.put(("step", rnd, part, i, n))) if out is not None else None
    values, steps, train_err = tune_round(_data, values, steps, train, order, tell)
    test_err, t = evaluate(_data, values, test) if test else (None, None)
    return part, values, steps, train_err, test_err, t


def _tested(part, values):
    """(part, the scores of its tested words) with `values`, for the misses and the start's tally."""
    test = [w for w in _data["answers"] if part_of(w) == part]
    apply(values, _data["base"])
    return part, score_targets(_data, test)


class Inline:
    """A stand-in for ProcessPoolExecutor that runs each job at once, in this process (tests; --workers 0)."""
    def __init__(self, data):
        _keep(data)

    def submit(self, fn, *args):
        class Done:
            def __init__(self, value):
                self.value = value

            def result(self):
                return self.value
        return Done(fn(*args))

    def shutdown(self, wait=True, cancel_futures=False):
        apply(_data["start"], _data["base"])             # (the rules as they were: this process goes on)
        _data.pop("_fast").__exit__(None, None, None)
        _data.clear()


def pool(data, workers, progress=None):
    """Where the parts are tuned: `workers` processes, or this one (0); each number tried is put on `progress` (a
    multiprocessing queue for processes)."""
    if workers == 0:
        ex = Inline(data)
        _data["_progress"] = progress
        return ex
    return ProcessPoolExecutor(max_workers=workers, initializer=_start, initargs=(data, progress))


# ---- the data -------------------------------------------------------------------------------------------------------
def read_compact(path, progress=None):
    """{word: [compact sense]} from the compact entries (measure_rudeness fetch); progress(share read) now and then."""
    out = {}
    size, done, shown = max(1, os.path.getsize(path)), 0, 0.0
    with open(path, "rb") as f:
        for line in f:
            e = json.loads(line)
            out.setdefault(e["w"], []).extend(e["senses"])
            done += len(line)
            if progress and done / size - shown >= 0.005:
                shown = done / size
                progress(shown)
    return out


def program_words(compacts):
    """{word: compact senses as JSON text}: the words the program keeps and scores (wordsource.RudeCollector: any sign
    of rudeness, or only a form of such a word)."""
    kept = {w: cs for w, cs in compacts.items() if any(rudeness.has_signal(c) for c in cs)}
    for w, cs in compacts.items():
        targets = {c.get("f") for c in cs}
        if w not in kept and len(targets) == 1 and None not in targets and next(iter(targets)) in kept:
            kept[w] = cs
    return {w: json.dumps(cs, separators=(",", ":")) for w, cs in kept.items()}


READING, LINKING, MATCHING = "Reading the Wiktionary entries", "Linking words to their families", "Matching to WordNet"


def prepare(entries, answers, wn=None, zipf=None, log=print, progress=None):
    """(data for the tuning, the program's words for the guard) from the compact entries and the answers;
    progress(step, share done or None) for the window's bar."""
    progress = progress or (lambda step, share: None)
    log("Reading the Wiktionary entries ...")
    progress(READING, 0.0)
    compacts = read_compact(entries, lambda share: progress(READING, share))
    progress(LINKING, None)
    words = {w: [rudeness.expand(c) for c in cs] for w, cs in compacts.items()}
    poses = {w: [c.get("pos", "") for c in cs] for w, cs in compacts.items()}
    family = rudeness.families({w: [p for c in cs for p in c.get("e", ())] for w, cs in compacts.items()},
                               {w: [k for c in cs for k in c.get("d", ())] for w, cs in compacts.items()})
    pairs = answer_pairs(answers, words)
    need = scope(set(pairs), words, family)
    words = {w: words[w] for w in need}
    poses = {w: poses[w] for w in need}
    log(f"Matching {len(words):,} words' meanings to WordNet ..." if wn else "WordNet is not installed: without it")
    wn_matches, wn_names = wordnet_tables(words, poses, wn, lambda share: progress(MATCHING, share))
    zipf = zipf or (lambda w: 0.0)
    values, base = snapshot()
    data = {"words": words, "poses": poses, "family": {w: tuple(family.get(w, ())) for w in need},
            "answers": pairs, "zipf": {w: zipf(w) for w in pairs}, "wn_matches": wn_matches, "wn_names": wn_names,
            "base": base, "start": values, "bounds": {p: bounds(p, v) for p, v in values.items()}}
    return data, program_words(compacts)


def guard(saved, values, base, wn=None, zipf=None):
    """{"whole": words smeared whole, kind: words with a meaning of that kind}: what the program would show with
    `values` (rudeness.score_saved over its words)."""
    start = snapshot()[0]
    try:
        apply(values, base)
        out = rudeness.score_saved(saved, obscene.CENSORED, wn, zipf=zipf)
    finally:
        apply(start, base)
    counts = collections.Counter()
    for res in out.values():
        bits, whole = res[0], res[1]
        counts["whole"] += bool(whole)
        for k in obscene.RUDE_KINDS:
            counts[k] += bool(bits & rudeness.KIND_BITS[k])
    return {k: counts[k] for k in ("whole",) + tuple(obscene.RUDE_KINDS)}


# ---- writing the numbers back --------------------------------------------------------------------------------------
def _num(v):
    """A number as the source writes it: 3.0, 0.35, 2.5 (two decimals at most)."""
    v = round(v, 2)
    return f"{v:.2f}".rstrip("0").rstrip(".") + (".0" if v == int(v) else "")


def _block(text, name):
    """(start, end) of `name = {...}` or `name = [...]` at the start of a line in `text` (to its closing bracket)."""
    m = re.search(rf"^{name} = ([\[{{])", text, re.M)
    if not m:
        raise ValueError(f"{name} not found in rudeness.py")
    depth, i = 0, m.start(1)
    while i < len(text):
        c = text[i]
        if c in "[{(":
            depth += 1
        elif c in "]})":
            depth -= 1
            if depth == 0:
                return m.start(), i + 1
        elif c in "\"'":                     # (a string: skip it whole, brackets inside patterns included)
            q = text[i:i + 3] if text[i:i + 3] in ('"""', "'''") else c
            i = text.index(q, i + len(q)) + len(q) - 1
        i += 1
    raise ValueError(f"{name}'s end not found")


def write_back(path, values, base):
    """Write `values` into rudeness.py at `path` (each number where it stands, comments kept) and bump
    RUDENESS_VERSION; the file is read back to check every number landed. Returns the changed text."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    old = dict(values)
    for p, v in values.items():
        parts = p.split(" ")
        if len(parts) == 1:
            text, n = re.subn(rf"^({p} = )[-0-9.]+", lambda m: m.group(1) + _num(v), text, count=1, flags=re.M)
            if not n:
                raise ValueError(f"{p} not found in rudeness.py")
        elif parts[1] == "*":
            a, b = _block(text, parts[0])
            kind = re.escape(parts[2])
            origs = iter([t[parts[2]] for t in base[parts[0]] if parts[2] in t])
            block = re.sub(rf'("{kind}": )[-0-9.]+', lambda m: m.group(1) + _num(next(origs) * v), text[a:b])
            text = text[:a] + block + text[b:]
        else:
            a, b = _block(text, parts[0])
            block = text[a:b]
            if parts[0] == "TAG_POINTS":
                m = re.search(rf'"{re.escape(parts[1])}": \{{[^}}]*\}}', block)
                inner = re.sub(rf'("{re.escape(parts[2])}": )[-0-9.]+', lambda q: q.group(1) + _num(v), m.group(0))
                block = block[:m.start()] + inner + block[m.end():]
            else:
                block = re.sub(rf'("{re.escape(parts[1])}": )[-0-9.]+', lambda q: q.group(1) + _num(v), block, 1)
            text = text[:a] + block + text[b:]
    text = re.sub(r'^(RUDENESS_VERSION = ")(\d+)(")', lambda m: f"{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}",
                  text, count=1, flags=re.M)
    check(text, old, base)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    return text


def check(text, values, base):
    """Run the new rudeness.py's text on its own and check each number reads as `values` say (to 2 decimals)."""
    space = {"__name__": "rudeness_check"}
    exec(compile(text, "rudeness.py", "exec"), space)           # (the repository's own file, just written)
    for p, v in values.items():
        parts = p.split(" ")
        if len(parts) == 1:
            got = [(space[p], v)]
        elif parts[1] == "*":
            tables = [t for _p, t in space["WORDING"]] if parts[0] == "WORDING" else list(space[parts[0]].values())
            got = [(t[parts[2]], o[parts[2]] * v) for t, o in zip(tables, base[parts[0]]) if parts[2] in o]
        elif parts[0] == "TAG_POINTS":
            got = [(space["TAG_POINTS"][parts[1]][parts[2]], v)]
        else:
            got = [(space[parts[0]][parts[1]], v)]
        for have, want in got:
            if abs(have - round(want, 2)) > 0.006:
                raise ValueError(f"{p}: {have} written, {want} meant")


def misses(data, scored):
    """[(word, gloss, answered, the rules' kind)] of the tested meanings `scored` still gets wrong, commonest
    first."""
    out = []
    for w, sc in scored.items():
        for i, want in data["answers"][w][0]:
            got = rudeness.sense_kind(sc[i])
            if got != want:
                out.append((-data["zipf"].get(w, 0.0), w, rudeness.gloss_of(data["words"][w][i]), want, got))
    return [x[1:] for x in sorted(out)]


def write_misses(path, found, rnd):
    """The misses as text: one meaning a line, the word, your kind, the rules' kind, its definition."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Tested meanings the best numbers (round {rnd}) still get wrong: word, your kind, the rules' "
                "kind, definition\n")
        for word, gloss, want, got in found:
            f.write(f"{word}\t{want}\t{got}\t{gloss}\n")


def changed(start, values):
    """[(param, from, to)] of the numbers that moved (factors shown as their effect: "TOPIC_POINTS * clinical")."""
    return [(p, start[p], v) for p, v in values.items() if round(v, 2) != round(start[p], 2)]


def read_answers(path):
    """The answers file's {word: {"kinds": {meaning key: kind}, "whole": bool}} (measure_rudeness.read_answers)."""
    import measure_rudeness
    return measure_rudeness.read_answers(path)


# ---- the run, between the window and the processes -------------------------------------------------------------
class Tuning:
    """The search: every part's rounds in the processes, one round at a time; events go to `events` (a queue) as
    ("round", n, {part: (train error, test error)}, average test error), ("best", round), ("done", why),
    ("tally", "now" | "best", {class: [tp, fp, fn]}), ("guard", "now" | "best", counts), ("misses", list),
    ("log", text), ("error", text). pause(), resume(), stop()."""

    def __init__(self, data, saved, events, rounds=60, workers=PARTS + 1, misses_path=None):
        self.data, self.saved, self.events, self.rounds, self.workers = data, saved, events, rounds, workers
        self.misses_path = misses_path
        self.start_values = dict(data["start"])
        self.tested = tested_parts(data)    # (only parts with answered words: a few answers leave some empty)
        self.values = {part: dict(self.start_values) for part in range(PARTS + 1)}
        self.steps = {part: {p: STEP for p in self.start_values} for part in range(PARTS + 1)}
        self.history = []                   # [(round, {part: values}, average test error)]
        self.best = None                    # (round, average test error, all words' values, tally)
        self._go = threading.Event()
        self._go.set()
        self._stop = False
        self.round = 0

    def run(self):
        """The search (a worker thread: never touches tkinter)."""
        try:
            steps = self.events if self.workers == 0 else _mp_queue()
            if steps is not self.events:          # (the processes' steps, passed on to the window)
                threading.Thread(target=_relay, args=(steps, self.events), daemon=True).start()
            ex = pool(self.data, self.workers, steps)
            try:
                self._run(ex)
            finally:
                ex.shutdown(wait=True, cancel_futures=True)
                if steps is not self.events:
                    steps.put(None)
        except Exception as e:              # (the window says so)
            self.events.put(("error", f"{type(e).__name__}: {e}"))

    def _run(self, ex):
        jobs = [ex.submit(_run_part, p, self.start_values, {k: 0.0 for k in self.start_values}, 0)
                for p in self.tested]
        now = self._results(0, jobs)
        avg = sum(r[4] for r in now) / len(now)
        self.events.put(("round", 0, {r[0]: (r[3], r[4]) for r in now}, avg))
        self.events.put(("tally", "now", _sum_tallies(r[5] for r in now)))
        self.history.append((0, {p: dict(self.start_values) for p in range(PARTS + 1)}, avg))
        self.best = (0, avg, dict(self.start_values), _sum_tallies(r[5] for r in now))
        self.events.put(("best", 0))
        self._misses(ex)
        for rnd in range(1, self.rounds + 1):
            self._go.wait()
            if self._stop:
                return
            jobs = [ex.submit(_run_part, p, self.values[p], self.steps[p], rnd) for p in self.tested + [ALL]]
            res = {r[0]: r for r in self._results(rnd, jobs)}
            for p, r in res.items():
                self.values[p], self.steps[p] = r[1], r[2]
            avg = sum(res[p][4] for p in self.tested) / len(self.tested)
            self.round = rnd
            self.history.append((rnd, {p: dict(self.values[p]) for p in res}, avg))
            self.events.put(("round", rnd, {p: (res[p][3], res[p][4]) for p in res}, avg))
            if avg < self.best[1] - 1e-9:
                self.best = (rnd, avg, dict(self.values[ALL]), _sum_tallies(res[p][5] for p in self.tested))
                self.events.put(("best", rnd))
                self.events.put(("tally", "best", self.best[3]))
                self._misses(ex)
            if all(s < MIN_STEP for st in self.steps.values() for s in st.values()):
                self.events.put(("done", "settled"))
                return
        self.events.put(("done", "rounds"))

    def _results(self, rnd, jobs):
        """The jobs' results in order: ("begin", round, jobs), then each one an event for the window's bar ("part",
        round, done, of)."""
        self.events.put(("begin", rnd, len(jobs)))
        out = []
        for j in jobs:
            out.append(j.result())
            self.events.put(("part", rnd, len(out), len(jobs)))
        return out

    def _misses(self, ex):
        """The tested meanings the best round still gets wrong (each part's numbers at that round): an event, and
        all of them in the misses file."""
        scored = {}
        for job in [ex.submit(_tested, part, self.values[part]) for part in self.tested]:
            scored.update(job.result()[1])
        found = misses(self.data, scored)
        self.events.put(("misses", found))
        if self.misses_path:
            write_misses(self.misses_path, found, self.best[0])

    def pause(self):
        self._go.clear()

    def resume(self):
        self._go.set()

    def stop(self):
        self._stop = True
        self._go.set()


def _mp_queue():
    import multiprocessing
    return multiprocessing.Queue()


def _relay(source, events):
    """Pass the tuning processes' steps on to the window's events, until None."""
    for e in iter(source.get, None):
        events.put(e)


def tested_parts(data):
    """The parts that hold at least one answered word (in order): only these are tested and averaged."""
    return sorted({part_of(w) for w in data["answers"]})


def _sum_tallies(tallies):
    out = None
    for t in tallies:
        if out is None:
            out = {c: list(v) for c, v in t.items()}
        else:
            for c, v in t.items():
                out[c] = [a + b for a, b in zip(out[c], v)]
    return out


def precision_recall(t):
    """{class: (precision, recall) in %} from a tally."""
    return {c: (100 * tp / max(1, tp + fp), 100 * tp / max(1, tp + fn)) for c, (tp, fp, fn) in t.items()}


# ---- the guard's process --------------------------------------------------------------------------------------------
_guard = {}


def _start_guard(saved):
    """The guard's process: the program's words, WordNet's matches for them worked out once."""
    from wordfreq import zipf_frequency
    lower_priority()
    words = {w: [rudeness.expand(c) for c in json.loads(t)] for w, t in saved.items()}
    poses = {w: [c.get("pos", "") for c in json.loads(t)] for w, t in saved.items()}
    wn = rudeness.wordnet()
    matches, names = wordnet_tables(words, poses, wn)
    _guard.update(saved=saved, wn="wn" if wn else None, zipf=lambda w: zipf_frequency(w, "en"))
    _guard["_fast"] = fast(matches, names)
    _guard["_fast"].__enter__()


def _run_guard(values, base):
    return guard(_guard["saved"], values, base, _guard["wn"], _guard["zipf"])


# ---- the window ----------------------------------------------------------------------------------------------------
PART_LINE = "#A6D9BD"           # (the chart's own colours: a part's faint line, the average's)
AVERAGE_LINE = "#5FBF8C"
SHOWN_CHANGES = 6
SHOWN_MISSES = 3
GUARD_NAMES = (("whole", "Smeared whole"),) + tuple((k, n) for k, n in (
    ("clinical", "Clinical"), ("crude", "Crude"), ("swear", "Swear word"), ("insult", "Insult"), ("sexual", "Sexual"),
    ("slur", "Slur")))


def doubled(now, best):
    """The guard's names that cover more than DOUBLED times the words they do now (from none: any)."""
    return [k for k, _n in GUARD_NAMES if best.get(k, 0) > DOUBLED * now.get(k, 0) and best.get(k, 0) >= 10]


class TuneWindow:
    """The window (the mock-up agreed): the error round by round, each kind before and after, the numbers changed,
    the guard, the meanings still wrong; Pause, Discard, Keep the best numbers."""

    CHART = (960, 400)                      # (the most it starts at; it grows with the window)
    TICK_MS = 1000                          # the bar's time left counts down this often

    def __init__(self, root, answers_path, rounds, source):
        import tkinter as tk
        from fonts import font
        from theme import PALETTE as P
        from ui_motion import Animator
        from widgets import RoundButton
        self.tk, self.font, self.P = tk, font, P
        self.root, self.answers_path, self.rounds, self.source = root, answers_path, rounds, source
        self.events = queue.Queue()
        self.from_program = False                 # (started by the program's bubble: its close box only hides it)
        self.tuning = self.data = None
        self.points = {}                    # {part: [(round, test error)]}, ALL: train error
        self.avg = []                       # [(round, average test error)]
        self.tallies, self.guards, self.miss = {}, {}, []
        self.best_round, self.done, self.closed = None, False, False
        bg = P["bg"]
        root.title("Tune the rules")
        root.configure(bg=bg)
        anim = Animator(root, reduce_motion=True)
        box = tk.Frame(root, bg=bg, padx=26, pady=20)
        box.pack(fill="both", expand=True)
        top = tk.Frame(box, bg=bg)
        top.pack(fill="x")
        tk.Label(top, text="Tune the rules", font=font("head"), bg=bg, fg=P["text"]).pack(side="left")
        self.status = tk.Label(top, font=font("body"), bg=bg, fg=P["muted"])
        self.status.pack(side="right")
        tk.Label(box, text="Rules only: it changes the numbers in rudeness.py; the program never reads your answers.",
                 font=font("small"), bg=bg, fg=P["muted"]).pack(anchor="w")
        self.info = tk.Label(box, font=font("body"), bg=bg, fg=P["text"], text="Reading the Wiktionary entries ...",
                             justify="left", anchor="w")
        self.info.pack(fill="x", pady=(12, 6))
        from tkinter import ttk
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Tune.Horizontal.TProgressbar", background=P["accent"], troughcolor=P["surface2"],
                        bordercolor=P["surface2"], lightcolor=P["accent"], darkcolor=P["accent"], thickness=10)
        self.bar = ttk.Progressbar(box, maximum=100, mode="determinate", style="Tune.Horizontal.TProgressbar")
        self.bar.pack(fill="x")
        self.bar_text = tk.Label(box, font=font("small"), bg=bg, fg=P["muted"], anchor="w")
        self.bar_text.pack(fill="x", pady=(3, 10))
        self.eta, self.step, self.share = None, None, None      # (the reading's bar: its step and share done)
        self.round_started = None                               # (a round's bar: when it began, each part's share)
        self.bar_round, self.tried, self.round_eta = 0, {}, None
        self.parts = (0, 0)
        w, h = self.chart_size(root)
        self.bottom = tk.Frame(box, bg=bg)                      # (packed first at the bottom: the chart takes the rest)
        self.chart = tk.Canvas(box, width=w, height=h, bg=P["surface"], highlightthickness=1,
                               highlightbackground=P["border"])
        self.note = tk.Label(self.bottom, font=font("small"), bg=bg, fg=P["muted"], wraplength=w, justify="left")
        self.note.pack(anchor="w", pady=(6, 0))
        box = self.bottom
        cols = tk.Frame(box, bg=bg)
        cols.pack(fill="x", pady=(14, 0))
        self.kinds_box = tk.Frame(cols, bg=bg)
        self.kinds_box.pack(side="left", anchor="n")
        self.changes_box = tk.Frame(cols, bg=bg)
        self.changes_box.pack(side="right", anchor="n")
        self.guard_box = tk.Frame(box, bg=P["surface"], highlightthickness=1, highlightbackground=P["border"],
                                  padx=12, pady=8)
        self.guard_box.pack(fill="x", pady=(16, 0))
        self.miss_box = tk.Frame(box, bg=bg)
        self.miss_box.pack(fill="x", pady=(12, 0))
        nav = tk.Frame(box, bg=bg)
        nav.pack(fill="x", pady=(18, 0))
        kw = dict(font=font("body"), padx=16, pady=6, radius=12, animator=anim)
        self.pause_btn = RoundButton(nav, "Pause", self.pause, bg=P["surface"], **kw)
        self.pause_btn.pack(side="left")
        self.keep_btn = RoundButton(nav, "Keep the best numbers", self.keep, bg=P["select_bg"], **kw)
        self.keep_btn.pack(side="right")
        RoundButton(nav, "Discard", self.discard, bg=P["surface"], **kw).pack(side="right", padx=(0, 8))
        tk.Label(box, text="Keep writes the numbers into src/rudeness.py (and bumps RUDENESS_VERSION); review the diff "
                 "before committing.", font=font("small"), bg=bg, fg=P["muted"]).pack(anchor="w", pady=(12, 0))
        self.bottom.pack(side="bottom", fill="x")
        self.chart.pack(fill="both", expand=True)
        self._resize_job = None
        self.chart.bind("<Configure>", self._resized)
        self.keep_btn.set_enabled(False)
        self.pause_btn.set_enabled(False)
        self.hidden = self.failed = False
        root.protocol("WM_DELETE_WINDOW", self.close_box)
        self.show_bar()
        self.draw()
        self._poll_job = root.after(150, self._poll)
        self._tick_job = root.after(self.TICK_MS, self._tick)

    @classmethod
    def chart_size(cls, root):
        """The chart's starting size: CHART, smaller on a small screen (the rest of the window needs about 560 px)."""
        w, h = cls.CHART
        return max(560, min(w, root.winfo_screenwidth() - 140)), max(220, min(h, root.winfo_screenheight() - 600))

    def _resized(self, _e=None):
        """The chart follows the window's size: drawn again once the resizing pauses (not at every step of a drag)."""
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(60, self._redraw)

    def _redraw(self):
        self._resize_job = None
        self.note.config(wraplength=max(300, self.chart.winfo_width()))
        self.draw()

    # ---- the bar: reading the entries, then each round ----------------------------------------------------------
    def show_bar(self):
        """The bar and its line from what is known: the reading's step and share, or the round's parts done."""
        import startup
        now = time.time()
        if self.round_started is None:                          # (reading the entries)
            if self.share is None:
                self.bar.config(mode="indeterminate")
                self.bar.start(15) if not getattr(self, "_moving", False) else None
                self._moving = True
                self.bar_text.config(text=f"{self.step or READING} ...")
                return
            self._still()
            self.bar.config(value=100 * self.share)
            left = self.eta.remaining(now) if self.eta else None
            self.bar_text.config(text=f"{self.step}: {self.share:.0%}" + (
                f"  ·  {startup.format_eta(left)}" if left is not None else "  ·  working out the time left"))
            return
        self._still()
        (done, of), rnd = self.parts, self.bar_round
        if self.done or self.failed:
            self.bar.config(value=100 if self.done else self.bar.cget("value"))
            self.bar_text.config(text="Done" if self.done else "")
            return
        share = self.round_share()
        self.bar.config(value=100 * share)
        if done == of and self._paused():
            self.bar_text.config(text=f"Paused after round {rnd}")
            return
        left = self.round_eta.remaining(now) if done < of else None
        what = "Scoring the rules as they are" if rnd == 0 else f"Round {rnd} of up to {self.rounds}"
        self.bar_text.config(text=f"{what}: {share:.0%}" + (f"  ·  {startup.format_eta(left)} in this round" if left
                                                             is not None else "  ·  working out the time left"
                                                             if done < of else "")
                             + ("  (it stops early once nothing improves)" if rnd == 1 else ""))

    def round_share(self):
        """How much of this round is done: each part's numbers tried (a part done counts whole)."""
        done, of = self.parts
        if not of:
            return 0.0
        return max(done / of, min(1.0, sum(self.tried.values()) / of))

    def _still(self):
        if getattr(self, "_moving", False):
            self.bar.stop()
            self.bar.config(mode="determinate")
            self._moving = False

    def _tick(self):
        if self.closed:
            return
        self.show_bar()
        self._tick_job = self.root.after(self.TICK_MS, self._tick)

    # ---- events from the work ---------------------------------------------------------------------------------
    def start(self, data, saved, workers, guard_workers=1):
        """The data is ready: start the search (a worker thread) and the guard's process."""
        self.data, self.saved = data, saved
        n = sum(len(p) for p, _w in data["answers"].values())
        if not data["answers"]:
            self.info.config(text="None of your answers matched a word in the entries: nothing to tune on yet.")
            self.status.config(text="Nothing to tune")
            self.pause_btn.set_enabled(False)
            return
        have = len(tested_parts(data))
        self.info.config(text=f"Your answers: {len(data['answers']):,} words, {n:,} meanings. Split into {PARTS} "
                         f"parts: tuned on {PARTS - 1}, tested on the {PARTS}th, each part in turn."
                         + (f" Only {have} of the {PARTS} parts have answered words yet, so the test is rough until "
                            "you answer more." if have < PARTS else ""))
        self.tuning = Tuning(data, saved, self.events, self.rounds, workers,
                             os.path.join(os.path.dirname(os.path.abspath(self.answers_path)), MISSES_FILE))
        threading.Thread(target=self.tuning.run, daemon=True).start()
        self.guard_pool = pool_for_guard(saved, guard_workers)
        self._ask_guard("now", data["start"])
        self.pause_btn.set_enabled(True)
        self.status.config(text="Round 0")

    def _ask_guard(self, which, values):
        fut = self.guard_pool.submit(_run_guard, values, self.data["base"])
        self.guards.pop(which, None) if which == "best" else None
        threading.Thread(target=lambda: self.events.put(("guard", which, _result(fut))), daemon=True).start()
        self.draw_guard()

    def _poll(self):
        if self.closed:
            return
        try:
            while not self.closed:
                self.handle(self.events.get_nowait())
        except queue.Empty:
            pass
        if not self.closed:                       # (an event can close it: "gone" while hidden)
            self._poll_job = self.root.after(150, self._poll)

    def handle(self, e):
        """One event from the search, the guard or the start (see Tuning)."""
        kind = e[0]
        if kind == "log":
            self.info.config(text=e[1])
        elif kind == "progress":
            if e[1] != self.step:
                self.eta = None
            self.step, self.share = e[1], e[2]
            if e[2] is not None:
                import startup
                self.eta = self.eta or startup.EtaTracker()
                self.eta.add(100 * e[2], time.time())
            self.show_bar()
        elif kind == "begin":                                   # (a round's parts start)
            import startup
            self.bar_round, self.round_started, self.parts, self.tried = e[1], time.time(), (0, e[2]), {}
            self.round_eta = startup.EtaTracker()
            if e[1]:
                self.status.config(text=f"Round {e[1]} of up to {self.rounds}")
            self.show_bar()
        elif kind == "step":                                    # (a part tried another number: "step", rnd, part, i, n)
            if e[1] == self.bar_round and self.round_eta is not None:
                self.tried[e[2]] = e[3] / max(1, e[4])
                self.round_eta.add(self.round_share() * 100, time.time())
                self.show_bar()
        elif kind == "part":
            self.parts = (e[2], e[3])
            self.show_bar()
        elif kind == "ready":
            self.start(*e[1:])
        elif kind == "round":
            _k, rnd, errs, avg = e
            for part, (train, test) in errs.items():
                self.points.setdefault(part, []).append((rnd, train if part == ALL else test))
            self.avg.append((rnd, avg))
            self.status.config(text=f"Round {rnd} of up to {self.rounds}" + ("  ·  paused" if self._paused() else ""))
            say(f"Round {rnd} of up to {self.rounds}")
            self.draw()
        elif kind == "best":
            self.best_round = e[1]
            self.keep_btn.set_enabled(e[1] > 0)
            self.draw()
        elif kind == "tally":
            self.tallies[e[1]] = e[2]
            self.draw_kinds()
        elif kind == "misses":
            self.miss = e[1]
            self.draw_misses()
        elif kind == "guard":
            self.guards[e[1]] = e[2]
            self.draw_guard()
        elif kind == "show":
            self.show_again()
        elif kind == "gone":                      # (the program closed: a hidden tuner would be out of reach)
            if self.hidden:
                self.discard()
        elif kind == "done":
            say("Done")
            if self.hidden:                       # (finished while hidden: back, for Keep or Discard)
                self.show_again()
            self.done = True
            self.pause_btn.set_enabled(False)
            self.status.config(text=f"Done at round {self.avg[-1][0] if self.avg else 0}: "
                               + ("settled" if e[1] == "settled" else "the last round"))
            self.check_best()
            self.show_bar()
        elif kind == "error":
            self.failed = True
            if self.hidden:
                self.show_again()
            self.status.config(text="Stopped: an error")
            self.note.config(text=e[1], fg=self.P["bad"][1])

    # ---- started by the program's Tune the rules bubble (--from-program) -----------------------------------------
    def listen(self, stream):
        """Lines from the program (a worker thread: no Tk here): "show" brings the window back; the end of the stream
        (the program closed) is an event too."""
        try:
            for line in stream:
                if line.strip() == "show":
                    self.events.put(("show",))
        except (OSError, ValueError):
            pass
        self.events.put(("gone",))

    def close_box(self):
        """The window's close box: while the tuning still runs (asked for), only hidden, and the program's bubble brings
        it back; Discard stops it. Started by hand, or once done, it closes as Discard does."""
        if self.from_program and not (self.done or self.failed or self.closed):
            self.hidden = True
            self.root.withdraw()
            say("Hidden")
            return
        self.discard()

    def show_again(self):
        self.hidden = False
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _paused(self):
        return self.tuning is not None and not self.tuning._go.is_set()

    def check_best(self):
        """Count the guard for the best numbers (when the search pauses or ends) and list the misses."""
        if self.best_round and self.guards.get("best_round") != self.best_round:
            self.guards["best_round"] = self.best_round
            self._ask_guard("best", self.tuning.best[2])

    # ---- drawing ------------------------------------------------------------------------------------------------
    def draw(self):
        c, P, font = self.chart, self.P, self.font
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 50 or h < 50:                                    # (not laid out yet)
            w, h = int(c.cget("width")), int(c.cget("height"))
        legend = ((AVERAGE_LINE, None, 3, f"error: the average of the {PARTS} parts (100% minus the average F1)"),
                  (PART_LINE, None, 2, "each part, tested on numbers tuned without it"),
                  (P["muted"], (4, 4), 1, "the rules as they are now"))
        widths = [56 + font("small").measure(t) for *_k, t in legend]
        rows, used = 1, 0                                       # (the legend wraps when the chart is narrow)
        for wd in widths:
            if used and used + wd > w - 80:
                rows, used = rows + 1, 0
            used += wd
        left, right, top, bottom = 70, 130, 14, 42 + 18 * rows
        start = self.avg[0][1] if self.avg else 25.0
        hi = max(10, 5 * (int(max([start] + [e for pts in self.points.values() for _r, e in pts]) / 5) + 1))
        x = lambda r: left + r / max(1, self.rounds) * (w - left - right)     # noqa: E731
        y = lambda v: top + (hi - v) / hi * (h - top - bottom)                 # noqa: E731
        for v in range(0, hi + 1, 5 if hi <= 40 else 10):
            c.create_line(left, y(v), w - right, y(v), fill=P["border"])
            c.create_text(left - 8, y(v), text=f"{v}%", anchor="e", font=font("small"), fill=P["muted"])
        tick = 10 if self.rounds > 30 else 5
        for r in range(0, self.rounds + 1, tick):
            c.create_text(x(r), h - bottom + 14, text=str(r), font=font("small"), fill=P["muted"])
        c.create_text((left + w - right) / 2, h - bottom + 32, text="round", font=font("small"), fill=P["muted"])
        c.create_text(18, (top + h - bottom) / 2, text="error (lower is better)", angle=90, font=font("small"),
                      fill=P["muted"])
        if not self.avg:
            c.create_text((left + w - right) / 2, h / 2, text="The first round starts once the words are read.",
                          font=font("small"), fill=P["muted"])
            return
        c.create_line(left, y(start), w - right, y(start), fill=P["muted"], dash=(4, 4))
        c.create_text(w - right + 8, y(start), text=f"now {start:.1f}%", anchor="w", font=font("small"),
                      fill=P["muted"])
        for part in range(PARTS):
            pts = self.points.get(part, [])
            if len(pts) > 1:
                c.create_line(*[v for r, e in pts for v in (x(r), y(e))], fill=PART_LINE, width=2)
        if len(self.avg) > 1:
            c.create_line(*[v for r, e in self.avg for v in (x(r), y(e))], fill=AVERAGE_LINE, width=3)
        r, e = self.avg[-1]
        c.create_oval(x(r) - 4, y(e) - 4, x(r) + 4, y(e) + 4, fill=AVERAGE_LINE, outline=AVERAGE_LINE)
        ly = y(e) if abs(y(e) - y(start)) > 14 else y(e) + (16 if y(e) >= y(start) else -16)
        c.create_text(w - right + 8, ly, text=f"average {e:.1f}%", anchor="w", font=font("small"), fill=P["text"])
        if self.best_round:
            c.create_line(x(self.best_round), top, x(self.best_round), h - bottom, fill=P["muted"], dash=(2, 3))
            c.create_text(x(self.best_round) + 4, top + 8, text=f"best: round {self.best_round}", anchor="w",
                          font=font("small"), fill=P["muted"])
        lx, ly = left, h - bottom + 50                # the legend (every line named): under the plot
        for (col, dash, wd, text), width in zip(legend, widths):
            if lx > left and lx + width > w - 10:
                lx, ly = left, ly + 18
            c.create_line(lx, ly, lx + 24, ly, fill=col, width=wd, dash=dash)
            item = c.create_text(lx + 32, ly, text=text, anchor="w", font=font("small"), fill=P["text"])
            lx = c.bbox(item)[2] + 24
        self.draw_note()
        self.draw_changes()

    def draw_note(self):
        if not self.best_round:
            self.note.config(text="No round has beaten the rules as they are yet.")
            return
        fit = dict(self.points.get(ALL, [])).get(self.best_round)
        avg = dict(self.avg)[self.best_round]
        gap = avg - fit if fit is not None else 0
        self.note.config(text=f"Best at round {self.best_round}. Keep takes the numbers tuned on all your words at "
                         f"that round. Error on the words it tuned on: {fit:.1f}% ({gap:.1f} points below the tested "
                         "error: " + ("a small gap, so it is not just memorising your answers)." if gap < 5 else
                                      "a wide gap: it is learning your answers more than the rules).")
                         if fit is not None else "")

    def _clear(self, frame):
        for wdg in frame.winfo_children():
            wdg.destroy()

    def draw_kinds(self):
        import review
        tk, P, font, box = self.tk, self.P, self.font, self.kinds_box
        self._clear(box)
        tk.Label(box, text="Each kind, tested (precision / recall)", font=font("small"), bg=P["bg"],
                 fg=P["muted"]).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 4))
        now, best = (precision_recall(self.tallies[k]) if k in self.tallies else None for k in ("now", "best"))
        for i, (k, name) in enumerate(GUARD_NAMES[1:] + (("whole", "Smeared whole"),), 1):
            if now is None:
                break
            colour = review.kind_colour(k) if k != "whole" else P["surface2"]
            tk.Label(box, text=name, font=font("small"), bg=colour, fg=P["text"], padx=8, pady=1,
                     width=12).grid(row=i, column=0, sticky="w", pady=1)
            fmt = lambda pr: f"{pr[0]:.0f} / {pr[1]:.0f}"        # noqa: E731
            tk.Label(box, text=fmt(now[k]), font=font("small"), bg=P["bg"], fg=P["muted"]).grid(row=i, column=1,
                                                                                               padx=(10, 4))
            if best:
                tk.Label(box, text="→", font=font("small"), bg=P["bg"], fg=P["muted"]).grid(row=i, column=2)
                tk.Label(box, text=fmt(best[k]), font=font("body"), bg=P["bg"], fg=P["text"]).grid(
                    row=i, column=3, padx=(4, 0), sticky="w")

    def draw_changes(self):
        tk, P, font, box = self.tk, self.P, self.font, self.changes_box
        self._clear(box)
        if not self.tuning or not self.tuning.best:
            return
        moved = changed(self.tuning.start_values, self.tuning.best[2])
        moved.sort(key=lambda m: -abs(m[2] - m[1]) / max(abs(m[1]), 0.5))
        tk.Label(box, text=f"Numbers changed ({len(moved)} of {len(self.tuning.start_values)})", font=font("small"),
                 bg=P["bg"], fg=P["muted"]).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        for i, (p, a, b) in enumerate(moved[:SHOWN_CHANGES], 1):
            shown = p.replace(" * ", " × ")
            tk.Label(box, text=shown, font=font("small"), bg=P["bg"], fg=P["text"]).grid(row=i, column=0, sticky="w",
                                                                                        pady=1)
            tk.Label(box, text=f"{_num(a)} → {_num(b)}", font=font("body"), bg=P["bg"], fg=P["text"]).grid(
                row=i, column=1, sticky="e", padx=(14, 0))
        if len(moved) > SHOWN_CHANGES:
            tk.Label(box, text=f"and {len(moved) - SHOWN_CHANGES} more", font=font("small"), bg=P["bg"],
                     fg=P["muted"]).grid(row=SHOWN_CHANGES + 1, column=0, sticky="w")

    def draw_guard(self):
        tk, P, font, box = self.tk, self.P, self.font, self.guard_box
        self._clear(box)
        bg = P["surface"]
        now, best = self.guards.get("now"), self.guards.get("best")
        n = len(self.saved) if self.data else 0
        title = f"Guard: across all {n:,} words the program scores" + (", with the best numbers" if best else "")
        tk.Label(box, text=title, font=font("small"), bg=bg, fg=P["muted"]).grid(row=0, column=0, columnspan=8,
                                                                                 sticky="w")
        if now is None:
            tk.Label(box, text="Counting the words with the rules as they are now ...", font=font("small"), bg=bg,
                     fg=P["muted"]).grid(row=1, column=0, columnspan=8, sticky="w")
            return
        marked = doubled(now, best) if best else []
        for i, (k, name) in enumerate(GUARD_NAMES):
            row, col = 1 + i // 4, 2 * (i % 4)
            tk.Label(box, text=name, font=font("small"), bg=bg, fg=P["muted"]).grid(row=row, column=col, sticky="w",
                                                                                    padx=(0, 6))
            if best:
                d = (100 * (best[k] - now[k]) / now[k]) if now[k] else 0
                text = f"{now[k]:,} → {best[k]:,}" + (f"  {d:+.0f}%" if now[k] and best[k] != now[k] else "")
                text += ": check" if k in marked else ""
            else:
                text = f"{now[k]:,}"
            tk.Label(box, text=text, font=font("body"), bg=bg, fg=P["bad"][1] if k in marked else P["text"]).grid(
                row=row, column=col + 1, sticky="w", padx=(0, 18))
        foot = ("A kind more than doubling is marked: Keep asks first." if best else
                "Counted again with the best numbers when the search pauses or ends." if self.best_round is None or
                "best_round" not in self.guards else "Counting with the best numbers ...")
        tk.Label(box, text=foot, font=font("small"), bg=bg, fg=P["muted"]).grid(row=3, column=0, columnspan=8,
                                                                                sticky="w", pady=(4, 0))

    def draw_misses(self):
        import review
        tk, P, font, box = self.tk, self.P, self.font, self.miss_box
        self._clear(box)
        if not self.miss:
            return
        tk.Label(box, text=f"Still wrong after tuning: {len(self.miss):,} meanings (no number can fix these: ideas "
                 "for new rules)", font=font("small"), bg=P["bg"], fg=P["muted"]).pack(anchor="w")
        for word, gloss, want, got in self.miss[:SHOWN_MISSES]:
            r = tk.Frame(box, bg=P["bg"])
            r.pack(anchor="w", pady=1)
            tk.Label(r, text=word, font=font("body"), bg=P["bg"], fg=P["text"], width=12, anchor="w").pack(side="left")
            tk.Label(r, text=gloss[:52] + ("…" if len(gloss) > 52 else ""), font=font("small"), bg=P["bg"],
                     fg=P["muted"], width=44, anchor="w").pack(side="left")
            for who, k in (("you", want), ("rules", got)):
                tk.Label(r, text=f"{who}: {review.KIND_NAMES[k]}", font=font("small"), bg=review.kind_colour(k),
                         fg=P["text"], padx=6).pack(side="left", padx=(6, 0))
        tk.Label(box, text=f"… all {len(self.miss):,} are written to {MISSES_FILE} beside your answers.",
                 font=font("small"), bg=P["bg"], fg=P["muted"]).pack(anchor="w", pady=(2, 0))

    # ---- the buttons ----------------------------------------------------------------------------------------------
    def pause(self):
        if not self.tuning or self.done:
            return
        if self._paused():
            self.tuning.resume()
            self.pause_btn.config(text="Pause")
        else:
            self.tuning.pause()
            self.pause_btn.config(text="Resume")
            self.check_best()
        self.status.config(text=f"Round {self.tuning.round} of up to {self.rounds}"
                           + ("  ·  paused" if self._paused() else ""))

    def keep(self):
        from errors import ask_yes_no, show_error, show_message
        if not self.tuning or not self.tuning.best or not self.best_round:
            return
        now, best = self.guards.get("now"), self.guards.get("best")
        if best is None or now is None:
            self.check_best()
            show_message("Tune the rules", "Counting the guard first",
                         "The guard is counting the words with the best numbers: press Keep again once it shows.",
                         parent=self.root)
            return
        marked = doubled(now, best)
        if marked:
            names = ", ".join(n for k, n in GUARD_NAMES if k in marked)
            if not ask_yes_no("Tune the rules", "Keep numbers that more than double a kind?",
                              f"{names} would cover more than twice the words it does now. Keep them anyway?",
                              yes="Keep", no="Cancel", parent=self.root):
                return
        values = self.tuning.best[2]
        try:
            write_back(self.source, values, self.data["base"])
        except Exception as e:
            show_error("Tune the rules", f"The numbers were not written: {e}", parent=self.root)
            return
        moved = changed(self.tuning.start_values, values)
        show_message("Tune the rules", "Written into src/rudeness.py",
                     f"{len(moved)} numbers changed and RUDENESS_VERSION bumped. Read the diff (git diff "
                     "src/rudeness.py), run the tests and measure_rudeness answers, then commit.", parent=self.root)
        self.close()

    def discard(self):
        self.close()

    def close(self):
        self.closed = True
        try:
            self._still()                                       # (a moving bar's own timer, or Tk complains later)
        except self.tk.TclError:
            pass
        for job in (self._poll_job, self._tick_job, self._resize_job):
            try:
                self.root.after_cancel(job) if job else None
            except (self.tk.TclError, AttributeError, ValueError):
                pass
        if self.tuning:
            self.tuning.stop()
        gp = getattr(self, "guard_pool", None)
        if gp is not None:
            gp.shutdown(wait=False, cancel_futures=True)
        try:
            self.root.destroy()
        except self.tk.TclError:
            pass


def _result(fut):
    try:
        return fut.result()
    except Exception:                       # (a guard that failed: shown as not counted)
        return None


def pool_for_guard(saved, workers=1):
    """The guard's process (or this one: 0)."""
    if workers == 0:
        class Here:
            def __init__(self):
                _start_guard(saved)

            def submit(self, fn, *args):
                from concurrent.futures import Future
                f = Future()
                f.set_result(fn(*args))
                return f

            def shutdown(self, wait=True, cancel_futures=False):
                _guard.pop("_fast").__exit__(None, None, None)
                _guard.clear()
        return Here()
    return ProcessPoolExecutor(max_workers=workers, initializer=_start_guard, initargs=(saved,))


def main(argv=None):
    """The command line: the window (it reads the entries and starts the search itself)."""
    ap = argparse.ArgumentParser(description="Tune the numbers of the rudeness rules against the review's answers.")
    ap.add_argument("--review", default=os.path.join(ROOT, REVIEW_FILE),
                    help="the review file (its answers are rude_review_answers.jsonl beside it)")
    ap.add_argument("--entries", default=os.path.join(ROOT, "rudeness_entries.jsonl"),
                    help="the compact Wiktionary entries (python tools/measure_rudeness.py fetch)")
    ap.add_argument("--rounds", type=int, default=60, help="rounds at most")
    ap.add_argument("--from-program", action="store_true",
                    help="(the program's Tune the rules bubble) the close box hides the window while tuning runs; "
                         "a \"show\" line on stdin brings it back")
    ap.add_argument("--workers", type=int, default=min(PARTS + 1, os.cpu_count() or 1),
                    help="processes tuning the parts (0: this one)")
    args = ap.parse_args(argv)
    answers_path = review_answers_path(args.review)
    for path, how in ((args.entries, "python tools/measure_rudeness.py fetch (about 3 GB, not kept)"),
                      (answers_path, "python tierlist.py --review-rude")):
        if not os.path.exists(path):
            print(f"{path} is missing: make it with {how}.")
            return 1
    answers = read_answers(answers_path)
    import tkinter as tk
    from fonts import init_fonts
    from ui_style import set_icon
    root = tk.Tk()
    init_fonts(root)
    set_icon(root)
    win = TuneWindow(root, answers_path, args.rounds, os.path.join(ROOT, "src", "rudeness.py"))
    if args.from_program and sys.stdin is not None:
        win.from_program = True
        threading.Thread(target=win.listen, args=(sys.stdin,), daemon=True).start()

    load(args.entries, answers, win.events, args.workers)
    root.mainloop()
    return 0


def load(entries, answers, events, workers):
    """Read the entries in a process of its own (reading them in the window's process froze it for seconds at a
    time); its progress and its result come back as the window's events ("log", "progress", "ready", "error")."""
    import multiprocessing
    ctx = multiprocessing.get_context("spawn")    # (never a fork of a process that runs Tk)
    out = ctx.Queue()
    ctx.Process(target=_load_job, args=(entries, answers, out), daemon=True).start()

    def relay():
        while True:
            e = out.get()
            events.put(e + (workers,) if e[0] == "ready" else e)
            if e[0] in ("ready", "error"):
                return
    threading.Thread(target=relay, daemon=True).start()


def _load_job(entries, answers, out):
    """The reading process: prepare(), at a lower priority, everything it says sent back on `out`."""
    lower_priority()
    try:
        from wordfreq import zipf_frequency
        data, saved = prepare(entries, answers, rudeness.wordnet(), lambda w: zipf_frequency(w, "en"),
                              log=lambda t: out.put(("log", t)), progress=lambda step, share: out.put(
                                  ("progress", step, share)))
        out.put(("ready", data, saved))
    except Exception as e:
        out.put(("error", f"{type(e).__name__}: {e}"))


if __name__ == "__main__":
    sys.exit(main())
