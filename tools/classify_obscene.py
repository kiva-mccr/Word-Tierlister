"""Sort the rude words into kinds with Claude (OB-3): a developer's tool, never part of the program or its windows.

    python tools/classify_obscene.py estimate [--db tierlist.db]    which words would go, and about what it costs
    python tools/classify_obscene.py try fuck box penis              classify a few words now and print the answers
    python tools/classify_obscene.py run [--db tierlist.db]          classify them all (asks first; resumable)
    python tools/classify_obscene.py status                          how far a run has got (and by which model)

Cheap first, then strong where unsure: run --model claude-haiku-5-5, then run --recheck (Opus, the default) sends
only the words answered below --review again; their new answers replace the old ones. Then run --second asks only
for each unsure word's second choice (its likeliest other kind and the chance of it), giving Claude the answer it
already has. Which words a person should check (to_check) follows obscene.check_reason, the program's own rules for
what a word's kinds lead to (dealt or left out, smeared whole or meaning by meaning). No word is ever classified
twice by these, and forms never cost anything.

The kinds (CATEGORIES): clean, double (an innocent main meaning with a rude slang one), clinical, crude, swear,
sexual, insult, slur. Every meaning is judged on its own and the word gets a kind and a confidence (0-100); the
results go to word_categories.tsv next to the save (word, kind, confidence, each meaning's kind, note, model, second
choice).
Words below --review (80) are the ones to check by hand (OB-4).

Which words go (candidates): the ones already marked obscene, any whose stored meanings Wiktionary labels rude,
any whose meanings speak of sex, bodies, excretion or insults (SENSITIVE), the hand-picked list (obscene.on_list),
and the words of two public lists that are in the save (LDNOOBW and HurtLex; --no-lists leaves them out). A word
whose every meaning is a form of a candidate ("plural of bitch") takes that word's answer and costs nothing.

Claude answers through the Message Batches API (half price, usually within the hour). The run is saved as it goes
(word_categories.state.json), so stopping it and running again picks up where it was. It needs the anthropic
package (pip install anthropic; not one of the program's own) and a key (ANTHROPIC_API_KEY, or `ant auth login`).
The save is only read, never written.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(ROOT, "src"))
from constants import OFFLINE_ENV  # noqa: E402
from definitions import parse_definition  # noqa: E402
from obscene import FORM_GLOSS, check_reason, on_list, read_categories  # noqa: E402

CATEGORIES = ("clean", "double", "clinical", "crude", "swear", "sexual", "insult", "slur")
SENSE_CATEGORIES = tuple(c for c in CATEGORIES if c != "double")      # (a single meaning is never "double")
MODEL = "claude-opus-5-5"
PRICES = {"claude-opus-5-5": (4.00, 20.00), "claude-sonnet-5-5": (2.00, 10.00),   # $ per million tokens, in / out
          "claude-haiku-5-5": (0.10, 0.50), "claude-fable-5-1": (10.00, 50.00)}    # (the batch price is half)
GROUP = 20               # words per request
OUT_PER_WORD = 120       # output tokens per word for the estimate (the answer and Claude's thinking at low effort)
REVIEW_BELOW = 80
LISTS = {"ldnoobw": "https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words"
                    "/master/en",
         "hurtlex": "https://raw.githubusercontent.com/valeriobasile/hurtlex/master/lexica/EN/1.2/hurtlex_EN.tsv"}

# meanings that speak of these may be rude even without a label (Wiktionary keeps few labels in the save)
SENSITIVE = re.compile(
    r"\b(sex(ual(ly)?)?|genital\w*|penis|vagina|vulva|clitoris|testic\w+|scrotum|anus|anal|rectum|buttock\w*|breast\w*|"
    r"nipple\w*|semen|ejaculat\w*|masturbat\w*|copulat\w*|intercourse|fellatio|cunnilingus|orgasm\w*|erection|"
    r"prostitut\w*|brothel|pornograph\w*|erotic\w*|homosexual\w*|lesbian\w*|effeminate|excrement|fec(es|al)|"
    r"faec(es|al)|urinat\w*|urine|defecat\w*|flatulen\w*|fart\w*|stupid|idiot\w*|contemptible|despicable|"
    r"worthless|ethnic|racial|person of \w+ descent)\b", re.I)

SYSTEM = """You sort English words for a word-ranking game by how rude they are. The player can hide or blur some \
kinds of rude words, so each word needs a kind, judged meaning by meaning.

