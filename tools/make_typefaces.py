#!/usr/bin/env python3
"""Fetch the program's two typefaces (UI-73) into src/typefaces/ and tighten their line spacing: Young Serif (the
words) and Atkinson Hyperlegible (everything else), both from Google Fonts under the SIL Open Font Licence, which
allows changed copies (kept under the same licence, with it beside them).

    python tools/make_typefaces.py        # needs the internet and fontTools (pip install fonttools)

The change: as shipped, their lines are tall (Atkinson 1.24 em, Young Serif 1.41 em, against about 1.12 for the old
fonts), and much of the layout is measured in lines, so the window grew by a quarter. Each file's ascent and
descent (hhea, OS/2 typo and win) are set to LINE below: still above every accented capital Atkinson has and below
its deepest descender, and in Young Serif above every ascender (accented capitals reach a little higher; they are
drawn, never cut). Atkinson's digits are made all one width (tabular_digits). Run it again only to change the typefaces; the program reads the files.
"""
import os
import sys
import urllib.request

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
OUT = os.path.join(ROOT, "src", "typefaces")
BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FILES = {   # file -> its folder in google/fonts
    "YoungSerif-Regular.ttf": "youngserif",
    "AtkinsonHyperlegible-Regular.ttf": "atkinsonhyperlegible",
    "AtkinsonHyperlegible-Bold.ttf": "atkinsonhyperlegible",
    "AtkinsonHyperlegible-Italic.ttf": "atkinsonhyperlegible",
    "AtkinsonHyperlegible-BoldItalic.ttf": "atkinsonhyperlegible",
}
LICENCES = {"YoungSerif-OFL.txt": "youngserif", "AtkinsonHyperlegible-OFL.txt": "atkinsonhyperlegible"}
LINE = {"YoungSerif": (920, 230), "AtkinsonHyperlegible": (900, 230)}   # (ascent, descent) in 1/1000 em


def fetch(folder, name):
    with urllib.request.urlopen(BASE + f"{folder}/{name}", timeout=60) as r:
        return r.read()


def tighten(path, ascent, descent):
    """Set the font's line metrics (every table a system may read them from) to ascent / descent, with no line gap."""
    from fontTools.ttLib import TTFont
    f = TTFont(path)
    hhea, os2 = f["hhea"], f["OS/2"]
    hhea.ascent, hhea.descent, hhea.lineGap = ascent, -descent, 0
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = ascent, -descent, 0
    os2.usWinAscent, os2.usWinDescent = ascent, descent
    tabular_digits(f)
    f.save(path)


def tabular_digits(f):
    """Point 0-9 at the font's tabular figures (zero.tf ..), when it has them: Tk cannot ask for the tnum feature,
    and counts that change (the stats line) would otherwise shift what follows them by a pixel or more."""
    names = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
    if not all(n + ".tf" in f.getGlyphOrder() for n in names):
        return
    for table in f["cmap"].tables:
        if table.isUnicode():
            for i, n in enumerate(names):
                if ord("0") + i in table.cmap:
                    table.cmap[ord("0") + i] = n + ".tf"


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, folder in LICENCES.items():
        with open(os.path.join(OUT, name), "wb") as fh:
            fh.write(fetch(folder, "OFL.txt"))
    for name, folder in FILES.items():
        path = os.path.join(OUT, name)
        with open(path, "wb") as fh:
            fh.write(fetch(folder, name))
        tighten(path, *LINE[name.split("-")[0]])
        print("wrote", os.path.relpath(path, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
