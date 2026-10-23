#!/usr/bin/env python3
"""Random actions on the real main window (F-9), to find what no scripted test thought of: keys from the keymap,
tab switches, window resizes, Reduce motion on and off, Browse (select, move, unplace, sort, filter, zoom, scroll,
close), each settings dialog opened and closed, the definitions pane, undo, censoring on and off, duel answers.
It fails on any error raised along the way and when the window gets bigger than the (pretend 1366 x 768) screen.
A throwaway save; dialogs that wait for a click are answered at once.

    xvfb-run -a python tools/stress_ui.py               # seed 1, 400 actions (about five minutes)
    xvfb-run -a python tools/stress_ui.py --seed 7 --steps 1500
"""
import argparse
import os
import random
import sys
import tempfile
import time
import traceback
import types

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [HERE, os.path.join(HERE, "src")]
os.environ.setdefault("WORD_TIERLIST_OFFLINE", "1")      # (a throwaway save: no downloads, no lookups online)

AREA = (0, 0, 1311, 691)                                  # a 1366 x 768 laptop's usable area
WORDS = ["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist", "shit", "bastard", "damn",
         "pneumonoultramicroscopicsilicovolcanoconiosis", "a"] + [f"word{i}" for i in range(80)]
OBSCENE = ("shit", "bastard", "damn")
KEYS = [("1", 0), ("2", 0), ("6", 0), ("space", 0), ("u", 0), ("Up", 0), ("Down", 0), ("e", 0), ("BackSpace", 0),
        ("Tab", 0), ("d", 0), ("Left", 0), ("Right", 0), ("t", 0), ("s", 0), ("plus", 4), ("minus", 4), ("0", 4),
        ("z", 4), ("Escape", 0), ("f", 0), ("a", 0), ("l", 0)]
DEFINITION = "• (noun) a word\n• (verb) (vulgar) to do something rude\n• (noun) plural of word5"


def setup(rnd):
    """The window on a small pretend screen, over a save with a few placed and a few obscene words (censored)."""
    import tkinter as tk
    import app as A
    import browser as B
    import errors as E
    import sizing
    import sources as S
    import tierlist as T
    s = T.Store(os.path.join(tempfile.mkdtemp(prefix="wtl-stress-"), "stress.db"))
    s.insert_words(WORDS)
    s.set_anchors(WORDS[:6])
    s.set_meta("dealt_asked", "1")
    s.db.execute(f"UPDATE words SET obscene=1, rude=4 WHERE word IN ({','.join('?' * len(OBSCENE))})", OBSCENE)
    s.db.commit()
    s.set_censor(True)
    for w in WORDS[11:30]:
        s.place(w, rnd.randrange(6))
    for m in (A, B, sizing):
        m.usable_area = lambda r: AREA
    for m in (A, B, S, E):                               # (dialogs that wait for a click: answered at once)
        for name in ("show_message", "show_error", "show_exception"):
            if hasattr(m, name):
                setattr(m, name, lambda *a, **k: None)
        if hasattr(m, "ask_yes_no"):
            m.ask_yes_no = lambda *a, **k: False
    root = tk.Tk()
    app = A.App(root, s, T.Definitions(s))
    app.mem_defs.update({w: DEFINITION for w in WORDS})
    return root, app, s


def browse(app, rnd):
    app.open_browser()
    bw = next((b for b in app.browsers if b.alive()), None)
    if bw is None:
        return
    rows = bw.tree.get_children()
    if rows:
        bw.tree.selection_set(rnd.choice(rows))
    r = rnd.random()
    if r < 0.2:
        bw.move(rnd.randrange(6))
    elif r < 0.35:
        bw.unplace()
    elif r < 0.5:
        bw.sort_by(rnd.choice(["Default", "A-Z", "Rating", "Frequency", "Duels"]), toggle=True)
    elif r < 0.6:
        bw.filter_var.set(rnd.choice(["All placed", "Unplaced", "Obscene words", "Tier S"]))
        bw.reload()
    elif r < 0.7:
        bw.zoom_by(rnd.choice([-1, 1]))
    elif r < 0.8:
        bw.tree.yview_moveto(rnd.random())
    else:
        bw.close()


def act(root, app, store, rnd, pump):
    """One random action."""
    r = rnd.random()
    if r < 0.45:
        ks, state = rnd.choice(KEYS)
        e = types.SimpleNamespace(keysym=ks, char=ks if len(ks) == 1 else "", time=None, state=state,
                                  keycode=None, widget=root)
        app.on_key(e)
        app.on_key_release(e)
    elif r < 0.52:
        app.mode_var.set(rnd.choice(sorted(app.mode_switch.visible)))
        app.on_mode_change()
    elif r < 0.57:
        root.geometry(f"{rnd.randrange(700, AREA[2])}x{rnd.randrange(500, AREA[3])}")
    elif r < 0.60:
        app.anim.reduce_motion = rnd.random() < 0.5
    elif r < 0.66:
        browse(app, rnd)
    elif r < 0.70:
        rnd.choice([app.edit_anchors, app.edit_dealing, app.edit_keys, app.source_updates])()
        pump(3)
        for w in root.winfo_children():
            if getattr(w, "styled_dialog", False):
                w.event_generate("<Escape>")
    elif r < 0.74:
        app.toggle_defs()
    elif r < 0.77:
        app.undo()
    elif r < 0.80:
        store.set_censor(rnd.random() < 0.7)
        app.after_external_change()
    elif r < 0.85:
        if app.pair:
            app._on_duel(rnd.choice(["left", "right", "tie", "skip"]))
    else:
        time.sleep(rnd.random() * 0.25)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Random actions on the main window.")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--steps", type=int, default=400)
    args = ap.parse_args(argv)
    rnd = random.Random(args.seed)
    root, app, store = setup(rnd)
    errors, bad = [], []
    root.report_callback_exception = lambda *exc: errors.append("".join(traceback.format_exception(*exc))[-1500:])

    def pump(n=2):
        for _ in range(n):
            root.update()
            time.sleep(0.005)
    step = 0
    for step in range(args.steps):
        try:
            act(root, app, store, rnd, pump)
        except Exception:
            errors.append(f"step {step}: " + traceback.format_exc()[-1500:])
        pump(rnd.randrange(1, 4))
        w, h = root.winfo_width(), root.winfo_height()
        if w > AREA[2] + 2 or h > AREA[3] + 2:
            bad.append(f"step {step}: the window is {w}x{h}, bigger than the screen ({AREA[2]}x{AREA[3]})")
        if errors:
            break
    print(f"seed {args.seed}: {step + 1} steps, {len(errors)} errors, {len(bad)} invariant problems")
    for e in errors[:3]:
        print(e)
    for b in bad[:5]:
        print(b)
    return 1 if errors or bad else 0


if __name__ == "__main__":
    sys.exit(main())
