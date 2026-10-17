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
assert fam == F.family()
for role, (size, weight) in F.ROLES.items():
    f = F.font(role)
    assert f.cget("size") == size and f.cget("weight") == weight and f.cget("family") == fam, role
# re-init for a fresh root rebuilds without errors
root.destroy()
root = tk.Tk(); F.init_fonts(root); F.font("word"); root.destroy()

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
