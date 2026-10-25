"""Typography for the word tier list (UI-2, UI-73): two typefaces that ship with the program (src/typefaces, both
under the SIL Open Font Licence) and a small set of named roles, shared as tkinter Font objects. Young Serif shows
the words themselves (the card, a duel, a definition's heading); Atkinson Hyperlegible everything else. The text
keeps to three sizes (20, 12 and 10 points) beside the big words. Call init_fonts(root) once after creating the Tk
root (calling it again for a new root rebuilds everything); then use font("word"), font("body"), ...

The typefaces are loaded for this program only (load_typefaces: fontconfig on Linux, a private GDI font on Windows,
CoreText on macOS), never installed. Where that fails the old choice of installed fonts stands in."""
import ctypes
import ctypes.util
import os
import sys
import tkinter.font as tkfont

# the bundled typefaces: beside this file, and in a built program in the folder it unpacks to (PyInstaller puts this
# module's file there; standalone.pyinstaller_args packs "typefaces")
TYPEFACES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "typefaces")
DISPLAY_FAMILY = "Young Serif"              # the words (one weight: never asked for bold)
TEXT_FAMILY = "Atkinson Hyperlegible"       # everything else (regular, bold and both italics)

# Stand-ins when the bundled typefaces cannot be loaded: first installed family wins.
PREFERRED = ["Nunito", "Quicksand", "SF Pro Rounded", "Segoe UI", "Helvetica Neue", "Helvetica"]
FALLBACK = "Helvetica"

# role -> (size in points, weight, face): "display" is Young Serif, "text" Atkinson Hyperlegible. The text keeps to
# 20 / 12 / 10; the word on the card and a duel's two words (which must fit side by side) are the big exceptions.
ROLES = {
    "word":    (64, "normal", "display"),   # the word being sorted
    "pair":    (38, "normal", "display"),   # the two words in a duel
    "heading": (20, "normal", "display"),   # the word heading a definition
    "vs":      (20, "normal", "text"),
    "tier":    (20, "bold", "text"),        # S..F buttons
    "choice":  (20, "bold", "text"),        # Better / Same / Worse
    "title":   (20, "normal", "text"),
    "head":    (12, "bold", "text"),        # headings inside dialogs, tier letters on chips and charts
    "label":   (12, "normal", "text"),      # toast messages, action buttons, tabs
    "body":    (12, "normal", "text"),      # everything else
    "small":   (10, "normal", "text"),      # the card's frequency line
}

_family = FALLBACK                  # the text family in use
_display = FALLBACK                 # the display family in use
_fonts = {}
_root = None   # the root the current fonts belong to, so init_fonts() is a no-op the second time
_loaded = None   # load_typefaces() ran: True when every file loaded


def typeface_files(folder=TYPEFACES):
    """The bundled font files (.ttf), sorted."""
    try:
        return sorted(os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".ttf"))
    except OSError:
        return []


def _load_fontconfig(path):
    lib = ctypes.CDLL(ctypes.util.find_library("fontconfig") or "libfontconfig.so.1")
    lib.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    return bool(lib.FcConfigAppFontAddFile(None, os.fsencode(path)))


def _load_windows(path):
    FR_PRIVATE = 0x10                                # (this process only; gone when it closes)
    return ctypes.windll.gdi32.AddFontResourceExW(ctypes.c_wchar_p(path), FR_PRIVATE, 0) > 0


def _load_mac(path):
    cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    ct = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreText.framework/CoreText")
    cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
    cf.CFURLCreateFromFileSystemRepresentation.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long,
                                                           ctypes.c_bool]
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
    ct.CTFontManagerRegisterFontsForURL.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
    raw = os.fsencode(path)
    url = cf.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
    if not url:
        return False
    try:
        return bool(ct.CTFontManagerRegisterFontsForURL(url, 1, None))   # (1: kCTFontManagerScopeProcess)
    finally:
        cf.CFRelease(url)


def load_typefaces(files=None, platform=None):
    """Make the bundled typefaces usable by Tk in this program only (once per process). True when every file loaded;
    a failure is never an error (the installed stand-ins are used)."""
    global _loaded
    if _loaded is not None and files is None:
        return _loaded
    platform = platform or sys.platform
    loader = _load_windows if platform.startswith("win") else _load_mac if platform == "darwin" else _load_fontconfig
    files = typeface_files() if files is None else files
    ok = bool(files)
    for path in files:
        try:
            ok = loader(path) and ok
        except (OSError, AttributeError, TypeError, ValueError):
            ok = False
    _loaded = ok
    return ok


def pick_font_family(available, preferred=PREFERRED, fallback=FALLBACK):
    """Return the first preferred family present in `available` (case-insensitive), else fallback."""
    have = {f.lower(): f for f in available}
    for name in preferred:
        if name.lower() in have:
            return have[name.lower()]
    return fallback


def init_fonts(root):
    """Load the bundled typefaces, pick the families and build the shared Font objects (once per root)."""
    global _family, _display, _root
    if root is _root and _fonts:
        return _family
    _root = root
    load_typefaces()
    available = tkfont.families(root)
    _family = pick_font_family(available, [TEXT_FAMILY] + PREFERRED)
    _display = pick_font_family(available, [DISPLAY_FAMILY], fallback=_family)
    _fonts.clear()
    for role in ROLES:
        size, weight, face = spec(role)
        _fonts[role] = tkfont.Font(root=root, family=_display if face == "display" else _family, size=size,
                                   weight=weight)
    return _family


def spec(role):
    """(size, weight, face) a role is built with: a display role's stand-in (Young Serif missing) is bold, as the
    words were before."""
    size, weight, face = ROLES[role]
    if face == "display" and _display != DISPLAY_FAMILY:
        weight = "bold"
    return size, weight, face


def scale_fonts(factor):
    """Resize every role font to `factor` x its base size (1.0 = normal). Widgets using them follow at once."""
    for role, (size, _weight, _face) in ROLES.items():
        if role in _fonts:
            _fonts[role].configure(size=max(7, int(round(size * factor))))


def family():
    """Name of the text font family chosen by init_fonts()."""
    return _family


def display_family():
    """Name of the display font family (the words) chosen by init_fonts()."""
    return _display


def font(role):
    """The shared Font object for a role. init_fonts(root) must have been called."""
    return _fonts[role]
