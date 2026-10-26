import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""keymap.py (UI-48): every action's keys in one table, the user's changes on top; key presses -> key names."""
import keymap as K

# ---- key presses -> key names (Tk keysym + state), on each windowing system
assert K.event_spec("u", 0) == "u" and K.event_spec("U", 0x1) == "u"             # a letter: Shift does not count
assert K.event_spec("question", 0x1) == "question"                                # the character says it
assert K.event_spec("z", 0x4) == "Ctrl+z" and K.event_spec("Z", 0x5) == "Ctrl+z"
assert K.event_spec("ISO_Left_Tab", 0x1) == "Shift+Tab" == K.event_spec("Tab", 0x1, "win32")
assert K.event_spec("plus", 0x5) == "Ctrl+plus" and K.event_spec("KP_Add", 0x4) == "Ctrl+plus"   # keypad = main keys
assert K.event_spec("KP_3", 0) == "3" and K.event_spec("KP_Enter", 0) == "Return"
assert K.event_spec("f", 0x8) == "Alt+f" and K.event_spec("f", 0x20000, "win32") == "Alt+f"
assert K.event_spec("f", 0x8, "win32") == "f"                                     # (0x8 is not Alt on Windows)
assert K.event_spec("z", 0x8, "aqua") == "Ctrl+z"                                 # Command on macOS
assert K.event_spec("Shift_L", 0x1) is None and K.event_spec("Control_L", 0x4) is None   # a lone modifier
assert K.event_spec("F5", 0x1) == "Shift+F5" and K.event_spec("Up", 0x1) == "Shift+Up"

# ---- how keys read on screen
assert K.display("Ctrl+z") == "Ctrl Z" and K.display("Up") == "↑" and K.display("question") == "?"
assert K.display("BackSpace") == "Backspace" and K.display("BackSpace", short=True) == "Bksp"
assert K.display("Shift+Tab") == "Shift Tab" and K.display("Ctrl+minus") == "Ctrl −" and K.display("F7") == "F7"

# ---- the placing set: one key, the five after it on its keyboard row
assert K.place_keys("1") == ["1", "2", "3", "4", "5", "6"]
assert K.place_keys("q") == list("qwerty") and K.place_keys("a") == list("asdfgh")
assert K.place_keys("F1") == ["F1", "F2", "F3", "F4", "F5", "F6"]
assert K.place_keys("Ctrl+1") == [f"Ctrl+{i}" for i in range(1, 7)]
assert K.place_keys("8") is None and K.place_keys("m") is None and K.place_keys("space") is None   # not 5 after it
assert K.place_display("q") == "Q … Y"

# ---- the map: defaults, a view's own keys before the Everywhere ones, clashes within a view
km = K.Keymap()
assert km.lookup("place", "3") == "place" and km.place_tier("3") == 2 and km.place_tier("u") is None
assert km.lookup("place", "BackSpace") == "undo" and km.lookup("compare", "BackSpace") == "back"   # (as before)
assert km.lookup("compare", "space") == "stop" and km.lookup("place", "space") == "compare"
assert km.lookup("duel", "Down") == "tie" and km.lookup("compare", "Down") == "worse"
assert km.lookup("duel", "u") is None and km.lookup("browse", "Delete") == "unplace"
assert km.display("undo") == ["Backspace", "Ctrl Z"] and km.display("place") == ["1 … 6"]
assert km.clash("later", ["1"]) == ("place", "1") and km.clash("later", ["s"]) is None   # S is Skip, another view
assert km.clash("place", K.place_keys("q")) is None and km.clash("place", K.place_keys("t")) == ("later", "u")
assert km.clash("compare", ["u"]) == ("later", "u")
# changes are saved (only what changed) and read back; bad saved data falls back to the defaults
km.set("later", ["q"]); km.set("place", ["a"])
assert km.lookup("place", "q") == "later" and km.lookup("place", "u") is None and km.place_tier("h") == 5
again = K.Keymap(km.dumps())
assert again.keys_of("later") == ["q"] and again.keys_of("place") == list("asdfgh") and not again.is_default("later")
assert set(eval(km.dumps().replace("null", "None"))) == {"later", "place"}
assert K.Keymap("not json").keys == K.Keymap().keys
assert K.Keymap('{"place": ["m"], "nope": ["x"], "undo": 5}').keys_of("place") == list("123456")
km.reset("later"); assert km.is_default("later") and not km.is_default("place")
km.reset(); assert km.dumps() == "{}"
assert all(len(k) <= K.MAX_KEYS for k in K.DEFAULTS.values())
# no two actions of one view share a default key (except the view's own keys over Everywhere ones, by design)
for g, _name in K.GROUPS:
    seen = {}
    for a, ga, _l, _k in K.ACTIONS:
        if ga == g:
            for s in km.keys_of(a):
                assert s not in seen, (g, s, a, seen.get(s))
                seen[s] = a
# reported: the zoom keys did nothing on Windows. With Ctrl held, Windows' key name for these keys depends on the
# layout; the virtual-key code does not, so the zoom keys are read from it there (and nowhere else)
assert K.event_spec("??", 0x4, "win32", 189) == "Ctrl+minus" and K.event_spec("??", 0x4, "win32", 187) == "Ctrl+equal"
assert K.event_spec("??", 0x5, "win32", 187) == "Ctrl+plus" and K.event_spec("??", 0x4, "win32", 107) == "Ctrl+plus"
assert K.event_spec("??", 0x4, "win32", 48) == "Ctrl+0" and K.event_spec("??", 0x4, "win32", 96) == "Ctrl+0"
assert K.event_spec("minus", 0x0, "win32", 189) == "minus"                      # (without Ctrl: as Tk says)
assert K.event_spec("??", 0x4, "x11", 189) == "Ctrl+??"                          # (other systems: as Tk says)
km = K.Keymap()
for code, action in ((187, "zoom_in"), (189, "zoom_out"), (48, "zoom_reset"), (107, "zoom_in"), (109, "zoom_out")):
    assert km.lookup("place", K.event_spec("??", 0x4, "win32", code)) == action, code
import types
assert K.spec_of(types.SimpleNamespace(keysym="??", state=0x4, keycode=189), "win32") == "Ctrl+minus"
print("KEYMAP OK")
