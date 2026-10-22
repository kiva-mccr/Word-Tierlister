"""The keyboard shortcuts (UI-48): one table of every action that has a key, its view and its default keys, and
the user's changes on top (saved in the save as meta "keymap"). No tkinter: the windows turn a key press into a
key name with event_spec() and ask lookup() what it does.

    km = Keymap(store.get_meta("keymap"))
    km.lookup("compare", event_spec("Up", 0))        # -> "better"
    km.display("undo")                               # -> ["Backspace", "Ctrl Z"]
    km.set("later", ["q"]); store.set_meta("keymap", km.dumps())

A key is a string: optional "Ctrl+", "Alt+", "Shift+" (Shift only for keys that have no shifted character of
their own, like Shift+Tab), then the Tk key name with letters in lower case ("Ctrl+z", "Up", "question").
Placing (1-6) is one row that moves as a set: its key is the first of six in a row on the keyboard (1, q, a, z,
F1...), and the other five follow (place_keys()).
"""
import json

GROUPS = (("all", "Everywhere"), ("place", "Place new words"), ("compare", "While comparing"),
          ("duel", "Duels (Refine, Boundary, Conflicts)"), ("browse", "Browse / edit"))
GROUP_NAMES = dict(GROUPS)

# id, group, label, default keys (at most MAX_KEYS)
ACTIONS = (
    ("undo", "all", "Undo", ["BackSpace", "Ctrl+z"]),
    ("defs", "all", "Definition", ["d"]),
    ("next_tab", "all", "Next tab", ["Tab"]),
    ("prev_tab", "all", "Previous tab", ["Shift+Tab"]),
    ("zoom_in", "all", "Zoom in", ["Ctrl+plus", "Ctrl+equal"]),
    ("zoom_out", "all", "Zoom out", ["Ctrl+minus"]),
    ("zoom_reset", "all", "Actual size", ["Ctrl+0"]),
    ("place", "place", "Place in S … F", ["1"]),
    ("compare", "place", "Compare to anchors", ["space"]),
    ("later", "place", "Don't know / later", ["u", "question"]),
    ("find", "place", "Look up a word", ["slash"]),
    ("better", "compare", "Better", ["Up", "b"]),
    ("same", "compare", "Same tier", ["e", "Return", "equal"]),
    ("worse", "compare", "Worse", ["Down", "w"]),
    ("back", "compare", "Back one answer", ["BackSpace"]),
    ("stop", "compare", "Stop comparing", ["space", "Escape"]),
    ("left", "duel", "Left wins", ["Left", "a"]),
    ("right", "duel", "Right wins", ["Right", "l"]),
    ("tie", "duel", "Tie", ["Down", "t"]),
    ("skip", "duel", "Skip pair", ["s"]),
    ("unplace", "browse", "Unplace the selected word", ["Delete"]),
)
MAX_KEYS = 3
GROUP_OF = {a: g for a, g, _l, _k in ACTIONS}
LABEL_OF = {a: lab for a, _g, lab, _k in ACTIONS}
DEFAULTS = {a: list(k) for a, _g, _l, k in ACTIONS}

# keys the program needs for itself: the header menus open with Alt+F / E / V / S, and F10 opens File
RESERVED = {"Alt+f": "opens the File menu", "Alt+e": "opens the Edit menu", "Alt+v": "opens the View menu",
            "Alt+s": "opens the Settings menu", "F10": "opens the File menu"}

# keyboard rows for the placing set (the first key and the five after it)
ROWS = ("1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm", [f"F{i}" for i in range(1, 13)])
SET = 6

# key names as they read on screen; anything else: a letter in capitals, or the Tk name as it is
NAMES = {"BackSpace": "Backspace", "space": "Space", "Return": "Enter", "Escape": "Esc", "Delete": "Delete",
         "Tab": "Tab", "Up": "↑", "Down": "↓", "Left": "←", "Right": "→", "question": "?",
         "plus": "+", "minus": "−", "equal": "=", "comma": ",", "period": ".", "slash": "/",
         "semicolon": ";", "apostrophe": "'", "bracketleft": "[", "bracketright": "]", "backslash": "\\",
         "grave": "`", "exclam": "!", "at": "@", "numbersign": "#", "dollar": "$", "percent": "%",
         "asciicircum": "^", "ampersand": "&", "asterisk": "*", "parenleft": "(", "parenright": ")",
         "underscore": "_", "colon": ":", "quotedbl": '"', "less": "<", "greater": ">", "bar": "|",
         "braceleft": "{", "braceright": "}", "asciitilde": "~", "Home": "Home", "End": "End",
         "Prior": "Page Up", "Next": "Page Down", "Insert": "Insert"}
SHORT = {"BackSpace": "Bksp"}               # in the small hints on the buttons
# the keypad types the same as the main keys
KEYPAD = {"KP_Add": "plus", "KP_Subtract": "minus", "KP_Enter": "Return", "KP_Multiply": "asterisk",
          "KP_Divide": "slash", "KP_Decimal": "period", "KP_Equal": "equal", "ISO_Left_Tab": "Tab",
          "KP_Delete": "Delete"}
