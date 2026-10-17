"""Typography for the word tier list (UI-2): one friendly font family and a small set of named
size roles, shared as tkinter Font objects. Call init_fonts(root) once after creating the Tk root
(calling it again for a new root rebuilds everything); then use font("word"), font("body"), ..."""
import tkinter.font as tkfont

# First installed family wins. Rounded/friendly ones first, then clean system UI fonts.
PREFERRED = ["Nunito", "Quicksand", "SF Pro Rounded", "Segoe UI", "Helvetica Neue", "Helvetica"]
FALLBACK = "Helvetica"

# role -> (size, weight). Sizes match the old hard-coded ones so the layout does not move.
ROLES = {
    "word":   (64, "bold"),    # the word being sorted
    "pair":   (38, "bold"),    # the two words in a duel
    "vs":     (24, "normal"),
    "tier":   (20, "bold"),    # S..F buttons
    "choice": (18, "bold"),    # Better / Same / Worse
    "title":  (18, "normal"),
    "head":   (14, "bold"),    # headings inside text panes, small badges
    "label":  (13, "normal"),  # toast messages, action buttons
    "body":   (12, "normal"),  # everything else
}

_family = FALLBACK
_fonts = {}
_root = None   # the root the current fonts belong to, so init_fonts() is a no-op the second time


def pick_font_family(available, preferred=PREFERRED, fallback=FALLBACK):
    """Return the first preferred family present in `available` (case-insensitive), else fallback."""
    have = {f.lower(): f for f in available}
    for name in preferred:
        if name.lower() in have:
            return have[name.lower()]
    return fallback


def init_fonts(root):
    """Pick the family for this machine and build the shared Font objects (once per root)."""
    global _family, _root
    if root is _root and _fonts:
        return _family
    _root = root
    _family = pick_font_family(tkfont.families(root))
    _fonts.clear()
    for role, (size, weight) in ROLES.items():
        _fonts[role] = tkfont.Font(root=root, family=_family, size=size, weight=weight)
    return _family


def scale_fonts(factor):
    """Resize every role font to `factor` x its base size (1.0 = normal). Widgets using them follow at once."""
    for role, (size, _weight) in ROLES.items():
        if role in _fonts:
            _fonts[role].configure(size=max(7, int(round(size * factor))))


def family():
    """Name of the font family chosen by init_fonts()."""
    return _family


def font(role):
    """The shared Font object for a role. init_fonts(root) must have been called."""
    return _fonts[role]
