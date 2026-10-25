import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""The definitions pane opens without a flicker (reported, back again: on Windows and Linux). While it slides its
contents are placed (clipped); at the end they go back to being packed, and that change was left to the next idle
moment, so for a frame the pane showed empty: seen only under a real window manager, and with the Wiktionary link
inside it (UI-67). Here the pane is opened under openbox (when it is installed) while its contents are checked
every few milliseconds: once shown they never vanish again.

Its contents are never unmapped while it opens or is open (F-27); a longer definition eases it taller (F-28). Then, tracked frame by frame (asked for): the page around it never moves against the slide. Opening in a window that
must grow, the window grew first and the page dropped by half the growth, then slid back up as the pane opened;
closing, the pane was put back to its full size for a frame just before it left (the page jumped up and back), and
the gap under it went only once it had gone (a last small jump). The tier buttons' place in the window is read every
few milliseconds: while it opens they only rise (or stay put), while it closes they only sink, by a pixel's
rounding at most."""
import os, shutil, subprocess, tempfile, time
os.environ["HOME"] = tempfile.mkdtemp()
import tkinter as tk
import tierlist as T

wm = subprocess.Popen(["openbox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) if shutil.which("openbox") \
    else None
time.sleep(1.0 if wm else 0)
try:
    s = T.Store(os.path.join(tempfile.mkdtemp(), "drawer.db"))
    anchors = ["serendipity", "luminous", "chair", "bureaucracy", "gristle", "moist"]
    s.insert_words(["table"] + anchors); s.set_anchors(anchors); s.set_meta("dealt_asked", "1")
    s.set_def("table", "1. (noun) a piece of furniture with a flat top and legs\n2. (verb) to put forward")
    root = tk.Tk(); root.geometry("1100x800+0+0")
    app = T.App(root, s, T.Definitions(s)); app.open_window()
    app.online.online = True; app._watch_online()                 # (the link shows, as on a computer that is online)
    for _ in range(40):
        root.update(); time.sleep(0.02)
    mapped = []

    def probe():
        try:
            mapped.append(app.def_frame._inner.winfo_ismapped())
        except tk.TclError:
            return
        root.after(4, probe)
    probe(); app.toggle_defs(True)
    end = time.time() + 1.0
    while time.time() < end:
        root.update(); time.sleep(0.002)
    shown = mapped[mapped.index(1):] if 1 in mapped else []
    assert shown and all(shown), mapped                           # (once shown, never empty again)
    lb = app.def_frame.text._link_button
    assert lb.winfo_ismapped()
    # F-27: its contents are never taken out and put back (unmapped) while it opens or stays open: at the end of
    # every slide they were, and on a compositing desktop (GNOME on Wayland) a frame could show the pane without
    # them now and then, the whole pane seeming to dip and come back (reported)
    unmaps, state = [], ["closed"]
    inner = app.def_frame._inner
    inner.bind("<Unmap>", lambda e: unmaps.append(state[0]) if e.widget is inner else None, add="+")
    for _ in range(4):
        for opening in (False, True):
            state[0] = "closing" if not opening else "opening"
            app.toggle_defs(opening)
            end = time.time() + 0.4
            while time.time() < end:
                root.update(); time.sleep(0.004)
            state[0] = "open" if opening else "closed"
            end = time.time() + 0.15
            while time.time() < end:
                root.update(); time.sleep(0.004)
    assert not [u for u in unmaps if u in ("opening", "open")], unmaps
    # F-28 (asked for): a longer definition makes it taller smoothly, eased like opening, not in one jump
    s.set_def("long", "\n".join(f"{i}. (adjective) meaning number {i} of a word with very many meanings" for i in range(1, 16)))
    root.geometry("1100x980"); app.toggle_defs(True)
    for _ in range(40):
        root.update(); time.sleep(0.01)
    tops = []

    def watch():
        try:
            tops.append(app.def_frame.winfo_rooty() - root.winfo_rooty())
        except tk.TclError:
            return
        root.after(3, watch)
    watch(); app._render_defs(["long"])
    end = time.time() + 0.5
    while time.time() < end:
        root.update(); time.sleep(0.003)
    steps = [b - a for a, b in zip(tops, tops[1:]) if b != a]
    assert steps and all(d < 0 for d in steps) and len(steps) >= 4, tops      # (only up, in several frames)
    app._render_defs(["table"]); app.toggle_defs(False); app.toggle_defs(True)
    # frame by frame: a window that must grow for it (and one that need not), opened and closed
    for size in ("1000x700", "1100x980"):
        app.toggle_defs(False)
        for _ in range(30):
            root.update(); time.sleep(0.02)
        root.geometry(size)
        for _ in range(30):
            root.update(); time.sleep(0.02)
        for opening in (True, False):
            ys = []

            def track():
                try:
                    ys.append(app.tier_row.winfo_rooty() - root.winfo_rooty())
                except tk.TclError:
                    return
                root.after(3, track)
            track(); app.toggle_defs(opening)
            end = time.time() + 0.6
            while time.time() < end:
                root.update(); time.sleep(0.002)
            steps = [b - a for a, b in zip(ys, ys[1:]) if b != a]
            wrong = [d for d in steps if (d > 1 if opening else d < -1)]
            assert not wrong, (size, opening, ys)
            if size == "1100x980" or not opening:      # (growing for it, the page may not move at all: the pane
                assert ys[-1] < ys[0] if opening else ys[-1] > ys[0], (size, opening, ys)     # takes what it gained)
    app.on_close()
finally:
    if wm:
        wm.terminate()
# F-34 (asked for: the pane had no scroll bar): a slim one beside a column only while its meanings do not all fit;
# showing it never changes the pane's width (its room is kept) or the text's wrapping
import tkinter as tk
from fonts import init_fonts, font
from widgets import DefinitionDrawer
r = tk.Tk(); init_fonts(r)
d = DefinitionDrawer(r, {"body": font("body"), "head": font("heading")}); d.pack(fill="x")
d.show_words(["table"], lambda w: "1. (noun) short"); d.set_open(True)
for _ in range(5):
    r.update()
assert not d.bars[0].winfo_manager()
w0, wrap0 = d._inner.winfo_reqwidth(), d.text.cget("width")
long = "\n".join(f"{i}. (noun) meaning number {i}, long enough to read like a definition" for i in range(1, 15))
d.show_words(["table"], lambda w: long); d.set_lines(5)
for _ in range(5):
    r.update()
assert d.bars[0].winfo_manager() and (d._inner.winfo_reqwidth(), d.text.cget("width")) == (w0, wrap0)
d.show_words(["table", "chair"], lambda w: long)                   # a duel: one bar per column
for _ in range(5):
    r.update()
assert d.columns == 2 and all(b.winfo_manager() for b in d.bars) and d._inner.winfo_reqwidth() <= w0 + 2
d.show_words(["table"], lambda w: "1. (noun) short")
for _ in range(5):
    r.update()
assert not any(b.winfo_manager() for b in d.bars)
r.destroy()
print("DRAWER OK" + ("" if wm else " (no openbox: checked without a window manager)"))
