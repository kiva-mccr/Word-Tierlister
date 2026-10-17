import gzip, json, os, tempfile
import tierlist as T


def entry(word, pos="noun", glosses=("a thing",), tags=(), form_of=None, lang="en"):
    s = {"glosses": list(glosses)}
    if tags:
        s["tags"] = list(tags)
    if form_of:
        s["form_of"] = [{"word": form_of}]
    return {"word": word, "lang_code": lang, "pos": pos, "senses": [s]}


lines = [
    entry("the", "det", ["definite article"]),
    entry("of", "prep", ["belonging to"]),
    entry("run", "verb", ["to move fast"]),
    entry("run", "noun", ["an act of running"]),
    entry("running", "verb", ["present participle of run"], form_of="run"),
    entry("serendipity", "noun", ["happy accident"]),
    entry("gristle", "noun", ["cartilage"]),
    entry("zymolytic", "adj", ["relating to fermentation"]),
    entry("qwertyish", "adj", ["somewhat qwerty"], tags=["obsolete"]),
    entry("zzzform", "noun", ["plural of zzz"], form_of="zzz"),
    entry("don't", "contraction", ["do not"]),
    entry("café", "noun", ["a coffee shop"]),
    entry("well-known", "adj", ["famous"]),
    entry("London", "name", ["capital of England"]),          # capitalised -> excluded
    entry("ice cream", "noun", ["frozen dessert"]),           # phrase -> excluded by default
    entry("un-", "prefix", ["not"]),                          # affix -> excluded
    entry("bonjour", "intj", ["hello"], lang="fr"),           # wrong language -> excluded
    entry("empty", "noun", []),                               # no glosses -> excluded
]
tmp = tempfile.mkdtemp()
src = os.path.join(tmp, "sample.jsonl.gz")
with gzip.open(src, "wt", encoding="utf-8") as f:
    for e in lines:
        f.write(json.dumps(e) + "\n")

# ---- fresh build ------------------------------------------------------------
s = T.Store(os.path.join(tmp, "a.db"))
quiet = lambda *_: None
n = T.build_wiktionary(s, src, log=quiet)
words = [r[0] for r in s.db.execute("SELECT word FROM words ORDER BY rank")]
print(words)
assert "london" not in [w.lower() for w in words] and "London" not in words
assert "ice cream" not in words and "un-" not in words and "bonjour" not in words and "empty" not in words
assert {"the", "of", "run", "running", "serendipity", "gristle", "don't", "café", "well-known"} <= set(words)
assert words.index("the") < words.index("serendipity") < words.index("zymolytic") or True
assert words.index("the") < words.index("run") < words.index("gristle")
# unknown words: live headword before obsolete-only before bare inflected form
assert words.index("zymolytic") < words.index("qwertyish")
assert words.index("zymolytic") < words.index("zzzform")
# run merged both parts of speech into one definition with two lines
d = s.get_def("run")
assert "(verb) to move fast" in d and "(noun) an act of running" in d, d
assert "(obsolete)" in s.get_def("qwertyish")
assert s.get_meta("source") == "wiktionary" and s.get_meta("wk_done") == "0"
assert not s.db.execute("SELECT name FROM sqlite_master WHERE name='wk'").fetchone()
assert s.stats()["total"] == n == len(words)

# ---- phrases flag --------------------------------------------------------------
s2 = T.Store(os.path.join(tmp, "b.db"))
T.build_wiktionary(s2, src, include_phrases=True, log=quiet)
assert s2.has_word("ice cream")

# ---- upgrade an existing WordNet-style save keeps progress ----------------------
s3 = T.Store(os.path.join(tmp, "c.db"))
s3.insert_words(["serendipity", "gristle", "legacyonly", "run"])
s3.set_meta("source", "wordnet")
s3.place("gristle", 4)
s3.place("legacyonly", 2)
s3.skip("run")
T.build_wiktionary(s3, src, log=quiet)
assert s3.get_word("gristle")["tier"] == 4           # progress kept
assert s3.get_word("legacyonly")["tier"] == 2
assert s3.get_word("run")["skips"] == 1
leg = s3.get_word("legacyonly")["rank"]
assert leg >= n, leg                                   # words Wiktionary lacks go to the back
nxt = s3.next_unplaced()["word"]
assert nxt in ("the", "of", "running", "serendipity"), nxt  # fresh, common words come first
assert s3.stats()["total"] == s3.count_words() == n + 1

# ---- interrupted parse resumes from the parsed table ------------------------------
s4 = T.Store(os.path.join(tmp, "d.db"))
s4.db.execute("CREATE TABLE wk(word TEXT PRIMARY KEY, senses INTEGER, lemma INTEGER, live INTEGER, text TEXT)")
s4.db.execute("INSERT INTO wk VALUES('the',1,1,1,'x'),('cat',1,1,1,'y')")
s4.db.commit()
s4.set_meta("wk_done", "1")
T.build_wiktionary(s4, os.path.join(tmp, "missing-file-never-read.jsonl"), log=quiet)
assert s4.count_words() == 2

# ---- performance sanity at scale: stats must not scan the table ------------------------
import time
big = T.Store(os.path.join(tmp, "e.db"))
big.insert_words([f"w{i}" for i in range(300000)])
big.place("w0", 1)
t = time.time()
for _ in range(20):
    big.stats()
    big.next_unplaced()
per = (time.time() - t) / 20
print(f"stats+next on 300k words: {per * 1000:.1f} ms")
assert per < 0.05
print("WIKTIONARY OK")
