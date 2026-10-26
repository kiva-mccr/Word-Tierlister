#!/usr/bin/env python3
"""Draw the program's icon (IC-1) into src/icons/: the progress shelf's six spines in the tier colours, S to F, on
the cream tile with rounded corners and a slightly darker border, the lilac shelf mark over the fourth spine. The user
chose this design.

    python tools/make_icon.py          # icon-16.png .. icon-256.png, icon-1024.png, icon.ico, icon.icns (needs Pillow)

Each size is drawn from the shapes, four times over and scaled down (never one big picture shrunk), so the small
ones stay crisp. The colours are the light look's defaults (theme.LIGHT, DEFAULT_TIERS), whatever the user picked:
the icon is the program's, not the save's. Run it again only to change the icon; the program reads the files.
"""
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(ROOT, "src"))
from theme import DEFAULT_TIERS, LIGHT, mix  # noqa: E402

OUT = os.path.join(ROOT, "src", "icons")
SIZES = (16, 24, 32, 48, 64, 128, 256)          # the window / taskbar sizes, and the .ico's
BIG = 1024                                      # for the Linux launcher and anything larger
EDGE = mix(LIGHT["bg"], LIGHT["text"], 0.22)    # the tile's border: the cream, a little darker (IC-4)


def rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def draw(size, ss=4):
    """The icon, `size` pixels square (RGBA: see-through outside the tile's rounded corners)."""
    from PIL import Image, ImageDraw
    text = LIGHT["text"]
    S = size * ss
    L = S / 4.65                                   # one "line" of text, the shelf's unit (as in ui_chart.Bookshelf)
    sw, gap, ow = 0.62 * L, 0.09 * L, 0.0625 * L   # spine width, gap between spines, outline width
    hmax, step = 2 * L, 0.125 * L                  # tallest spine; uneven tops, like real books
    mh = 0.38 * L
    mw = 1.5 * mh + 0.06 * L                       # the mark's triangle
    rise = 0.35 * L
    width = 6 * sw - gap
    height = mh + rise + hmax + 0.2 * L
    x0, top = (S - width) / 2, (S - height) / 2 + mh + rise
    base = top + hmax
    snap = lambda v: round(v / ss) * ss          # (edges on whole pixels of the final size: crisp when small)
    if size <= 32:                                 # small: spines a whole number of pixels, a pixel apart, no outline
        tiny = size < 20                           # (16 px: two pixels a spine, side by side; their colours part them)
        sw = (2 if tiny else max(3, round(sw / ss))) * ss
        gap, ow = (0 if tiny else ss), 0
        width = 6 * sw - gap
        x0 = snap((S - width) / 2)
        mw = (3 if tiny else max(5, round(mw / ss) | 1)) * ss    # (an odd width: its point on one pixel)
        mh = mw / 2 + ss / 2
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    edge = max(ss, round(S * 0.024))               # a slightly darker border (IC-4, asked for: it stands out on
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=round(S * 0.22), fill=rgb(LIGHT["bg"]),     # any background)
                        outline=rgb(EDGE), width=edge)
    for k, col in enumerate(DEFAULT_TIERS):
        x1 = x0 + k * sw
        full = hmax - (k % 3) * step
        box = [snap(x1), snap(base - full), snap(x1 + sw - gap) - 1, snap(base) - 1]
        if ow:
            d.rectangle(box, fill=rgb(col), outline=rgb(mix(col, text, 0.18)), width=max(1, round(ow)))
        else:
            d.rectangle(box, fill=rgb(mix(col, text, 0.08)))
    board = mix(LIGHT["border"], text, 0.25)
    bh = max(ss, snap(0.125 * L))
    d.rectangle([snap(x0 - 0.06 * L), snap(base), snap(x0 + width + 0.06 * L) - 1, snap(base) + bh - 1], fill=rgb(board))
    cx = x0 + 3 * sw + (sw - gap) / 2              # the mark, over the fourth spine (C)
    ty = snap(top - rise * 0.55 - mh)
    d.polygon([(cx - mw / 2, ty), (cx + mw / 2, ty), (cx, ty + mh)], fill=rgb(mix(LIGHT["accent"], text, 0.3)))
    return im.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    images = {n: draw(n) for n in SIZES + (BIG,)}
    for n, im in images.items():
        im.save(os.path.join(OUT, f"icon-{n}.png"), optimize=True)
    small = [images[n] for n in SIZES]
    small[-1].save(os.path.join(OUT, "icon.ico"), sizes=[(n, n) for n in SIZES], append_images=small[:-1])
    # the macOS program's own icon (an app bundle's .icns), from the same drawings
    images[BIG].save(os.path.join(OUT, "icon.icns"), append_images=[images[n] for n in (16, 32, 64, 128, 256)])
    print(f"Wrote {len(images)} PNGs, icon.ico and icon.icns into {os.path.relpath(OUT, ROOT)}.")


if __name__ == "__main__":
    main()