Kinds for a single meaning:
- clean: nothing rude about it.
- clinical: the proper, neutral word for a body part, bodily function or sexual matter (penis, intercourse, urinate).
- crude: mild, bathroom or playground rudeness (fart, butt, crap, piss, boob).
- swear: profanity used as an exclamation or intensifier (damn, shit, fuck, bloody in British use).
- sexual: explicit slang for sex acts, sexual body parts or sexual matters (beyond crude).
- insult: aimed at a person's character, intelligence or looks, but not at a group they belong to (idiot, jerk).
- slur: attacks people for their race, ethnicity, nationality, religion, sexuality, gender or disability.

The kind for the whole word:
- If its main (most common) meanings are clean but another meaning is rude: double (box, screw, cock, pussy).
- Otherwise the rudest kind among its main meanings, in this order from mildest: clean, clinical, crude, insult, \
swear, sexual, slur.
- A form of a word (a plural, a past tense) is judged like the word itself.

The meanings given are from Wiktionary and may be shortened or incomplete: use your own knowledge of the word as \
well, including meanings not listed. Judge English as it is used today. Give one kind per numbered meaning, in \
order, and a confidence from 0 to 100 that the word's kind is right (below 80 means a person should check it). \
Keep each note to a few words, only when it helps (e.g. "rude only in slang", "dated slur")."""

SCHEMA = {
    "type": "object",
    "properties": {"words": {"type": "array", "items": {
        "type": "object",
        "properties": {"word": {"type": "string"},
                       "meanings": {"type": "array", "items": {"type": "string", "enum": list(SENSE_CATEGORIES)}},
                       "kind": {"type": "string", "enum": list(CATEGORIES)},
                       "confidence": {"type": "integer"},
                       "note": {"type": "string"}},
        "required": ["word", "meanings", "kind", "confidence", "note"],
        "additionalProperties": False}}},
    "required": ["words"],
    "additionalProperties": False,
}


SYSTEM_SECOND = """Each English word below has already been sorted by how rude it is, but that answer was unsure. \
The kinds are: clean (nothing rude), double (an innocent main meaning with a rude slang one), clinical (the proper \
word for a body part, bodily function or sexual matter), crude (mild bathroom or playground rudeness), swear \
(profanity), sexual (explicit sexual slang), insult (aimed at a person, not a group), slur (attacks a group).

For each word, say which kind it most likely is IF the given answer is wrong (never the same kind as the given \
answer), and the chance (0-100) that this other kind is in fact the right one. The meanings shown may be \
incomplete: use your own knowledge of the word too."""

SCHEMA_SECOND = {
    "type": "object",
    "properties": {"words": {"type": "array", "items": {
        "type": "object",
        "properties": {"word": {"type": "string"},
                       "second": {"type": "string", "enum": list(CATEGORIES)},
                       "chance": {"type": "integer"}},
        "required": ["word", "second", "chance"],
        "additionalProperties": False}}},
    "required": ["words"],
    "additionalProperties": False,
}
OUT_PER_WORD_SECOND = 50    # its answer is short

SECOND_MIN = 25     # a second choice less likely than this (%) is not worth a person's check (the user's choice)


def to_check(answer, below, second_min=SECOND_MIN):
    """True if a word's answer is for checking by hand (obscene.check_reason: unsure, with a second choice that
    would change what happens to the word, or Claude's whole-word answer and the first meaning disagree)."""
    kind, conf, senses, _n, _m, second = answer
    return check_reason(kind, conf, senses, second, below, second_min) is not None


# ---- which words go -------------------------------------------------------------------------------------------
def read_save(db_path):
    """{word: (rank, obscene, definition text)} for every word in the save (read-only)."""
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return {w: (rank, obscene, text) for w, rank, obscene, text in db.execute(
            "SELECT w.word, w.rank, w.obscene, d.text FROM words w LEFT JOIN defs d ON d.word = w.word")}
    finally:
        db.close()


