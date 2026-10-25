import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import os, tempfile
import tkinter as tk
import fonts as F
import tierlist as T

# pure picker
assert F.pick_font_family(["Arial", "nunito", "Helvetica"]) == "nunito"
assert F.pick_font_family(["Arial", "Helvetica"]) == "Helvetica"
assert F.pick_font_family(["Comic Sans"]) == F.FALLBACK
assert F.pick_font_family([]) == F.FALLBACK
assert F.pick_font_family(["segoe ui", "Quicksand"]) == "Quicksand"      # earlier in the list wins

root = tk.Tk()
fam = F.init_fonts(root)
assert fam == F.family() == F.TEXT_FAMILY, fam                 # the bundled typefaces load (UI-73)
assert F.display_family() == F.DISPLAY_FAMILY
assert F.load_typefaces() is True
assert len(F.typeface_files()) == 5                             # Young Serif + Atkinson Hyperlegible's four
for role, (size, weight, face) in F.ROLES.items():
    f = F.font(role)
    want = F.DISPLAY_FAMILY if face == "display" else F.TEXT_FAMILY
    assert f.cget("size") == size and f.cget("weight") == weight and f.cget("family") == want, role
    assert f.actual("family") == want, (role, f.actual())     # really drawn in it, not a substitute
# the text keeps to three sizes beside the big words (the word on the card, a duel's two words)
assert {s for r, (s, _w, face) in F.ROLES.items() if r not in ("word", "pair")} == {20, 12, 10}
# a missing typeface is not an error: the installed stand-ins are used
assert F.load_typefaces(["/nonexistent/font.ttf"]) is False
assert F.load_typefaces(["/nonexistent/font.ttf"], platform="win32") is False
assert F.load_typefaces([], platform="darwin") is False
F._loaded = True
# re-init for a fresh root rebuilds without errors
root.destroy()
root = tk.Tk(); F.init_fonts(root); F.font("word"); root.destroy()

# the source, the zip and a build carry the typefaces and their licences (UI-73)
import standalone as S
files = {f.replace(os.sep, "/") for f in S.source_files()}
assert {"src/typefaces/" + os.path.basename(f) for f in F.typeface_files()} <= files
assert {"src/typefaces/YoungSerif-OFL.txt", "src/typefaces/AtkinsonHyperlegible-OFL.txt"} <= files
for platform in ("win32", "linux", "darwin"):
    sep = ";" if platform == "win32" else ":"
    assert f"{F.TYPEFACES}{sep}typefaces" in S.pyinstaller_args("dist", "work", platform=platform)
# their line spacing was tightened (tools/make_typefaces.py): a line of body text is not much taller than the old
# fonts' (much of the layout is measured in lines)
root = tk.Tk(); F.init_fonts(root)
assert F.font("body").metrics("linespace") <= 1.25 * F.font("body").measure("M") + 4, F.font("body").metrics()
for role in ("body", "head", "tier"):                    # digits all one width: a changing count never shifts a line
    assert len({F.font(role).measure(d * 6) for d in "0123456789"}) == 1, role
root.destroy()

# the app uses roles and no hard-coded tuples remain
import glob
for path in [os.path.join(_paths.ROOT, "tierlist.py")] + glob.glob(os.path.join(_paths.SRC, "*.py")):
    src = open(path, encoding="utf-8").read()
    assert "(FONT," not in src and "FONT =" not in src, path
tmp = tempfile.mkdtemp()
s = T.Store(os.path.join(tmp, "f.db")); s.insert_words(["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist", "x1", "x2"])
s.set_anchors(["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"]) if hasattr(s, "set_anchors") else None
root = tk.Tk()
app = T.App(root, s, T.Definitions(s)); root.update()
assert str(app.word_card.cget("font")) == str(F.font("word")), app.word_card.cget("font")
assert str(app.toast.cget("font")) == str(F.font("label"))
root.destroy()
print("FONTS OK")
