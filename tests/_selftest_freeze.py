import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""Reported: the program froze (the log's watchdog caught it: the window thread inside a canvas delete, from the word
card's magnifier being hovered). Its Enter / Leave redrew it by deleting it and making it again; the new item under
the pointer was entered again, and Tk looped on that for good. Here, under openbox (when installed), the pointer
rests on every edge and the middle of the magnifier, and new words are shown under it: the hover runs once a spot,
and nothing hangs (a hang ends the test with the stacks, not a test run that never finishes)."""
import faulthandler, os, shutil, subprocess, tempfile, time
os.environ["HOME"] = tempfile.mkdtemp()
faulthandler.dump_traceback_later(60, exit=True)                  # (a freeze fails the test instead of hanging it)
import tkinter as tk
import tierlist as T
import widgets as W

wm = subprocess.Popen(["openbox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) if shutil.which("openbox") \
    else None
time.sleep(1.0 if wm else 0)
try:
    s = T.Store(os.path.join(tempfile.mkdtemp(), "freeze.db"))
    words = ["table", "chair", "lamp", "bowl", "spoon"]
    anchors = ["serendipity", "luminous", "door", "bureaucracy", "gristle", "moist"]
    s.insert_words(words + anchors); s.set_anchors(anchors); s.set_meta("dealt_asked", "1")
    root = tk.Tk(); root.geometry("1100x800+0+0")
    app = T.App(root, s, T.Definitions(s)); app.open_window()
    for _ in range(40):
        root.update(); time.sleep(0.02)
    card = app.word_card
    calls = [0]
    real = W.WordCard._hover_find
    W.WordCard._hover_find = lambda self, on: (calls.__setitem__(0, calls[0] + 1), real(self, on))[1]

    def settle(seconds=0.3):
        end = time.time() + seconds
        while time.time() < end:
            root.update()
    x, y, size = card.find_box()
    worst = 0
    for dx in (0, 1, size // 2, size - 1, size):
        for dy in (0, 1, size // 2, size - 1, size):
            root.event_generate("<Motion>", warp=True, x=card.winfo_rootx() - root.winfo_rootx() + x + dx,
                                y=card.winfo_rooty() - root.winfo_rooty() + y + dy)
            calls[0] = 0
            settle()
            worst = max(worst, calls[0])
    assert worst <= 2, worst                                      # (it looped: thousands, or never returned)
    calls[0] = 0
    for _ in range(4):                                            # new words drawn under the resting pointer
        app.skip_word(); settle(0.15)
    assert calls[0] <= 8, calls[0]
    assert card.find_withtag("find")
    app.on_close()
finally:
    if wm:
        wm.terminate()
faulthandler.cancel_dump_traceback_later()
print("FREEZE OK" + ("" if wm else " (no openbox: checked without a window manager)"))
