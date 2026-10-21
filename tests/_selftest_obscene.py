import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""ST-6: which words are flagged as obscene. The user's (loose) rule: any of a word's meanings rude by Wiktionary's
labels, forms of a flagged word too (the review by hand then decides); the hand-picked list stands in until a
save has the labels."""
from obscene import decide, label_lines, obscene_in, on_list, page_marks, page_senses, tag_marks

# ---- the rule -------------------------------------------------------------------------------------------------
got = decide({"fuck": ["r", "r", "p"], "cunt": ["r"], "bitch": ["p", "r", "r"],
              "bureaucracy": ["p", "p", "r"], "box": ["p", "p", "p", "r"],           # one rude meaning is enough
              "table": ["p", "p"], "tables": ["f:table"],                            # none: not flagged
              "bitches": ["f:bitch"], "boxes": ["f:box"], "bitchesses": ["f:bitches"]})   # forms follow (of forms too)
assert got == {"fuck", "cunt", "bitch", "bureaucracy", "box", "bitches", "boxes", "bitchesses"}, got
# the Wiktionary download's tags (kaikki.org): rude labels, hedged ones, forms
assert tag_marks({"tags": ["vulgar", "slang"]}) == "r" and tag_marks({"tags": ["derogatory"]}) == "r"
assert tag_marks({"tags": ["ethnic", "slur"]}) == "r" and tag_marks({"raw_tags": ["pejorative"]}) == "r"
assert tag_marks({"tags": ["offensive", "sometimes"]}) == "p"                        # "sometimes offensive"
assert tag_marks({"tags": ["slang"]}) == "p" and tag_marks({"form_of": [{"word": "bitch"}], "tags": ["plural"]}) == "f:bitch"
# a page's wikitext (a save whose download is gone): the English section's sense lines, in order
page = """==English==
===Etymology 1===
====Noun====
{{en-noun}}

# {{lb|en|now|rare}} A female [[dog]].
#: {{ux|en|The bitch had a litter.}}
# {{lb|en|vulgar|derogatory}} A [[malicious]] woman.
#* {{quote-book|en|year=1999|passage=...}}
## {{lb|en|vulgar|slang}} A [[complaint]].
# {{lb|en|sometimes|offensive}} A man who is weak.

====Verb====
# {{lb|en|vulgar|intransitive}} To [[complain]].

==French==
===Noun===
# {{lb|fr|vulgar}} not English: never read
"""
assert page_marks(page) == ["p", "r", "r", "p", "r"], page_marks(page)
forms = "==English==\n===Noun===\n# {{plural of|en|bitch}}\n\n===Verb===\n# {{en-third-person singular of|bitch}}\n"
assert page_marks(forms) == ["f:bitch", "f:bitch"]
assert page_marks("==German==\n# {{lb|de|vulgar}} x\n") == [] and page_marks("") == []
assert page_marks("==English==\n# {{lb|en|pejorative}} red tape\n") == ["r"]
assert page_marks("==English==\n# {{lb|en|mildly vulgar}} x\n# {{lb|en|potentially|offensive}} y\n") == ["p", "p"]
# OB-2: the senses' glosses as plain text, and the rude labels put on the stored definition's matching lines
senses = page_senses("==English==\n# A [[container]] with flat sides.\n# {{lb|en|vulgar|slang}} The [[vagina|vagina]]"
                     "; also {{l|en|a woman}} considered sexually.<ref>x</ref>\n# {{lb|en|sometimes|offensive}} To hit.\n")
assert senses[0] == ("p", [], "A container with flat sides.")
assert senses[1] == ("r", ["vulgar"], "The vagina; also a woman considered sexually."), senses[1]
assert senses[2][0] == "p"
stored = ("\u2022 (noun) A box: a container with flat sides.\n\u2022 (noun) The vagina; also, a woman considered "
          "sexually.\n\u2022 (verb) To hit someone.")
assert label_lines(stored, senses).splitlines() == ["\u2022 (noun) A box: a container with flat sides.",
    "\u2022 (noun) (vulgar) The vagina; also, a woman considered sexually.", "\u2022 (verb) To hit someone."]
assert label_lines(stored, senses[:1]) is None and label_lines(None, senses) is None      # nothing rude / no text
assert label_lines("\u2022 (noun) Something else entirely.", senses) is None               # a loose match labels nothing
assert label_lines(label_lines(stored, senses), senses) is None                            # (already labelled)

# ---- the hand-picked list (until the labels are in) --------------------------------------------------------
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
