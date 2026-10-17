"""Colour palette for the word tier list (UI-1). Pure data + tiny helpers: no tkinter import,
so it can be tested anywhere. Light theme only; a dark theme can be added later as a second
dict with the same keys."""

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
    # feedback banners: (background, text)
    "ok":       ("#DDF3E4", "#25523A"),
    "info":     ("#EFEAF4", "#4A4560"),
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


def _lum(h):
    """Relative luminance of a #RRGGBB colour (WCAG definition)."""
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    """WCAG contrast ratio between two #RRGGBB colours."""
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)
