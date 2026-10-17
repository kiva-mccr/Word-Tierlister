import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
import tkinter as tk
from tkinter import ttk
import fonts, ui_style
from theme import PALETTE as P

root = tk.Tk()
fonts.init_fonts(root)
st = ui_style.apply_ttk_style(root)
assert st.theme_use() == "clam"
assert root.cget("bg") == P["bg"]
for name in ("TFrame", "TLabel"):
    assert st.lookup(name, "background") == P["bg"], name
assert st.lookup("TButton", "background") == P["surface"]
assert st.lookup("Treeview", "background") == P["surface"]
assert st.lookup("Treeview", "foreground") == P["text"]
assert st.lookup("TEntry", "fieldbackground") == P["surface"]
assert st.lookup("TLabelframe.Label", "foreground") == P["muted"]
assert st.lookup("Vertical.TScrollbar", "troughcolor") == P["bg"]
assert st.lookup("TRadiobutton", "background") == P["bg"]
assert st.lookup("TLabel", "font")
# the option database reaches new plain tk widgets
t = tk.Text(root); assert t.cget("bg") == P["surface"] and t.cget("fg") == P["text"]
m = tk.Menu(root); assert str(m.cget("bg")) == P["surface"]
top = tk.Toplevel(root); assert top.cget("bg") == P["bg"]
# a styled widget builds without TclError
ttk.Button(root, text="x").pack(); ttk.Treeview(root).pack()
root.update(); root.destroy()
# idempotent on a second root
r2 = tk.Tk(); fonts.init_fonts(r2); ui_style.apply_ttk_style(r2); r2.destroy()
print("STYLE OK")