def list_words(cache_dir, log=print):
    """{list name: set of words} of the public lists (downloaded once into cache_dir; a list that cannot be fetched is
    left out, with a note)."""
    out = {}
    os.makedirs(cache_dir, exist_ok=True)
    for name, url in LISTS.items():
        path = os.path.join(cache_dir, name + ".txt")
        if not os.path.exists(path):
            if os.environ.get(OFFLINE_ENV):
                continue
            try:
                with urllib.request.urlopen(url, timeout=30) as r:
                    data = r.read().decode("utf-8")
            except OSError as e:
                log(f"  ({name} could not be fetched, left out: {e})")
                continue
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        if name == "hurtlex":                                  # id, pos, category, stereotype, lemma, level
            words = {ln.split("\t")[4] for ln in lines[1:] if ln.count("\t") >= 5}
        else:
            words = set(lines)
        out[name] = {w.strip().lower() for w in words if w.strip()}
    return out


def form_target(text):
    """The word every meaning of `text` is a form of ("plural of bitch" -> "bitch"), or None."""
    senses = parse_definition(text)
    targets = set()
    for s in senses:
        m = FORM_GLOSS.search(s["text"])
        if not m:
            return None
        targets.add(m.group(1).lower().strip(".'\""))
    return targets.pop() if len(targets) == 1 else None


def candidates(save, lists=None):
    """-> ({word: [why ...]} to send, {form: its word} that follow a sent word), commonest first."""
    lists = lists or {}
    why = {}
    for word, (rank, obscene, text) in save.items():
        reasons = []
        if obscene:
            reasons.append("marked")
        senses = parse_definition(text) if text else []
        if any(s["rude"] for s in senses):
            reasons.append("labelled")
        if any(SENSITIVE.search(s["text"]) for s in senses):
            reasons.append("meaning")
        if on_list(word):
            reasons.append("hand list")
        reasons += [name for name, words in lists.items() if word in words]
        if reasons:
            why[word] = reasons
    forms = {}
    for word in list(why):
        target = form_target(save[word][2] or "")
        if target and target != word and target in why:
            forms[word] = target
            del why[word]
    order = sorted(why, key=lambda w: save[w][0])
    return {w: why[w] for w in order}, forms


def prompt_for(words, save):
    """The user message for a group of words: each word with its numbered meanings."""
    parts = []
    for w in words:
        senses = parse_definition(save[w][2] or "") if w in save else []
        lines = [f"WORD: {w}"] + [f"  {i}. {s['text'] if not s['pos'] else '(' + s['pos'] + ') ' + s['text']}"
                                  for i, s in enumerate(senses, 1)]
        if not senses:
            lines.append("  (no meanings stored: use your own knowledge, and give one kind per meaning you know)")
        parts.append("\n".join(lines))
    return "Sort these words:\n\n" + "\n\n".join(parts)


def prompt_second(words, save, done):
    """The user message for the second choice: each word, its meanings and the unsure answer it already has."""
    parts = []
    for w in words:
        kind, conf, senses, _n, _m, _s = done[w]
        meanings = parse_definition(save[w][2] or "") if w in save else []
        lines = [f"WORD: {w}   (answer given: {kind}, {conf}% sure)"]
        for i, m in enumerate(meanings, 1):
            mk = f"  [{senses[i - 1]}]" if i <= len(senses) else ""
            lines.append(f"  {i}. {m['text'] if not m['pos'] else '(' + m['pos'] + ') ' + m['text']}{mk}")
        parts.append("\n".join(lines))
    return "Give the second choice for these words:\n\n" + "\n\n".join(parts)


def request_second(words, save, model, done):
    return {"model": model, "max_tokens": 8000, "system": SYSTEM_SECOND,
            "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA_SECOND}},
            "messages": [{"role": "user", "content": prompt_second(words, save, done)}]}


