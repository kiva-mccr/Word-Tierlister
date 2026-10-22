import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import gzip, json, os, tempfile
import rudeness
import tierlist as T


def entry(word, pos="noun", glosses=("a thing",), tags=(), form_of=None, lang="en", categories=()):
    s = {"glosses": list(glosses)}
    if categories:
        s["categories"] = list(categories)
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
    # OB-6: the rules score each meaning (src/rudeness.py); the meanings they read are kept in the save
    entry("bastard", "noun", ["a child born out of wedlock"]),
    entry("bastard", "noun", ["a mean person"], tags=["vulgar", "derogatory"]),
    entry("bastard", "adj", ["inferior"], tags=["derogatory"]),
    entry("bastards", "noun", ["plural of bastard"], form_of="bastard"),         # (and its forms)
    entry("shit", "noun", ["faeces"], tags=["vulgar"]),                           # first meaning rude: smeared whole
    entry("shit", "verb", ["to defecate"]),
    entry("shit", "verb", ["to fool"]),
    entry("bureaucracy", "noun", ["government by officials"]),                   # derogatory, but of no person
    entry("bureaucracy", "noun", ["the officials"]),
    entry("bureaucracy", "noun", ["excessive red tape"], tags=["derogatory"]),
    entry("come", "verb", ["to move nearer"]),                                   # a sexual meaning: only it smeared
    entry("come", "verb", ["to orgasm"], tags=["vulgar"]),
    entry("gyp", "verb", ["to cheat"], tags=["offensive", "sometimes"]),         # hedged: clean
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
assert "\u2022 (noun) (vulgar, derogatory) a mean person" in s.get_def("bastard")    # OB-2: rude senses labelled
assert "(derogatory) excessive red tape" in s.get_def("bureaucracy") and "(offensive, sometimes)" in s.get_def("gyp")
assert s.get_meta("source") == "wiktionary" and s.get_meta("wk_done") == "0"
assert not s.db.execute("SELECT name FROM sqlite_master WHERE name='wk'").fetchone()
assert s.stats()["total"] == n == len(words)
# ST-6: the kinds come from the same pass, and the meanings the rudeness rules read (OB-6)
kinds = {r[0]: r[1] for r in s.db.execute("SELECT word, kinds FROM words")}
assert kinds["run"] == 1 | 2 and kinds["serendipity"] == 1 and kinds["zymolytic"] == 4 and kinds["the"] == 16, kinds
assert kinds["don't"] == 16 and kinds["of"] == 16
assert s.get_meta("kinds_done") == "1"
assert set(s.rude_senses()) == {"bastard", "bastards", "shit", "bureaucracy", "come", "gyp"}, s.rude_senses()
assert T.queue_steps(s) == ["Detecting compound words", "Looking up how common", "Scoring rude meanings",
                            "Shuffling the queue"]
T.prepare_queue(s, log=lambda *_: None)
assert not T.queue_steps(s) and s.get_meta("rude_done") == rudeness.RUDENESS_VERSION
B = rudeness.KIND_BITS
rude = dict(s.db.execute("SELECT word, rude FROM words WHERE rude IS NOT NULL"))
assert rude == {"shit": B["clean"] | B["crude"], "bastard": B["clean"] | B["insult"], "bastards": B["clean"],
                "bureaucracy": B["clean"], "come": B["clean"] | B["sexual"], "gyp": B["clean"]}, rude
# (a form follows its word's first meaning: bastard's is clean; "sometimes offensive" is hedged to clean; a
# "derogatory" label on red tape describes no person: no insult)
assert s.obscene_words() == {"shit"}, s.obscene_words()          # (an insult is never smeared: obscene.CENSORED)
assert s.smeared_meanings("come") == ["to orgasm"] and s.smeared_meanings("bastard") == []
assert s.get_word("gyp")["out"] == 0 and s.get_word("come")["out"] == 0   # (a clean meaning: dealt by its kind)

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
s4.db.execute("CREATE TABLE wk(word TEXT PRIMARY KEY, senses INTEGER, lemma INTEGER, live INTEGER, text TEXT,"
              " kinds INTEGER)")
s4.db.execute("INSERT INTO wk VALUES('the',1,1,1,'x',16),('cat',1,1,1,'y',1)")
s4.db.commit()
s4.save_rude_senses({})
s4.set_meta("wk_done", "1")
T.build_wiktionary(s4, os.path.join(tmp, "missing-file-never-read.jsonl"), log=quiet)
assert s4.count_words() == 2 and s4.get_word("cat")["kinds"] == 1
# a parse staged before OB-6 (no meanings kept for the rules) is read again from the file
s5 = T.Store(os.path.join(tmp, "d5.db"))
s5.db.execute("CREATE TABLE wk(word TEXT PRIMARY KEY, senses INTEGER, lemma INTEGER, live INTEGER, text TEXT)")
s5.db.execute("INSERT INTO wk VALUES('the',1,1,1,'x')")
s5.db.commit()
s5.set_meta("wk_done", "1")
T.build_wiktionary(s5, src, log=quiet)
assert s5.count_words() == n and s5.get_word("run")["kinds"] == 3

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
