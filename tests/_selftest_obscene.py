import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""ST-6: which words are obscene (obscene.py's list chosen by hand, not Wiktionary's labels, which caught
"bureaucracy", "box" and "screw")."""
from obscene import is_obscene, obscene_in

for w in ("fuck", "motherfuckers", "mother-fucker", "bullshit", "dipshit", "bitch", "bitchy", "bitches", "bitch's",
          "asshole", "ass", "asses", "slutty", "sluttish", "pissed", "crapping", "titties", "twat", "twats", "cunt",
          "dumbass", "wanker", "fuck'em"):
    assert is_obscene(w), w
for w in ("bureaucracy", "class", "bass", "assassin", "assume", "cocktail", "cock", "tit", "dyke", "scrap",
          "piston", "title", "button", "therapist", "dickens", "spicy", "spices", "snigger", "sniggering", "niggardly",
          "swanky", "saltwater", "wristwatch", "shiitake", "shitake", "mishit", "who're", "craps", "dicker",
          "crappie", "beanery", "come", "screw", "box", "ball", "head", "hole", "prick", "damning", "glass"):
    assert not is_obscene(w), w
assert obscene_in(["table", "shit", "glass", "fucking"]) == ["shit", "fucking"]
print("OBSCENE OK")