KEYPAD.update({f"KP_{i}": str(i) for i in range(10)})
MODIFIER_KEYS = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Meta_L", "Meta_R",
                 "Super_L", "Super_R", "Caps_Lock", "Num_Lock", "ISO_Level3_Shift", "Mode_switch"}


def event_spec(keysym, state=0, windowing="x11"):
    """The key name for a key press (Tk's keysym and state). None for a lone modifier key (Shift, Ctrl...).
    Shift is only part of the name for keys without a shifted character (Shift+Tab, Shift+F5); Ctrl on macOS is
    the Command key as well."""
    if keysym in MODIFIER_KEYS or not keysym:
        return None
    shift = bool(state & 0x1) or keysym == "ISO_Left_Tab"
    ctrl = bool(state & 0x4) or (windowing == "aqua" and bool(state & 0x8))
    alt = bool(state & (0x20000 if windowing == "win32" else 0x10 if windowing == "aqua" else 0x8))
    key = KEYPAD.get(keysym, keysym)
    if len(key) == 1:
        key = key.lower()
        shift = False                        # (the character already says it: "?" not Shift+/)
    elif key in NAMES and len(NAMES[key]) == 1 and key not in ("Up", "Down", "Left", "Right"):
        shift = False                        # punctuation by name ("question", "plus")
    return ("Ctrl+" if ctrl else "") + ("Alt+" if alt else "") + ("Shift+" if shift else "") + key


def split(spec):
    """(modifier prefix, key): "Ctrl+Shift+Tab" -> ("Ctrl+Shift+", "Tab")."""
    mods = ""
    while True:
        for m in ("Ctrl+", "Alt+", "Shift+"):
            if spec.startswith(m) and len(spec) > len(m):
                mods, spec = mods + m, spec[len(m):]
                break
        else:
            return mods, spec


def display(spec, short=False):
    """How a key reads on screen: "Ctrl+z" -> "Ctrl Z", "Up" -> "↑", "question" -> "?"."""
    mods, key = split(spec)
    name = (SHORT.get(key) if short else None) or NAMES.get(key) or (key.upper() if len(key) == 1 else key)
    return " ".join([m for m in mods.split("+") if m] + [name])


def place_keys(first):
    """The six keys of the placing set that starts at `first` (same modifiers on all six), or None when fewer
    than five keys follow it on its keyboard row."""
    mods, key = split(first)
    for row in ROWS:
        row = list(row)
        if key in row:
            i = row.index(key)
            if i + SET > len(row):
                return None
            return [mods + k for k in row[i:i + SET]]
    return None


def place_display(first):
    keys = place_keys(first) or [first]
    return f"{display(keys[0])} … {display(keys[-1])}" if len(keys) > 1 else display(keys[0])


class Keymap:
    """The defaults with the user's changes on top. Only changed actions are saved."""

    def __init__(self, saved=None):
        self.keys = {a: list(k) for a, k in DEFAULTS.items()}
        try:
            changes = json.loads(saved) if saved else {}
        except (ValueError, TypeError):
            changes = {}
        for a, ks in (changes.items() if isinstance(changes, dict) else []):
            if a in self.keys and isinstance(ks, list) and all(isinstance(k, str) for k in ks):
                self.keys[a] = ks[:MAX_KEYS] if a != "place" or (ks and place_keys(ks[0])) else self.keys[a]

    def dumps(self):
        return json.dumps({a: ks for a, ks in self.keys.items() if ks != DEFAULTS[a]}, sort_keys=True)

    # -- reading
    def keys_of(self, action):
        """Every key that does this action (the placing set: all six)."""
        if action == "place":
            return place_keys(self.keys["place"][0]) or []
        return list(self.keys[action])

    def display(self, action, short=False):
        """The keys as they read on screen, one string each (the placing set as one: "1 … 6")."""
        if action == "place":
            return [place_display(self.keys["place"][0])]
        return [display(k, short) for k in self.keys[action]]

    def place_tier(self, spec):
        """0..5 if `spec` is one of the placing keys, else None."""
        ks = self.keys_of("place")
        return ks.index(spec) if spec in ks else None

    def lookup(self, group, spec):
        """What `spec` does in this view (its own keys first, then the Everywhere ones), or None."""
        for g in (group, "all"):
            for a, _g, _l, _k in ACTIONS:
                if GROUP_OF[a] == g and spec in self.keys_of(a):
                    return a
        return None

    def clash(self, action, specs):
        """The other action in the same view that already uses one of `specs`: (action, key) or None."""
        g = GROUP_OF[action]
        for a, _g, _l, _k in ACTIONS:
            if a != action and GROUP_OF[a] == g:
                for s in specs:
                    if s in self.keys_of(a):
                        return a, s
        return None

    def is_default(self, action):
        return self.keys[action] == DEFAULTS[action]

    # -- changing
    def set(self, action, keys):
        self.keys[action] = list(keys)[:MAX_KEYS]

    def reset(self, action=None):
        for a in ([action] if action else list(self.keys)):
            self.keys[a] = list(DEFAULTS[a])
