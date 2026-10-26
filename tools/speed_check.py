#!/usr/bin/env python3
"""Time what runs per word, per duel and per click on a big save (F-9): the numbers to check after any change to
what a refresh, a placement, a duel or a Browse sort does. It builds a throwaway save (it never touches yours).

    python tools/speed_check.py                          # a million words, 300,000 placed, then 3,000 placed
    python tools/speed_check.py --words 300000 --placed 30000

On a headless Linux box run it under xvfb-run. Each action should stay under about 40 ms (Browse's sorts under
about 200 ms); exit status 1 if one takes more than twice that.
"""
import argparse
import os
import random
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [HERE, os.path.join(HERE, "src")]
os.environ.setdefault("WORD_TIERLIST_OFFLINE", "1")      # (a throwaway save: no downloads, no lookups online)

ACTION_MS, BROWSE_MS = 40, 200


def build(n, placed, folder):
    """A save of `n` words with `placed` of them in random tiers (ratings and duel counts spread out)."""
    from store import Store
    s = Store(os.path.join(folder, f"speed-{n}-{placed}.db"))
    words = [f"w{i:07d}" for i in range(n)]
    s.insert_words(words)
    s.set_anchors(words[:6])
    rnd = random.Random(1)
    s.db.executemany("UPDATE words SET tier=?, rating=?, games=? WHERE word=?",
                     [(rnd.randrange(6), 1500 + rnd.random() * 400, rnd.randrange(20), w)
                      for w in words[6:6 + placed]])
    s.db.commit()
    s.set_meta("dealt_asked", "1")
    s._forget_tallies()
    return s


def timed(label, fn, budget, slow, n=20):
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    ms = (time.perf_counter() - t0) / n * 1000
    print(f"  {label:34} {ms:8.1f} ms")
    if ms > 2 * budget:
        slow.append(f"{label}: {ms:.0f} ms")


def check(n, placed, folder, slow):
    import tkinter as tk
    from app import App
    from definitions import Definitions
    print(f"== {n:,} words, {placed:,} placed")
    t0 = time.perf_counter()
    s = build(n, placed, folder)
    print(f"  (built in {time.perf_counter() - t0:.0f} s)")
    root = tk.Tk()
    t0 = time.perf_counter()
    app = App(root, s, Definitions(s))
    root.update()
    print(f"  {'open the window':34} {(time.perf_counter() - t0) * 1000:8.0f} ms")
    app.anim.reduce_motion = True
    idle = root.update_idletasks
    timed("refresh", app.refresh, ACTION_MS, slow)
    timed("place a word", lambda: (app.place_word(random.randrange(6)), idle()), ACTION_MS, slow)
    timed("skip a word", lambda: (app.skip_word(), idle()), ACTION_MS, slow)
    timed("undo", lambda: (app.undo(), idle()), ACTION_MS, slow)
    for mode in ("refine", "boundary"):
        if mode in app.modes_with_work(s.stats()):
            app.mode_var.set(mode)
            app.on_mode_change()
            root.update()
            timed(f"{mode}: answer a duel", lambda: (app.pair and app._on_duel("left"), idle()), ACTION_MS, slow)
    app.mode_var.set("place")
    app.on_mode_change()
    app.open_browser()
    root.update()
    bw = app.browsers[0]
    for show in ("All placed", "Unplaced", "Nouns", "Obscene words"):
        bw.filter_var.set(show)
        for sort in s.SORTS:
            timed(f"Browse: {show}, {sort}", lambda: (bw.sort_by(sort), root.update()), BROWSE_MS, slow, n=2)
    for show in ("All placed", "Unplaced", "Tier B"):          # (a search runs whenever the typing pauses: F-17)
        bw.filter_var.set(show)
        for text in ("w", "w00", "w0123456", "zz"):
            bw.search_var.set(text)
            timed(f"Browse search {text!r}: {show}", lambda: (bw.reload(), root.update()), BROWSE_MS, slow, n=2)
    bw.search_var.set("")
    root.destroy()
    s.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Time per-action work on a big throwaway save.")
    ap.add_argument("--words", type=int, default=1_000_000)
    ap.add_argument("--placed", type=int, action="append", help="placed words (again for another save)")
    args = ap.parse_args(argv)
    slow = []
    with tempfile.TemporaryDirectory(prefix="wtl-speed-") as folder:
        for placed in args.placed or [300_000, 3_000]:
            check(args.words, placed, folder, slow)
    print("slow: " + "; ".join(slow) if slow else "OK: nothing slow")
    return 1 if slow else 0


if __name__ == "__main__":
    sys.exit(main())
