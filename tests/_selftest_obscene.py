import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""ST-6: which words are flagged as obscene. The user's rule: most of a word's meanings rude, or its first one
(Wiktionary's labels per meaning), forms of a flagged word too; the hand-picked list stands in until a save has
the labels."""
from obscene import decide, label_lines, obscene_in, on_list, page_senses, tag_marks


def page_marks(wikitext):
    return [mark for mark, _r, _g in page_senses(wikitext)]


# ---- the rule -------------------------------------------------------------------------------------------------
got = decide({"fuck": ["r", "r", "p"], "cunt": ["r"], "slur": ["r", "p", "p"],        # first meaning rude
              "bitch": ["p", "r", "r"],                                              # most meanings rude
              "bureaucracy": ["p", "p", "r"], "come": ["p", "r"], "box": ["p", "p", "p", "r"],   # neither
              "bitches": ["f:bitch"], "fucking": ["f:fuck", "r"], "boxes": ["f:box"],            # forms follow
              "bitchesses": ["f:bitches"]})                                          # (forms of forms too)
assert got == {"fuck", "cunt", "slur", "bitch", "bitches", "fucking", "bitchesses"}, got
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

# ---- kinds by meaning (OB-3..OB-5): what a word's kinds lead to, with the default ticks (Sexual, Slur left out)
from obscene import check_reason, outcome, outcome_text, read_categories, second_outcome, smear_whole, word_kinds
FREAK = ["clean", "insult", "insult", "sexual", "clean"]
assert word_kinds("insult", FREAK) == {"clean", "insult", "sexual"}
assert outcome("insult", FREAK) == "some"                                  # shown, its rude meanings smeared
assert outcome_text("insult", FREAK) == "Shown; 3 of its 5 meanings smeared while censoring"
assert outcome("double", ["clean"] * 4) == "shown"                         # its rude use is not listed: shown
assert outcome("slur", ["clean"] * 5) == "smeared"                         # ("faggot": the slur is its usual use)
assert outcome("sexual", ["sexual", "sexual", "insult"]) == "smeared"      # an insult meaning: dealt, smeared
assert outcome("sexual", ["sexual", "slur"]) == "left out"                 # every meaning of an unticked kind
assert outcome("sexual", ["sexual", "clean"]) == "smeared"                 # its first meaning is rude
assert outcome("sexual", ["clean", "sexual"]) == "some"                    # its first meaning is clean
assert outcome("clinical", ["clinical"]) == "smeared"
assert outcome("insult", FREAK, whole=True) == "smeared" and outcome("sexual", ["sexual", "clean"], whole=False) == "some"
assert outcome("sexual", ["sexual"], ticked={"sexual"}) == "smeared"       # (the ticks are the player's)
assert outcome("clean", ["unsure", "clean"]) == "smeared"                  # unsure counts as rude, never left out
assert smear_whole("clean", ["clean", "clean"]) is False and smear_whole("crude", []) is True
assert second_outcome("insult", FREAK, "clean:30") == "shown" and second_outcome("insult", FREAK, "double:30") == "some"
assert second_outcome("insult", ["insult"], "slur:30") == "left out"
assert check_reason("insult", 90, ["insult", "clean"], "") is None         # sure, and the first meaning agrees
assert check_reason("insult", 70, ["insult"], "") == "Claude was only 70% sure"
assert check_reason("insult", 70, ["insult"], "crude:40") is None           # either way: smeared
assert check_reason("insult", 70, ["insult"], "slur:40") == "Claude was only 70% sure (or else: Slur, 40%)"
assert check_reason("insult", 70, ["insult"], "slur:20") is None            # an unlikely second choice
assert check_reason("insult", 90, FREAK, "").startswith("Claude calls the word Insult, but its first meaning is not")
assert check_reason("clean", 90, ["crude", "clean"], "").endswith("but its first meaning is")
assert check_reason("sexual", 90, ["sexual", "slur"], "") is None           # left out either way
import tempfile, os
tsv = os.path.join(tempfile.mkdtemp(), "word_categories.tsv")
with open(tsv, "w", encoding="utf-8") as f:
    f.write("# word\tkind\tconfidence\tmeanings\tnote\tmodel\tsecond\nfreak\tinsult\t75\tclean,insult\t\tm\tdouble:25\n"
            "freaks\tinsult\t75\t\tform of freak\tm\n")
assert read_categories(tsv) == {"freak": ("insult", 75, ["clean", "insult"], "", "m", "double:25"),
                                "freaks": ("insult", 75, [], "form of freak", "m", "")}
print("OBSCENE OK")
