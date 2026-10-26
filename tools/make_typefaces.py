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


def contours(glyphs, name, steps=12):
    """A glyph's outline as closed polygons (each curve flattened into `steps` short lines)."""
    from fontTools.pens.basePen import BasePen

    class Flat(BasePen):
        def __init__(self, gs):
            super().__init__(gs)
            self.done, self.cur = [], []

        def _moveTo(self, p):
            self.cur = [p]

        def _lineTo(self, p):
            self.cur.append(p)

        def _curveToOne(self, p1, p2, p3):
            p0 = self.cur[-1]
            self.cur += [tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t ** 2 * c + t ** 3 * d
                               for a, b, c, d in zip(p0, p1, p2, p3)) for t in (k / steps for k in range(1, steps + 1))]

        def _qCurveToOne(self, p1, p2):
            p0 = self.cur[-1]
            self.cur += [tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * b + t ** 2 * c for a, b, c in zip(p0, p1, p2))
                         for t in (k / steps for k in range(1, steps + 1))]

        def _closePath(self):
            if len(self.cur) > 2:
                self.done.append(self.cur)
            self.cur = []

        _endPath = _closePath

    pen = Flat(glyphs)
    glyphs[name].draw(pen)
    return pen.done


def _area(poly):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1])) / 2


def hole_shapes(glyphs, name, points=20):
    """A glyph's holes (the inside of an e, o, a, d: contours wound against its outer one), each as a polygon of
    about `points` points evenly along it: the smear fills them so a counter never shows white through it (F-40)."""
    polys = contours(glyphs, name)
    if len(polys) < 2:
        return []
    outer = max(polys, key=lambda p: abs(_area(p)))
    sign = _area(outer) > 0
    out = []
    for hole in polys:
        a = _area(hole)
        if (a > 0) == sign or abs(a) < 400:                   # (an outer contour, or a speck)
            continue
        step = max(1, len(hole) // points)
        out.append([v for p in hole[::step] for v in (round(p[0]), round(p[1]))])
    return out


def write_overhangs(folder=OUT):
    """overhang.json: for each face ("family|weight|slant"), the letters whose ink reaches past their own box, as
    {letter: [left, right]} in 1/1000 em (Young Serif's j reaches 0.125 em left, its f 0.09 em right). Tk measures
    and repaints text by those boxes, so fonts.text_overhang reads this to smear and repaint the rest (F-32). Under
    "holes|...", each Latin letter's holes as flat lists [x0, y0, x1, y1, ..] from its origin, y up from the
    baseline (hole_shapes, F-40)."""
    import json
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.ttLib import TTFont
    out = {}
    for name, (family, weight, slant) in FACES.items():
        f = TTFont(os.path.join(folder, name + ".ttf"))
        glyphs, hmtx, upm = f.getGlyphSet(), f["hmtx"], f["head"].unitsPerEm
        found, holes = {}, {}
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
            shapes = hole_shapes(glyphs, glyph) if code < 0x250 and slant == "roman" else []   # (Latin letters;
            #                                                       no smear is italic: the file stays small, F-40)
            if shapes:
                holes[chr(code)] = [[round(v * 1000 / upm) for v in shape] for shape in shapes]
        out[f"{family}|{weight}|{slant}"] = found
        if holes:
            out[f"holes|{family}|{weight}|{slant}"] = holes
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
