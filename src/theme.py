"""Colour palette for the word tier list (UI-1). Pure data + tiny helpers: no tkinter import,
so it can be tested anywhere. Light theme only; a dark theme can be added later as a second
dict with the same keys."""
import colorsys

PALETTE = {
    "bg":       "#FBF7F4",   # warm cream window background
    "surface":  "#FFFFFF",   # cards, rows, entry fields
    "surface2": "#F4EEF8",   # quiet panels, hover fills (faint lilac)
    "text":     "#3D3A4B",   # main text, soft ink rather than pure black
    "muted":    "#6D6880",   # secondary text (>= 4.5:1 on bg)
    "disabled": "#A9A5B5",   # greyed-out button text
    "border":   "#E6DFEA",   # hairlines
    "accent":   "#B8A4F4",   # lilac accent: focus rings, selected states
    "accent_text": "#3D3A4B",
    "select_bg": "#DCD2FA",  # selected row / pressed fill
    "shadow":   "#E9E2E6",   # offset shape under cards
    # feedback messages (toasts): (background, text)
    "ok":       ("#DDF3E4", "#25523A"),
    "info":     ("#FFFFFF", "#3D3A4B"),   # plain messages (skip, undo, zoom): a white card
    "warn":     ("#FFF1C9", "#6B5200"),
    "alert":    ("#FFDCC8", "#6B3210"),
    "bad":      ("#FFD9DF", "#7A2438"),
    # duel / compare buttons
    "better":   "#CDEFD8",
    "worse":    "#FAD3D9",
    "same":     "#EFEAF4",
    "left":     "#DDE7FB",
    "right":    "#FFE6D2",
    "neutral":  "#EFEAF4",
    "required": "#D0364F",   # the classic red asterisk on a required choice (>= 4.5:1 on bg)
}

TIER_COLORS = ["#FFB3C1", "#FFCBA4", "#FFF0A8", "#BDEBC8", "#A9DDF5", "#D5C6F5"]  # S A B C D F
TIER_TEXT = PALETTE["text"]     # dark ink reads on every tier colour
# The bars of the tier chart (UI-13) use the tier pastels themselves, drawn like the tier pills (a faint
# edge of the same hue, so even the pale yellow reads on the cream). By choice, they are not tuned for
# colour-blind separation: every bar has its tier letter under it and its count on top, so no one has to
# tell tiers apart by colour. (A tuned set that passed the validator was tried and dropped: it lost the
# pastel look.)
TIER_BAR = TIER_COLORS


def tint(h, amount):
    """`h` (#RRGGBB) mixed towards white by `amount` (0 = unchanged, 1 = white)."""
    h = h.lstrip("#")
    return "#" + "".join(f"{round(int(h[i:i + 2], 16) + (255 - int(h[i:i + 2], 16)) * amount):02X}" for i in (0, 2, 4))


# Browse rows (UI-23): a lighter wash of each tier colour, so a long list reads soft; the selected row
# shows the full tier colour.
TIER_ROW = [tint(c, 0.55) for c in TIER_COLORS]


def tier_blend(x):
    """The tier colour at x in 0..5 (S..F), blended between neighbouring tiers round the colour wheel (hue,
    saturation and value each go part way), so in-between colours stay as bright as the pastels; mixing the RGB
    channels instead turns them grey. Used by the progress shelf (UI-14)."""
    x = max(0.0, min(float(len(TIER_COLORS) - 1), x))
    lo = int(x)
    hi = min(len(TIER_COLORS) - 1, lo + 1)
    t = x - lo
    (h1, s1, v1), (h2, s2, v2) = _hsv(TIER_COLORS[lo], lo), _hsv(TIER_COLORS[hi], hi)
    r, g, b = colorsys.hsv_to_rgb((h1 + (h2 - h1) * t) % 1.0, s1 + (s2 - s1) * t, v1 + (v2 - v1) * t)
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def _hsv(hexc, tier):
    h = hexc.lstrip("#")
    hue, sat, val = colorsys.rgb_to_hsv(*(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)))
    if tier == 0 and hue > 0.5:          # S's pink sits just before A's peach on the wheel, not after F's lilac
        hue -= 1.0
    return hue, sat, val


