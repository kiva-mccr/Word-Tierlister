"""Colour palette for the word tier list (UI-1). Pure data + tiny helpers: no tkinter import,
so it can be tested anywhere. Light by default; a dark one with the same keys (UI-62), and the tier colours can be
chosen (UI-61). apply(dark, tiers) changes PALETTE, TIER_COLORS and TIER_ROW in place before a window is built
(the App reopens its window to show a change): take colours from them when drawing, never copy one at import."""
import colorsys

LIGHT = {
    "bg":       "#FBF7F4",   # warm cream window background
    "surface":  "#FFFFFF",   # cards, rows, entry fields
    "surface2": "#F4EEF8",   # quiet panels, hover fills (faint lilac)
    "text":     "#3D3A4B",   # main text, soft ink rather than pure black
    "muted":    "#575268",   # secondary text (7:1 on bg, UI-76; it was 5:1)
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

# the dark look (UI-62, asked for; not the default): "Dusk" (UI-77, chosen from mock-ups over the old plum night): a
# warm night, cream text, and the tiers in film-photograph pastels (DUSK_TIERS) unless the save chose its own
DARK = {
    "bg":       "#211E27",
    "surface":  "#2C2833",
    "surface2": "#38333F",
    "text":     "#F1EADF",
    "muted":    "#CBC2B7",
    "disabled": "#746C78",
    "border":   "#3F3946",
    "accent":   "#C2B0D2",
    "accent_text": "#F1EADF",
    "select_bg": "#4A4150",
    "shadow":   "#17151B",
    "ok":       ("#2D4434", "#D3E6C9"),
    "info":     ("#2C2833", "#F1EADF"),
    "warn":     ("#4A3F22", "#F3DFA6"),
    "alert":    ("#4E3424", "#F5CDA8"),
    "bad":      ("#4D2C2E", "#F4C4BE"),
    "better":   "#34473A",
    "worse":    "#4E3233",
    "same":     "#3A3542",
    "left":     "#33394A",
    "right":    "#4C3B2E",
    "neutral":  "#3A3542",
    "required": "#F08A80",
}
PALETTE = dict(LIGHT)

DEFAULT_TIERS = ("#FFB3C1", "#FFCBA4", "#FFF0A8", "#BDEBC8", "#A9DDF5", "#D5C6F5")   # S A B C D F
DUSK_TIERS = ("#E6A39A", "#ECBE93", "#E9D79A", "#B6CCA7", "#A6C0D3", "#C2B0D2")      # the dark look's (UI-77)
TIER_COLORS = list(DEFAULT_TIERS)
LOOK = {"dark": False}          # the look apply() chose last
TIER_TEXT = "#3D3A4B"           # dark ink reads on every tier colour (in the dark look too: the tiers stay pastel)
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


def mix(a, b, t):
    """#RRGGBB part way (t, 0..1) from `a` to `b`."""
    ca, cb = (tuple(int(c.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) for c in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb))


# Browse rows (UI-23): a lighter wash of each tier colour, so a long list reads soft; the selected row
# shows the full tier colour. In the dark look a deeper wash under light text (TIER_ROW_TEXT).
TIER_ROW = [tint(c, 0.55) for c in TIER_COLORS]
TIER_ROW_TEXT = [TIER_TEXT]


def contrast(a, b):
    """WCAG's contrast ratio between two #RRGGBB colours (1 to 21; text wants 4.5, UI-76 aims for about 7)."""
    def lum(h):
        c = [int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        r, g, b = (x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def is_light(color):
    """True for a light colour (a pastel, the light look's surfaces): dark ink reads on it."""
    h = color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55


def ink_on(fill):
    """The text colour for something filled with `fill`: the dark ink on a light one (every tier colour, in the
    dark look too), the look's own text colour on a dark one."""
    return TIER_TEXT if is_light(fill) else PALETTE["text"]


def is_hex(text):
    """True for a colour written #RRGGBB."""
    t = str(text or "")
    return len(t) == 7 and t[0] == "#" and all(ch in "0123456789abcdefABCDEF" for ch in t[1:])


def default_tiers(dark=None):
    """The tier colours a save gets when it has not chosen its own: the light look's pastels, or Dusk's (UI-77).
    dark=None: for the look in use."""
    return DUSK_TIERS if (LOOK["dark"] if dark is None else dark) else DEFAULT_TIERS


def apply(dark=False, tiers=None):
    """Use the dark look or the light one, and these tier colours (six #RRGGBB, else the look's defaults), in place:
    everything that reads PALETTE, TIER_COLORS, TIER_ROW (and TIER_ROW_TEXT[0]) from now on gets them. Call it
    before a window is built; one already built keeps its colours."""
    LOOK["dark"] = bool(dark)
    PALETTE.clear()
    PALETTE.update(DARK if dark else LIGHT)
    good = [c.upper() for c in (tiers or ()) if is_hex(c)]
    TIER_COLORS[:] = good if len(good) == len(DEFAULT_TIERS) else list(default_tiers(dark))
    if dark:
        TIER_ROW[:] = [mix(PALETTE["surface"], c, 0.42) for c in TIER_COLORS]
        TIER_ROW_TEXT[0] = PALETTE["text"]
    else:
        TIER_ROW[:] = [tint(c, 0.55) for c in TIER_COLORS]
        TIER_ROW_TEXT[0] = TIER_TEXT


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


