#!/usr/bin/env python3
"""Fetch the program's two typefaces (UI-73) into src/typefaces/ and tighten their line spacing: Young Serif (the
words) and Atkinson Hyperlegible (everything else), both from Google Fonts under the SIL Open Font Licence, which
allows changed copies (kept under the same licence, with it beside them).

    python tools/make_typefaces.py        # needs the internet and fontTools (pip install fonttools)

The change: as shipped, their lines are tall (Atkinson 1.24 em, Young Serif 1.41 em, against about 1.12 for the old
fonts), and much of the layout is measured in lines, so the window grew by a quarter. Each file's ascent and
descent (hhea, OS/2 typo and win) are set to LINE below: still above every accented capital Atkinson has and below
its deepest descender, and in Young Serif above every ascender (accented capitals reach a little higher; they are
drawn, never cut). Atkinson's digits are made all one width (tabular_digits). overhang.json lists the letters whose ink
reaches past their own box (write_overhangs). Run it again only to change the typefaces; the program reads the files.
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


FACES = {"YoungSerif-Regular": ("Young Serif", "normal", "roman"),
         "AtkinsonHyperlegible-Regular": ("Atkinson Hyperlegible", "normal", "roman"),
         "AtkinsonHyperlegible-Bold": ("Atkinson Hyperlegible", "bold", "roman"),
         "AtkinsonHyperlegible-Italic": ("Atkinson Hyperlegible", "normal", "italic"),
         "AtkinsonHyperlegible-BoldItalic": ("Atkinson Hyperlegible", "bold", "italic")}


BODY = (100, 480)         # the letters' bodies, in 1/1000 em above the baseline: over the serifs, up to the smear's band's top
#                           (widgets.SMEAR_BODY)


def body_extent(glyphs, name, lo=BODY[0], hi=BODY[1]):
    """(left, right) x of a glyph's ink between heights lo and hi (its body, where the smear's band lies), or None:
    its outline flattened into short lines, each clipped to that slab."""
    from fontTools.pens.basePen import BasePen

    class Slab(BasePen):
        def __init__(self, gs):
            super().__init__(gs)
            self.xs, self.at = [], (0, 0)

        def _seg(self, a, b):
            (x0, y0), (x1, y1) = a, b
            if y0 > y1:
                (x0, y0), (x1, y1) = (x1, y1), (x0, y0)
            if y1 < lo or y0 > hi:
                return
            if y0 == y1:
                self.xs += [x0, x1]
                return
            for y in (max(y0, lo), min(y1, hi)):
                self.xs.append(x0 + (x1 - x0) * (y - y0) / (y1 - y0))

        def _moveTo(self, p):
            self.at = p

        def _lineTo(self, p):
            self._seg(self.at, p)
            self.at = p

        def _curveToOne(self, p1, p2, p3):
            p0, n = self.at, 16
            pts = [tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t ** 2 * c + t ** 3 * d
                         for a, b, c, d in zip(p0, p1, p2, p3)) for t in (k / n for k in range(1, n + 1))]
            for q in pts:
                self._seg(self.at, q)
                self.at = q

        def _qCurveToOne(self, p1, p2):
            p0, n = self.at, 16
            pts = [tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * b + t ** 2 * c for a, b, c in zip(p0, p1, p2))
                   for t in (k / n for k in range(1, n + 1))]
            for q in pts:
                self._seg(self.at, q)
                self.at = q

    pen = Slab(glyphs)
    glyphs[name].draw(pen)
    return (min(pen.xs), max(pen.xs)) if pen.xs else None


def write_overhangs(folder=OUT):
    """overhang.json: for each face ("family|weight|slant"), the letters whose ink reaches past their own box, as
    {letter: [left, right]} in 1/1000 em (Young Serif's j reaches 0.125 em left, its f 0.09 em right). Tk measures
    and repaints text by those boxes, so fonts.text_overhang reads this to smear and repaint the rest (F-32). And
    under "body|..." each letter's room either side of its body (the ink between BODY's heights), so the smear's band
    starts and ends inside the end letters (F-35: at the box's edges it showed as a flat ledge under the smear)."""
    import json
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.ttLib import TTFont
    out = {}
    for name, (family, weight, slant) in FACES.items():
        f = TTFont(os.path.join(folder, name + ".ttf"))
        glyphs, hmtx, upm = f.getGlyphSet(), f["hmtx"], f["head"].unitsPerEm
        found, body = {}, {}
        for code, glyph in f.getBestCmap().items():
            if not chr(code).isprintable() or chr(code).isspace():
                continue
            pen = BoundsPen(glyphs)
            glyphs[glyph].draw(pen)
            if not pen.bounds:
                continue
            left = max(0, -pen.bounds[0]) * 1000 / upm
            right = max(0, pen.bounds[2] - hmtx[glyph][0]) * 1000 / upm
            if left >= 5 or right >= 5:
                found[chr(code)] = [round(left), round(right)]
            ext = body_extent(glyphs, glyph, BODY[0] * upm / 1000, BODY[1] * upm / 1000) if code < 0x250 else None
            if ext:                                         # (Latin letters: the ones words begin and end with)
                body[chr(code)] = [round(ext[0] * 1000 / upm), round((hmtx[glyph][0] - ext[1]) * 1000 / upm)]
        out[f"{family}|{weight}|{slant}"] = found
        out[f"body|{family}|{weight}|{slant}"] = body
    with open(os.path.join(folder, "overhang.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
    write_overhangs()
    print("wrote", os.path.relpath(os.path.join(OUT, "overhang.json"), ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
