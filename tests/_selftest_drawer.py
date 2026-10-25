import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""The definitions pane opens without a flicker (reported, back again: on Windows and Linux). While it slides its
contents are placed (clipped); at the end they go back to being packed, and that change was left to the next idle
moment, so for a frame the pane showed empty: seen only under a real window manager, and with the Wiktionary link
inside it (UI-67). Here the pane is opened under openbox (when it is installed) while its contents are checked
every few milliseconds: once shown they never vanish again."""
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
    app.on_close()
finally:
    if wm:
        wm.terminate()
print("DRAWER OK" + ("" if wm else " (no openbox: checked without a window manager)"))
