import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""The rudeness rules (OB-6): points from labels, topics / categories, the definition's wording, WordNet, the
links between words and word families; a meaning's kind; the word's points over the censored kinds. Cases from the tuning against Claude."""
from rudeness import KIND_BITS as KIND_BITS_
from rudeness import MEANING_MIN, WHOLE_MIN, score_sense, score_word, sense_kind, sense_points, word_points


def kind(gloss, tags=(), topics=(), cats=(), pos="noun"):
    return sense_kind(score_sense({"glosses": [gloss], "tags": list(tags), "topics": list(topics),
                                   "categories": [{"name": c} for c in cats]}, pos))


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
assert kind("Urine.", ["childish"]) == "clean"                                          # a softener ("wee-wee")
assert kind("A muscle of the forearm.", topics=["anatomy"]) == "clean"                # anatomy alone: clean
assert kind("Used as an intensifier.", ["vulgar"], pos="adv") == "swear"
assert kind("Damn!", ["vulgar"], pos="intj") == "swear"
assert kind("Darn.", ["euphemistic"], cats=["English swear words"]) == "clean"     # a minced oath: the polite word
assert kind("Darn.", ["vulgar"], cats=["English swear words"]) == "swear"
assert kind("Chess pieces.", ["slang"], cats=["English ethnic slurs"]) != "slur"  # (a category alone: maybe a slip)
assert kind("Sometimes used of a person.", ["sometimes", "offensive"]) == "clean"     # hedged: half as rude
assert kind("A person.", ["offensive"]) == "clean"                                   # (a label alone: a suspect)

# the word's points: its first meaning counts most; only the censored kinds count
rude, clean = {"sexual": 6.0}, {}
assert word_points([rude]) == 6.0 >= WHOLE_MIN and word_points([clean, rude]) < WHOLE_MIN    # rude, but not usually
assert word_points([rude, clean, clean]) >= WHOLE_MIN
assert word_points([{"insult": 5.0}], kinds={"sexual", "slur"}) == 0.0                # Insult not censored
assert sense_points({"insult": 5.0, "crude": 3.0}, {"crude"}) == 3.0
assert word_points([]) == 0.0 and MEANING_MIN < WHOLE_MIN
scored = score_word([{"glosses": ["A container."]}, {"glosses": ["The vagina."], "tags": ["vulgar"]}], "noun", "box")
assert [sense_kind(p) for p in scored] == ["clean", "sexual"] and word_points(scored) < WHOLE_MIN   # shown; smeared meaning

# ---- the links between words (second pass): Wiktionary's synonym lists spread a kind both ways
from rudeness import incoming_links, link_points, rude_kinds_of, score_words
PENIS = ["dick", "johnson", "schlong", "banana", "member"]
words = {
    "dick": [{"glosses": ["The penis."], "tags": ["vulgar"], "synonyms": [{"word": w} for w in PENIS]}],
    "johnson": [{"glosses": ["The penis."], "tags": ["slang"], "categories": ["Genitalia"], "synonyms": [{"word": w} for w in PENIS]}],
    "schlong": [{"glosses": ["A penis."], "tags": ["slang"], "synonyms": [{"word": "dick"}, {"word": "johnson"}]}],
    "banana": [{"glosses": ["An elongated curved fruit."]}, {"glosses": ["The penis."], "tags": ["slang"]}],
    "member": [{"glosses": ["One who belongs to a group."]}, {"glosses": ["A limb; the penis."]}],   # standard English
    "table": [{"glosses": ["A flat surface."], "synonyms": [{"word": "desk"}, {"word": "bench"}]}],
}
first = {w: score_word(s, "noun", w) for w, s in words.items()}
assert sense_kind(first["schlong"][0]) != "sexual" and sense_kind(first["banana"][1]) != "sexual"   # alone: not yet
rude = rude_kinds_of(first)
assert "sexual" in rude["dick"] and "table" not in rude
assert [k for k, _g, src in incoming_links(words, first)["banana"]] == ["sexual", "sexual"]       # (dick, johnson)
added = link_points("banana", words["banana"], rude, incoming_links(words, first))
assert added[0] == {} and added[1].get("sexual", 0) > 0                     # the fruit gains nothing
both = score_words(words, {w: ["noun"] * len(s) for w, s in words.items()})
assert sense_kind(both["schlong"][0]) == "sexual"                            # its synonyms are sexual: outward
assert sense_kind(both["banana"][1]) == "sexual" and sense_kind(both["banana"][0]) == "clean"   # inward
assert sense_kind(both["table"][0]) == "clean"
assert [sense_kind(p) for p in both["member"]] == ["clean", "clinical"]       # synonyms share meaning, not rudeness:
                                                                              # a plain word for it stays the proper one

# WordNet, when installed (never downloaded here): a meaning matched by the words its definition shares
from rudeness import score_word as sw, wordnet, wordnet_match
wn = wordnet()
if wn is None:
    print("(WordNet not installed: its checks skipped)")
else:
    def wkind(word, gloss, pos="noun", tags=()):
        return sense_kind(score_sense({"glosses": [gloss], "tags": list(tags)}, pos, word, wn))
    assert wordnet_match("pee", "To urinate.", "verb", wn) is not None                # a synonym for a gloss
    assert wordnet_match("pig", "A light pinkish-red colour, like that of a pig.", "noun", wn) is None or \
        wkind("pig", "A light pinkish-red colour, like that of a pig.") == "clean"    # not the animal, not a hog
    assert wkind("pee", "To urinate.", "verb") == "crude"                             # (no label on Wiktionary)
    assert wkind("puke", "vomit.") == "crude" and wkind("genitalia", "External sex organs.") == "clinical"
    assert wkind("jackass", "A foolish or stupid person.", tags=["vulgar"]) == "insult"
    assert wkind("table", "A flat surface.") == "clean"
    assert sense_kind(sw([{"glosses": ["To urinate."]}], "verb", "pee", None)[0]) == "clean"   # (without it)

# the fixes from the 50-word sample: plain sex words are Clinical, euphemisms add nothing, a group makes a slur
assert kind("Belonging to the sex which typically produces sperm.") in ("clean", "clinical")
assert kind("A lavatory.", ["euphemistic"]) == "clean"
assert kind("Someone who performs anilingus.", ["slang", "vulgar"]) == "sexual"
assert kind("Welsh person.", ["derogatory"]) == "slur" and kind("A native of the South Pacific islands.", ["derogatory"]) == "slur"
assert kind("A youth of low social standing.", ["derogatory", "offensive"]) == "insult"   # offensive alone: no slur
from rudeness import is_form, form_target
assert is_form({"glosses": ["present participle and gerund of fist"]})
assert form_target({"glosses": ["x"], "alt_of": [{"word": "pum-pum"}]}) == "pum-pum"
assert form_target({"glosses": ["plural of bitch"]}) == "bitch" and form_target({"glosses": ["A dog."]}) is None
assert word_points([{}, {"sexual": 10.0}]) < WHOLE_MIN                          # one very rude later meaning
assert word_points([{}, {"sexual": 6.0}], forms=[True, False]) >= WHOLE_MIN     # (the first only names a word)
# word families: a word built from one whose first meaning is rude gains points towards that kind, a booster only
from rudeness import families
fam = families({"bullshit": ["bull", "shit"]}, {"shit": ["shithead"], "cock": ["cocktail"]})
assert fam == {"bullshit": {"bull", "shit"}, "shithead": {"shit"}, "cocktail": {"cock"}}
W = {"shit": [{"glosses": ["Faeces."], "tags": ["vulgar"]}], "bull": [{"glosses": ["A male bovine."]}],
     "cock": [{"glosses": ["A male chicken."]}, {"glosses": ["A penis."], "tags": ["vulgar", "slang"]}],
     "bullshit": [{"glosses": ["Nonsense."], "tags": ["slang"]}],
     "shithead": [{"glosses": ["A contemptible person."]}], "cocktail": [{"glosses": ["A mixed drink."]}]}
plain = score_words(W)
both = score_words(W, family=fam)
assert sum(both["bullshit"][0].values()) == sum(plain["bullshit"][0].values()) + 2   # from shit, not from bull
assert both["bullshit"][0]["crude"] >= 2                       # (towards shit's kind: Faeces is Crude)
assert both["cocktail"] == plain["cocktail"]                   # (cock's first meaning is the bird)
assert sum(both["shithead"][0].values()) == sum(plain["shithead"][0].values()) + 2  # (listed as derived by shit)
# false matches the user found: "did" (a form of "do", which has a slang meaning), "best" (of "good"), "well: (slang)
# very" (an intensifier, no rude label), "take: to have sex with" (a plain meaning of a word about something else)
import json
from rudeness import compact, meaning_kinds, results, score_saved
W = {"do": [{"glosses": ["To perform."]}, {"glosses": ["To have sex with."], "tags": ["slang"], "categories": ["Sex"]}],
     "did": [{"glosses": ["simple past of do"], "form_of": [{"word": "do"}]}],
     "fuck": [{"glosses": ["To have sexual intercourse."], "tags": ["vulgar"]}],
     "fucked": [{"glosses": ["simple past of fuck"], "form_of": [{"word": "fuck"}]}],
     "take": [{"glosses": ["To grab."]}, {"glosses": ["To have sex with."], "categories": ["Sex"]}],
     "penis": [{"glosses": ["The male organ."], "categories": ["Genitalia"]}]}
got = score_words(W)
assert sense_kind(got["do"][1]) == "sexual" and sense_kind(got["did"][0]) == "clean"      # a form follows the first
assert sense_kind(got["fucked"][0]) == "sexual"                                            # meaning of its word
assert kind("Very (as a general-purpose intensifier).", ["slang"], pos="adv") == "clean"
assert kind("Used as an intensifier.", ["vulgar"], pos="adv") == "swear"
assert meaning_kinds(W["take"], got["take"]) == ["clean", "clean"]                          # (Clinical, but not
assert meaning_kinds(W["penis"], got["penis"]) == ["clinical"]                              # what "take" is about)
assert results("take", W["take"], got["take"], {"sexual"})[0] == KIND_BITS_["clean"]
assert kind("To take the virginity of.", ["euphemistic"], pos="verb") != "sexual"          # (a euphemism: polite)

assert kind("An exclamation used to express pleasant or unpleasant mild surprise.", pos="intj") == "clean"   # "why"
assert kind("The mainstream culture, controlled by the elites.", ["derogatory", "often"]) == "clean"  # "system"
assert kind("Abbreviation of one-shot.", ["alt-of", "derogatory"]) == "clean"
from rudeness import _hedged
assert _hedged(["derogatory", "often"]) == [("derogatory", 0.8)]          # (kaikki sorts labels: hedges apply to all)

# a common word (rudeness.COMMON_ZIPF) is rarely meant rudely: only its strongly labelled meanings count
W = {"top": [{"glosses": ["The highest part."]}, {"glosses": ["Fellatio; a blowjob."], "tags": ["slang"]}],
     "box": [{"glosses": ["A container."]}, {"glosses": ["The vagina."], "tags": ["vulgar"]}]}
got = score_words(W)
assert meaning_kinds(W["top"], got["top"]) == ["clean", "sexual"]
assert meaning_kinds(W["top"], got["top"], common=True) == ["clean", "clean"]
assert meaning_kinds(W["box"], got["box"], common=True) == ["clean", "sexual"]
saved = {w: json.dumps([compact(x, "noun") for x in v]) for w, v in W.items()}
assert score_saved(saved, {"sexual"}, zipf=lambda w: 5.5)["top"][0] == KIND_BITS_["clean"]
assert score_saved(saved, {"sexual"}, zipf=lambda w: 2.0)["top"][0] != KIND_BITS_["clean"]   # (a rare word: counts)

# borrowed ideas, measured on random lists judged by hand (OB-6): a rude label alone is a suspect, not an insult;
# a euphemism is the polite word; a slang meaning that is a rude word, or a short slang name for a body part, is rude
assert kind("Someone unfamiliar with the sea.", ["derogatory"]) == "clean"              # ("landlubber")
assert kind("A stupid, contemptible person.", ["derogatory"]) == "insult"
assert kind("To urinate.", ["euphemistic"], cats=["Bodily functions"], pos="verb") == "clean"   # ("pass water")
W = {"damn": [{"glosses": ["To condemn to hell."], "tags": ["vulgar"], "categories": ["English swear words"]}],
     "dam": [{"glosses": ["A barrier across a river."]}, {"glosses": ["Damn."], "tags": ["slang"]}],
     "unit": [{"glosses": ["A single thing."]}, {"glosses": ["A penis."], "tags": ["slang"]}]}
got = score_words(W)
assert sense_kind(got["dam"][1]) == "swear" and sense_kind(got["dam"][0]) == "clean"
assert sense_kind(got["unit"][1]) == "sexual" and sense_kind(score_words({k: W[k] for k in ("unit",)})["unit"][1])

# the program keeps an entry's meanings compactly, the first with its family; score_saved reads them back
import json
from rudeness import compact_entry, score_saved, KIND_BITS
e = {"word": "shithead", "pos": "noun", "senses": [{"glosses": ["A contemptible person."], "examples": [{"text": "x"}]}],
     "etymology_templates": [{"name": "compound", "args": {"1": "en", "2": "shit", "3": "head"}}]}
c = compact_entry(e)
assert c == [{"g": "A contemptible person.", "pos": "noun", "e": ["shit", "head"]}], c
from rudeness import compact, has_signal
kept = compact({"glosses": ["A penis."], "tags": ["informal", "countable"]}, "noun")    # (informal: read, not a sign)
assert kept["t"] == ["informal"] and not has_signal({"g": "A table.", "t": ["informal"]})
saved = {"shithead": json.dumps(c), "shit": json.dumps(compact_entry(
    {"word": "shit", "pos": "noun", "senses": [{"glosses": ["Faeces."], "tags": ["vulgar"]}]}))}
got = score_saved(saved, {"crude", "swear", "sexual", "slur"})
assert got["shithead"][0] == KIND_BITS["clean"] and got["shit"][1], got         # (an insult alone: an ordinary word)
# a word goes into the rude kinds only when one of its meanings needs censoring; then all its kinds count
both = {"bitch": json.dumps(compact_entry({"word": "bitch", "pos": "noun", "senses": [
    {"glosses": ["A stupid, contemptible person."], "tags": ["derogatory"]},
    {"glosses": ["To complain."], "tags": ["vulgar"]}]}))}
b = score_saved(both, {"crude", "swear", "sexual", "slur"})["bitch"][0]
assert b & KIND_BITS["swear"] and b & KIND_BITS["insult"], b
# a group's own name is no slur (SLUR_MARKS): a word with a plain meaning naming one, "sometimes" rude, a letter-case
# form, or named by the word itself; a slur label, "ethnic" or "vulgar" still makes one
def word_kinds(word, senses):
    return [sense_kind(p) for p in score_word([{"glosses": [g], "tags": list(t)} for g, t in senses], "noun", word)]
assert word_kinds("gay", [("A homosexual, especially a male homosexual.", ()),
                          ("Flamboyant or effeminate in behavior.", ("derogatory", "slang"))])[1] != "slur"
assert kind("Homosexual.", ["colloquial", "derogatory", "sometimes"]) != "slur"                  # ("queer")
assert kind("Alternative letter-case form of Jew.", ["alt-of", "offensive"]) != "slur"          # ("jew")
assert word_kinds("transgender", [("A transgender person", ("offensive", "often"))]) != ["slur"]
assert word_kinds("dyke", [("An earthwork.", ()), ("A lesbian.", ("derogatory", "offensive", "vulgar"))])[1] == "slur"
assert kind("A Jew.", ["ethnic", "offensive", "slur"]) == "slur"                                 # ("kike")
assert kind("Alternative form of Hebe (a Jew).", ["alt-of", "derogatory", "offensive"]) == "slur"   # (not case)
assert kind("A transgender person.", ["derogatory", "offensive", "sometimes"]) == "slur"   # (two labels: "tranner")
print("RUDENESS OK")
