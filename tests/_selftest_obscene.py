import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""Which words are obscene (OB-14): the words on Surge AI's published list (src/wordlists/profanity_en.csv), less the
ordinary words in not_obscene.txt; the save marks them (Store.mark_obscene) and marks them again when the list
changes (obscene.LIST_VERSION)."""
import csv
import os
import tempfile

import obscene
from obscene import LIST_VERSION, obscene_in, is_obscene
from store import Store

# ---- the list, as published -----------------------------------------------------------------------------------
with open(obscene.LIST_FILE, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
assert len(rows) == 1598 and {"text", "severity_rating", "category_1"} <= set(rows[0]), (len(rows), rows[0].keys())
assert os.path.exists(os.path.join(obscene.WORDLISTS, "profanity_en_LICENSE.txt"))     # (MIT: ships with it)
assert len(LIST_VERSION) == 12

for w in ("fuck", "motherfucker", "mother-fucker", "Bullshit", "cunt", "bitch", "ass", "cock", "slut", "faggot",
          "nigger"):
    assert is_obscene(w), w
for w in ("table", "bureaucracy", "assassin", "cocktail", "class", "", "piston", "who're"):
    assert not is_obscene(w), w
# not_obscene.txt clears the ordinary and medical words the list catches (a word kept there never counts)
for w in ("buttermilk", "peter", "sheet", "crow", "finger", "anus", "sperm", "vulva"):
    assert w in {r["text"] for r in rows} and not is_obscene(w), w
cleared = [ln.strip() for ln in open(obscene.NOT_OBSCENE_FILE, encoding="utf-8") if ln.strip() and ln[0] != "#"]
assert cleared and all(c == c.lower() for c in cleared)
assert obscene_in(["table", "shit", "glass", "fucking"]) == ["shit", "fucking"]

# ---- the save marks them, once per list -----------------------------------------------------------------------
s = Store(os.path.join(tempfile.mkdtemp(), "o.db"))
s.insert_words(["table", "shit", "buttermilk", "fuck", "glass"])
s.db.execute("UPDATE words SET obscene=1 WHERE word='glass'")           # (a word the old rules smeared)
assert s.mark_obscene() == 3 and s.obscene_words() == {"shit", "fuck"}
assert s.mark_obscene() == 0
assert s.kind_counts()["obscene"] == 2
assert s.get_word("shit")["out"] == 1 and s.get_word("table")["out"] == 0     # (Obscene words unticked to start with)
s.set_deal(obscene=True)
assert s.get_word("shit")["out"] == 0
s.add_word("motherfuckers")                                                   # (UI-51: an added word: the list decides)
assert "motherfuckers" in s.obscene_words()
assert not s.censored("shit")
s.set_censor(True)
assert s.censored("shit") and not s.censored("table") and not s.censored("")
s.close()

# ---- a save from the rules' time (OB-6..OB-13) drops what they kept -------------------------------------------
path = os.path.join(tempfile.mkdtemp(), "old.db")
s = Store(path)
s.insert_words(["shit", "table"])
s.db.execute("ALTER TABLE words ADD COLUMN rude INTEGER")
s.db.execute("CREATE TABLE rude(word TEXT PRIMARY KEY, senses TEXT NOT NULL, smeared TEXT)")
s.db.execute("INSERT INTO rude VALUES('shit', '[]', NULL)")
s.db.execute("DROP INDEX idx_words_kinds"); s.db.execute("CREATE INDEX idx_words_kinds ON words(kinds, rude)")
for k, v in (("rude_done", "18"), ("rude_senses", "1"), ("deal_rude", "2"), ("censor_kinds", "14"),
             ("obscene_done", LIST_VERSION), ("censor", "1")):
    s.set_meta(k, v)
s.close()
s = Store(path)
names = {r[0]: r[1] for r in s.db.execute("SELECT name, sql FROM sqlite_master")}
assert "rude" not in names and "obscene" in names["idx_words_kinds"] and "rude" not in names["idx_words_kinds"], names
for k in ("rude_done", "rude_senses", "deal_rude", "censor_kinds", "obscene_done"):
    assert s.get_meta(k) is None, k                      # (obscene_done gone: prepare_queue marks the list again)
assert s.get_meta("censor") == "1"                       # (the user's own choices stay)
s.close()

print("OBSCENE OK")
