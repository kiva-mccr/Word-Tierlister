import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""Which words are obscene (OB-6): the meanings the rules read are picked out of the Wiktionary download
(wordsource.RudeCollector), scored (rudeness.score_saved through wordsource.find_rude), and the short hand-picked
list (obscene.on_list) covers the words they do not."""
import json

import rudeness
from obscene import obscene_in, on_list
from wordsource import RudeCollector, find_rude

B = rudeness.KIND_BITS


def entry(word, glosses, tags=(), pos="noun", form_of=None, categories=()):
    return {"word": word, "pos": pos, "senses": [dict({"glosses": [g], "tags": list(tags),
                                                       "categories": list(categories)},
                                                      **({"form_of": [{"word": form_of}]} if form_of else {}))
                                                 for g in glosses]}


# ---- picking the meanings out of the download ----------------------------------------------------------------
c = RudeCollector()
for w, e in [("bitches", entry("bitches", ["plural of bitch"], form_of="bitch")),     # a form before its word waits
             ("bitch", entry("bitch", ["A female dog."])),
             ("bitch", entry("bitch", ["A malicious woman."], ["vulgar", "derogatory"])),   # (entries one after another)
             ("box", entry("box", ["A container."])),                                  # nothing rude: not kept
             ("boxes", entry("boxes", ["plural of box"], form_of="box")),              # nor its forms
             ("bitchy", entry("bitchy", ["Like a bitch."], pos="adj")),                # a rude root: kept
             ("penis", entry("penis", ["The male organ."], categories=["Genitalia"])),  # a category the rules read
             ("bonk", entry("bonk", ["To have sexual intercourse."], ["slang"]))]:     # the wording (slang: Sexual)
    c.add(w, e)
kept = c.finish()
assert set(kept) == {"bitch", "bitches", "bitchy", "penis", "bonk"}, set(kept)
bitch = json.loads(kept["bitch"])
assert [m["g"] for m in bitch] == ["A female dog.", "A malicious woman."] and bitch[1]["t"] == ["vulgar", "derogatory"]

# ---- scoring them: the kinds of each word's meanings, smeared whole or meaning by meaning ------------------
found = find_rude(["bitch", "bitches", "bitchy", "penis", "bonk", "box", "shit"], kept, log=lambda *_: None)
assert found["penis"] == (B["clinical"], False, []), found["penis"]                  # (Clinical is never smeared)
assert found["bonk"][0] == B["sexual"] and found["bonk"][1], found["bonk"]
assert found["bitch"] == (B["clean"] | B["insult"], False, []), found["bitch"]   # (an insult: shown as it is)
assert found["bitches"][1] == found["bitch"][1]                                      # a form is smeared as its word
assert found["shit"] == (B["swear"], True, []) and "box" not in found                # (no meanings kept: the list)
assert find_rude(["box", "shit"], None, old=["box"]) == {"box": (B["swear"], True, []), "shit": (B["swear"], True, [])}

# ---- the hand-picked list --------------------------------------------------------
for w in ("fuck", "motherfuckers", "mother-fucker", "bullshit", "dipshit", "bitch", "bitchy", "bitches", "bitch's",
          "asshole", "ass", "asses", "slutty", "sluttish", "pissed", "crapping", "titties", "twat", "twats", "cunt",
          "dumbass", "wanker", "fuck'em"):
    assert on_list(w), w
for w in ("bureaucracy", "class", "bass", "assassin", "assume", "cocktail", "cock", "tit", "dyke", "scrap",
          "piston", "title", "button", "therapist", "dickens", "spicy", "spices", "snigger", "sniggering", "niggardly",
          "swanky", "saltwater", "wristwatch", "shiitake", "shitake", "mishit", "who're", "craps", "dicker",
          "crappie", "beanery", "come", "screw", "box", "ball", "head", "hole", "prick", "damning", "glass"):
    assert not on_list(w), w
assert obscene_in(["table", "shit", "glass", "fucking"]) == ["shit", "fucking"]

print("OBSCENE OK")