def request_params(words, save, model):
    return {"model": model, "max_tokens": 16000, "system": SYSTEM,
            "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            "messages": [{"role": "user", "content": prompt_for(words, save)}]}


def groups(words, size=None):
    words, size = list(words), size or GROUP
    return [words[i:i + size] for i in range(0, len(words), size)]


# ---- the answers --------------------------------------------------------------------------------------------
def read_answer(message, words, model=""):
    """{word: (kind, confidence, [meaning kinds], note, model, "")} from one response (the last field is the second
    choice, asked for separately: read_second); words it left out, or a refusal / cut answer, come back with
    confidence 0 (to be checked by hand)."""
    got = {}
    if getattr(message, "stop_reason", None) == "end_turn":
        text = next((b.text for b in message.content if b.type == "text"), "")
        try:
            items = json.loads(text)["words"]
        except (ValueError, KeyError, TypeError):
            items = []
        for item in items:
            w = str(item.get("word", "")).strip().lower()
            if w in words and item.get("kind") in CATEGORIES:
                conf = max(0, min(100, int(item.get("confidence") or 0)))
                senses = [m for m in item.get("meanings", []) if m in SENSE_CATEGORIES]
                got[w] = (item["kind"], conf, senses, str(item.get("note", "")).replace("\t", " ").strip(), model, "")
    reason = getattr(message, "stop_reason", None) or "no answer"
    for w in words:
        got.setdefault(w, ("clean", 0, [], f"not answered ({reason})", model, ""))
    return got


def read_second(message, words):
    """{word: "kind:chance"} from one second-choice response (words it left out are simply missing: asked again
    by the next run)."""
    got = {}
    if getattr(message, "stop_reason", None) == "end_turn":
        text = next((b.text for b in message.content if b.type == "text"), "")
        try:
            items = json.loads(text)["words"]
        except (ValueError, KeyError, TypeError):
            items = []
        for item in items:
            w = str(item.get("word", "")).strip().lower()
            if w in words and item.get("second") in CATEGORIES:
                got[w] = f"{item['second']}:{max(0, min(100, int(item.get('chance') or 0)))}"
    return got


def with_forms(results, forms):
    """Add each form with its word's answer, following a form of a form ("cock-tips" -> "cock-tip" -> "cocktip") to
    the word at the end. A form's earlier answer (in `results`) is never kept: it may be out of date."""
    out = {w: v for w, v in results.items() if w not in forms}
    for form, target in forms.items():
        word, seen = target, {form}
        while word in forms and word not in seen:
            seen.add(word)
            word = forms[word]
        if word in out:
            kind, conf, _, _, model, second = out[word]
            out[form] = (kind, conf, [], f"form of {target}", model, second)
    return out


def write_results(path, results, save):
    """word_categories.tsv: word, kind, confidence, meaning kinds, note, the model that answered, the second choice
    ("insult:30": the likeliest other kind and its chance, for unsure words; see `second`); commonest first."""
    rank = {w: save[w][0] if w in save else 10 ** 9 for w in results}
    with open(path, "w", encoding="utf-8") as f:
        f.write("# word\tkind\tconfidence\tmeanings\tnote\tmodel\tsecond\n")
        for w in sorted(results, key=lambda x: (rank[x], x)):
            kind, conf, senses, note, model, second = results[w]
            f.write(f"{w}\t{kind}\t{conf}\t{','.join(senses)}\t{note}\t{model}\t{second}\n")


def read_results(path):
    return read_categories(path) if os.path.exists(path) else {}


# ---- cost ---------------------------------------------------------------------------------------------------
def estimate(word_groups, save, model, client=None, params=None, out_per_word=OUT_PER_WORD):
    """(input tokens, output tokens, dollars at the batch price). Counts a sample with the API when a client is
    given, else guesses from the length of the text (about 4 characters a token)."""
    if not word_groups:
        return 0, 0, 0.0
    sample = word_groups[: min(5, len(word_groups))]
    params = params or (lambda g: request_params(g, save, model))
    if client is not None:
        per = [client.messages.count_tokens(**{k: v for k, v in params(g).items()
                                               if k in ("model", "system", "messages")}).input_tokens
               + len(json.dumps(params(g)["output_config"]["format"]["schema"])) // 4 for g in sample]
    else:
        per = [len(json.dumps({k: params(g)[k] for k in ("system", "messages", "output_config")})) // 4
               for g in sample]
    tokens_in = int(sum(per) / len(sample) * len(word_groups))
    tokens_out = out_per_word * sum(len(g) for g in word_groups)
    p_in, p_out = PRICES.get(model, PRICES[MODEL])
    return tokens_in, tokens_out, (tokens_in * p_in + tokens_out * p_out) / 2e6


# ---- the run ------------------------------------------------------------------------------------------------
def make_client():
    try:
        import anthropic
    except ImportError:
        sys.exit("This tool needs the anthropic package:  pip install anthropic")
    return anthropic.Anthropic()


def submit(client, word_groups, params, model, state, state_path, log=print):
    """Send the groups as batches (at most 10,000 requests each; params(group) -> a request) and note them in the
    state file."""
    state["model"] = model
    start = len(state["requests"])
    for b in range(0, len(word_groups), 10000):
        reqs = []
        for i, g in enumerate(word_groups[b:b + 10000], start + b):
            cid = f"g{i:06d}"
            state["requests"][cid] = g
            reqs.append({"custom_id": cid, "params": params(g)})
        batch = client.messages.batches.create(requests=reqs)
        state["batches"].append(batch.id)
        save_state(state_path, state)
        log(f"Sent batch {batch.id} ({len(reqs)} requests).")


def collect(client, state, poll=60, log=print, read=None):
    """Wait for every batch to end, then read the answers (read(message, words), by default read_answer with the
    run's model): {word: answer}."""
    results, model = {}, state.get("model", "")
    read = read or (lambda message, words: read_answer(message, words, model))
    for bid in state["batches"]:
        while True:
            batch = client.messages.batches.retrieve(bid)
            if batch.processing_status == "ended":
                break
            c = batch.request_counts
            log(f"  {bid}: {c.succeeded + c.errored} done, {c.processing} still working...")
            time.sleep(poll)
        for r in client.messages.batches.results(bid):             # (a failed request's words are left out:
            if r.result.type == "succeeded":                       # the next run sends them again)
                results.update(read(r.result.message, state["requests"].get(r.custom_id, [])))
    return results


def load_state(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"batches": [], "requests": {}}


def save_state(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def paths(db, second=False):
    """(the results file, the state file of a run: one for the second choices, so both can be under way, the
    folder of the downloaded lists)."""
    folder = os.path.dirname(os.path.abspath(db))
    state = "word_categories.second.state.json" if second else "word_categories.state.json"
    return (os.path.join(folder, "word_categories.tsv"), os.path.join(folder, state),
            os.path.join(folder, ".word_lists"))


def plan(args, log=print):
    """The words to send this time: candidates not answered yet (all of them with --redo; with --recheck, the ones
    answered below the --review confidence, to be answered again, by a stronger model, say; with --second, those
    unsure words that have no second choice yet). Forms are never sent: they follow their word."""
    out_path, _, cache = paths(args.db)
    save = read_save(args.db)
    cands, forms = candidates(save, {} if args.no_lists else list_words(cache, log))
    done = {} if args.redo else read_results(out_path)
    if args.second:                # the unsure words' second choice, from the answers already there
        todo = [w for w in cands if w in done and done[w][1] < args.review and not done[w][5]]
    elif args.recheck:
        todo = [w for w in cands if w in done and done[w][1] < args.review]
    else:
        todo = [w for w in cands if w not in done]
    if args.limit:
        todo = todo[: args.limit]
    return save, cands, forms, done, todo


def main(argv=None, client_factory=make_client, log=print, ask=input):
    ap = argparse.ArgumentParser(description="Sort the rude words into kinds with Claude (a developer's tool).")
    ap.add_argument("command", choices=("estimate", "try", "run", "status"))
    ap.add_argument("words", nargs="*", help="for try: the words to classify")
    ap.add_argument("--db", default=os.path.join(ROOT, "tierlist.db"), help="the save (default: tierlist.db)")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--no-lists", action="store_true", help="leave out the LDNOOBW and HurtLex words")
    ap.add_argument("--limit", type=int, default=0, help="send at most this many words (to try a small run first)")
    ap.add_argument("--redo", action="store_true", help="send again words already answered")
    ap.add_argument("--recheck", action="store_true",
                    help="send again only the words answered below the --review confidence (their new answers replace "
                         "the old): run with a cheap --model first, then --recheck with a stronger one")
    ap.add_argument("--second", action="store_true",
                    help="ask only for the unsure words' second choice (the likeliest other kind), giving Claude the "
                         "answer they already have; a word whose second choice leads to the same outcome (shown, "
                         "smeared, or left out) need not be checked by hand. Nothing is classified again")
    ap.add_argument("--review", type=int, default=REVIEW_BELOW, help="confidence below which a word is to be checked")
    ap.add_argument("--yes", action="store_true", help="do not ask before sending")
    args = ap.parse_args(argv)
    if sum((args.recheck, args.redo, args.second)) > 1:
        ap.error("--recheck, --redo and --second do not go together")
    out_path, state_path, _ = paths(args.db, args.second)

    if args.command == "try":
        save = read_save(args.db) if os.path.exists(args.db) else {}
        words = [w.lower() for w in args.words]
        if not words:
            ap.error("try needs some words")
        client = client_factory()
        for g in groups(words):
            msg = client.messages.create(**request_params(g, save, args.model))
            for w, (kind, conf, senses, note, _m, _s) in read_answer(msg, g, args.model).items():
                log(f"{w:20} {kind:9} {conf:3}  {','.join(senses)}  {note}")
        return 0

    if args.command == "status":
        done = read_results(out_path)
        pending = len(load_state(state_path)["batches"]) + len(load_state(paths(args.db, True)[1])["batches"])
        base = {w: v for w, v in done.items() if not v[3].startswith("form of ")}
        low = sum(1 for v in base.values() if v[1] < args.review)
        asked = sum(1 for v in base.values() if v[1] < args.review and v[5])
        check = sum(1 for v in base.values() if to_check(v, args.review))
        log(f"{len(done):,} words answered ({len(done) - len(base):,} of them forms that follow their word); "
            f"{pending} batch(es) still to collect.")
        log(f"Of the {len(base):,} base words, {low:,} are below {args.review}; {asked:,} of those have a second "
            f"choice. To check by hand: {check:,} (unsure, and no second choice yet or one that leads elsewhere).")
        by = {}
        for v in done.values():
            n, n_low = by.get(v[4] or "?", (0, 0))
            by[v[4] or "?"] = (n + 1, n_low + (v[1] < args.review))
        for model, (n, n_low) in sorted(by.items()):
            log(f"  {model}: {n:,} words, {n_low:,} below {args.review}")
        return 0

    if not os.path.exists(args.db):
        log(f"No save at {args.db} (--db names one).")
        return 1
    save, cands, forms, done, todo = plan(args, log)
    sources = {}
    for reasons in cands.values():
        for r in reasons:
            sources[r] = sources.get(r, 0) + 1
    log(f"{len(cands):,} words to classify (" + ", ".join(f"{n:,} {r}" for r, n in sorted(sources.items())) +
        f"), {len(forms):,} forms that follow their word; {len(done):,} already answered, {len(todo):,} to send"
        + (f" again (answered below {args.review})." if args.recheck else
           " for their second choice (unsure, not asked yet)." if args.second else "."))
    client = client_factory() if args.command == "run" else None
    if args.second:
        params = lambda g: request_second(g, save, args.model, done)  # noqa: E731
    else:
        params = lambda g: request_params(g, save, args.model)  # noqa: E731
    t_in, t_out, cost = estimate(groups(todo), save, args.model, client, params,
                                 OUT_PER_WORD_SECOND if args.second else OUT_PER_WORD)
    log(f"About {t_in:,} tokens in and {t_out:,} out with {args.model} at the batch price: about ${cost:,.2f}.")
    if args.command == "estimate":
        return 0

    state = load_state(state_path)
    earlier = bool(state["batches"])
    if earlier and state.get("model") and state["model"] != args.model:
        log(f"An earlier run with {state['model']} is still to collect: collecting it first. Run this command again "
            "afterwards to send what it asks for.")
    if not earlier:
        if not todo:
            log("Nothing to send.")
        else:
            if not args.yes and ask(f"Send {len(todo):,} words to Claude (about ${cost:,.2f})? [y/N] ").strip().lower() \
                    not in ("y", "yes"):
                log("Nothing sent.")
                return 1
            submit(client, groups(todo), params, args.model, state, state_path, log)
    results, got = dict(done), {}
    if state["batches"]:
        log("Waiting for the answers (most batches end within the hour; you can stop and run this again later)...")
        if args.second:
            got = collect(client, state, log=log, read=read_second)
            for w, second in got.items():
                if w in results:
                    results[w] = results[w][:5] + (second,)
        else:
            got = collect(client, state, log=log)
            results.update(got)
    write_results(out_path, with_forms(results, forms), save)
    check = sum(1 for w, v in results.items() if w not in forms and to_check(v, args.review))
    log(f"Wrote {out_path}: {len(results):,} words. To check by hand: {check:,} (base words; forms follow them).")
    failed = sum(1 for g in state["requests"].values() for w in g if w not in got)
    if failed:
        log(f"No answer for {failed:,} of the words sent; the next run sends them again.")
    if os.path.exists(state_path):
        os.remove(state_path)                          # collected: the next run starts afresh with what is left
    return 0


if __name__ == "__main__":
    sys.exit(main())
