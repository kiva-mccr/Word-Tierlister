import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""The rudeness rules (OB-6): points from labels, topics / categories, the definition's wording and the word
itself; a meaning's kind; the word's points over the censored kinds. Cases from the tuning against Claude."""
from rudeness import MEANING_MIN, WHOLE_MIN, score_sense, score_word, sense_kind, sense_points, word_points


def kind(gloss, tags=(), topics=(), cats=(), pos="noun", root=False):
    return sense_kind(score_sense({"glosses": [gloss], "tags": list(tags), "topics": list(topics),
                                   "categories": [{"name": c} for c in cats]}, pos, root))


assert kind("A table.") == "clean" and kind("To arrive.", ["slang"]) == "clean"
assert kind("Rubbish; worthless matter.", ["vulgar"]) == "swear"                      # vulgar alone: a swear word
assert kind("Very good.", ["slang", "vulgar"], pos="adj") == "swear"                   # ("good-ass")
assert kind("To have sexual intercourse with.", ["vulgar"]) == "sexual"
assert kind("The act of defecating.", ["vulgar"]) == "crude"
assert kind("A nasty, despicable person.", ["vulgar"]) == "insult"
assert kind("A stupid person.", ["derogatory"]) == "insult"
assert kind("An Italian person.", ["derogatory"]) == "slur" and kind("An Italian person.") == "clean"
assert kind("A trans woman.", ["derogatory", "offensive"]) == "slur"
assert kind("A person of Chinese descent.", ["ethnic", "slur"]) == "slur"
assert kind("A stupid person.") == "insult" and kind("a stupid person", ["derogatory"]) == "insult"   # (no slur)
assert kind("The penis.", cats=["Genitalia"]) == "clinical"                            # the proper word
assert kind("Penis.", ["slang"], cats=["Genitalia"]) == "sexual"                      # a slang one is not
assert kind("Urine.", ["childish"]) == "crude"
assert kind("A muscle of the forearm.", topics=["anatomy"]) == "clean"                # anatomy alone: clean
assert kind("Used as an intensifier.", ["vulgar"], pos="adv") == "swear"
assert kind("Damn!", ["vulgar"], pos="intj") == "swear"
assert kind("Darn.", ["euphemistic"], cats=["English swear words"]) == "swear"
assert kind("Very; extremely.", root=True) == "clean"                                  # a rude root alone: not enough,
assert kind("Very bad.", ["humorous"], root=True) == "clean"
assert sense_points(score_sense({"glosses": ["Awful."], "tags": ["derogatory"]}, "adj", True)) == 6.0  # but it adds
assert kind("Sometimes used of a person.", ["sometimes", "offensive"]) == "clean"     # hedged: half as rude
assert kind("A person.", ["offensive"]) in ("slur", "insult")

# the word's points: its first meaning counts most; only the censored kinds count
rude, clean = {"sexual": 6.0}, {}
assert word_points([rude]) == 6.0 >= WHOLE_MIN and word_points([clean, rude]) < WHOLE_MIN    # rude, but not usually
assert word_points([rude, clean, clean]) >= WHOLE_MIN
assert word_points([{"insult": 5.0}], kinds={"sexual", "slur"}) == 0.0                # Insult not censored
assert sense_points({"insult": 5.0, "crude": 3.0}, {"crude"}) == 3.0
assert word_points([]) == 0.0 and MEANING_MIN < WHOLE_MIN
scored = score_word([{"glosses": ["A container."]}, {"glosses": ["The vagina."], "tags": ["vulgar"]}], "noun", "box")
assert [sense_kind(p) for p in scored] == ["clean", "sexual"] and word_points(scored) < WHOLE_MIN   # shown; smeared meaning

# WordNet, when installed (never downloaded here): a meaning matched by the words its definition shares
from rudeness import score_word as sw, wordnet, wordnet_match
wn = wordnet()
if wn is None:
    print("(WordNet not installed: its checks skipped)")
else:
    def wkind(word, gloss, pos="noun", tags=()):
        return sense_kind(score_sense({"glosses": [gloss], "tags": list(tags)}, pos, False, word, wn))
    assert wordnet_match("pee", "To urinate.", "verb", wn) is not None                # a synonym for a gloss
    assert wordnet_match("pig", "A light pinkish-red colour, like that of a pig.", "noun", wn) is None or \
        wkind("pig", "A light pinkish-red colour, like that of a pig.") == "clean"    # not the animal, not a hog
    assert wkind("pee", "To urinate.", "verb") == "crude"                             # (no label on Wiktionary)
    assert wkind("puke", "vomit.") == "crude" and wkind("genitalia", "External sex organs.") == "clinical"
    assert wkind("jackass", "A foolish or stupid person.", tags=["vulgar"]) == "insult"
    assert wkind("table", "A flat surface.") == "clean"
    assert sense_kind(sw([{"glosses": ["To urinate."]}], "verb", "pee", None)[0]) == "clean"   # (without it)
print("RUDENESS OK")
