#!/usr/bin/env python3
"""Watch every widget of the main window, frame by frame, while words are placed fast, and report what moved
that should not have, short spikes (somewhere for a frame or two, then back), and anything drawn over the
tier buttons. A debugging tool for layout jitter (it never touches your save: it builds a throwaway one).

    python tools/layout_trace.py                     # 40 presses, 60 ms apart, motion on
    python tools/layout_trace.py --reduce-motion --every 30 --presses 80 --zoom 1.5
    python tools/layout_trace.py --csv trace.csv     # every frame's geometry, for a closer look

On a headless Linux box run it under xvfb-run. Exit status 1 if anything that should stay still moved.

How it looks: it drives the real App with key presses at the given pace and, after every pass of the event
loop (what the screen shows), records each mapped widget's place on screen. Polling is needed because when
a frame moves its children get no <Configure> of their own; <Configure> events are logged too, so a widget
that changes size and back inside one pass is still caught.
"""
import argparse
import os
os.environ.setdefault("WORD_TIERLIST_OFFLINE", "1")      # (a throwaway save: no downloads, no lookups online)
import sys
import tempfile
import time
import types

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [HERE, os.path.join(HERE, "src")]

WORDS = ["ox", "incomprehensibilities", "cat", "lantern", "electroencephalograph", "moon", "a",
         "antidisestablishmentarianism", "jump", "serendipitous", "Q", "well-to-do"]
ANCHORS = ["serendipity", "luminous", "table", "bureaucracy", "gristle", "moist"]


def build_app(args):
    os.environ["HOME"] = tempfile.mkdtemp()           # no settings or saves of yours are read or written
    import tkinter as tk
    import tierlist as T
    s = T.Store(os.path.join(tempfile.mkdtemp(), "trace.db"))
    words = [f"{w}{i}" for i, w in enumerate(WORDS * (args.presses // len(WORDS) + 3))]
    s.insert_words(words + ANCHORS)
    s.set_anchors(ANCHORS)
    s.db.executemany("UPDATE words SET qkey=? WHERE word=?", [(i, w) for i, w in enumerate(words)])
    s.set_meta("reduce_motion", "1" if args.reduce_motion else "0")
    s.db.commit()
    root = tk.Tk()
    root.geometry(args.geometry)
    app = T.App(root, s, T.Definitions(s))
    return root, app


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def names(app):
    """Readable names for the widgets worth naming (the rest keep their Tk path)."""
    out = {str(b): f"tier button {n}" for n, b in zip("SABCDF", app.tier_btns)}
    for attr in ("word_card", "tier_row", "act_row", "compare_btn", "later_btn", "place_inner", "place_frame",
                 "center", "chart", "progress_bar", "hint_lbl", "def_frame", "status_band"):
        w = getattr(app, attr, None)
        if w is not None:
            out[str(w)] = attr
    return out


def snapshot(root):
    snap = {}
    for w in walk(root):
        try:
            if w.winfo_ismapped() and w.winfo_viewable():
                snap[str(w)] = (w.winfo_rootx(), w.winfo_rooty(), w.winfo_width(), w.winfo_height())
        except Exception:                             # destroyed mid-walk (an old toast)
            pass
    return snap


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--presses", type=int, default=40)
    ap.add_argument("--every", type=int, default=60, help="milliseconds between key presses")
    ap.add_argument("--reduce-motion", action="store_true")
    ap.add_argument("--zoom", type=float, default=0)
    ap.add_argument("--geometry", default="1100x760+0+0")
    ap.add_argument("--settle", type=float, default=1.5, help="seconds to wait before the first press")
    ap.add_argument("--csv", help="write every frame's geometry here")
    args = ap.parse_args()

    root, app = build_app(args)
    if args.zoom:
        app._apply_zoom(args.zoom)
    end = time.time() + args.settle
    while time.time() < end:
        root.update()
        time.sleep(0.005)

    configs = []                                       # (ms, path, w, h) for every <Configure>
    t0 = time.perf_counter()
    root.bind_all("<Configure>", lambda e: configs.append(((time.perf_counter() - t0) * 1000, str(e.widget),
                                                           e.width, e.height)), add="+")
    label = names(app)
    still = {p for p, n in label.items() if n.startswith("tier button") or n in ("tier_row", "act_row",
                                                                                 "compare_btn", "later_btn")}
    frames = []                                        # (ms, press number, snapshot)
    press, next_at = 0, 0.0
    while press < args.presses or (time.perf_counter() - t0) * 1000 < next_at + 600:
        now = (time.perf_counter() - t0) * 1000
        if press < args.presses and now >= next_at:
            k = str(1 + press % 6)
            app.on_key(types.SimpleNamespace(keysym=k, time=None))
            app.on_key_release(types.SimpleNamespace(keysym=k, time=None))
            press += 1
            next_at = now + args.every
        root.update()
        frames.append(((time.perf_counter() - t0) * 1000, press, snapshot(root)))
        time.sleep(0.002)

    name = lambda p: label.get(p, p)
    problems = 0
    # 1. things that should stay still
    print(f"{len(frames)} frames, {args.presses} presses every {args.every} ms, "
          f"reduce motion {'on' if args.reduce_motion else 'off'}")
    for p in sorted(still, key=name):
        seen = [(ms, n, s[p]) for ms, n, s in frames if p in s]
        moves = [(seen[i][0], seen[i][1], seen[i - 1][2], seen[i][2]) for i in range(1, len(seen))
                 if seen[i][2] != seen[i - 1][2]]
        if moves:
            problems += 1
            print(f"MOVED  {name(p)}: {len(moves)} times, {len({m[3] for m in moves})} places")
            for ms, n, a, b in moves[:6]:
                print(f"         {ms:7.0f} ms (press {n}): {a} -> {b}")
    # 2. spikes: anything that goes somewhere for one or two frames and comes straight back
    spikes = {}
    for i in range(1, len(frames) - 2):
        a, b, c, d = frames[i - 1][2], frames[i][2], frames[i + 1][2], frames[i + 2][2]
        for p, g in b.items():
            if p in a and a[p] != g and (c.get(p) == a[p] or (c.get(p) != g and d.get(p) == a[p])):
                spikes.setdefault(p, []).append((frames[i][0], a[p], g))
    for p, lst in sorted(spikes.items(), key=lambda kv: -len(kv[1])):
        print(f"SPIKE  {name(p)}: {len(lst)} times, e.g. {lst[0][0]:.0f} ms {lst[0][1]} -> {lst[0][2]} -> back")
    # 3. a size that changes and changes back inside one pass of the loop (never seen by the snapshots)
    flips = {}
    for i in range(2, len(configs)):
        (t1, p1, *g1), (t2, p2, *g2), (t3, p3, *g3) = configs[i - 2], configs[i - 1], configs[i]
        if p1 == p2 == p3 and g1 == g3 != g2 and t3 - t1 < 20:
            flips.setdefault(p1, []).append((t2, g1, g2))
    for p, lst in sorted(flips.items(), key=lambda kv: -len(kv[1])):
        print(f"FLIP   {name(p)}: {len(lst)} times, e.g. {lst[0][0]:.0f} ms size {lst[0][1]} -> {lst[0][2]} -> back")
    # 4. anything drawn over the tier or action buttons that is not part of them
    over = {}
    for ms, n, s in frames:
        for b in still:
            if b not in s or not name(b).startswith(("tier button", "compare", "later")):
                continue
            bx, by, bw, bh = s[b]
            for p, (x, y, w, h) in s.items():
                if p == "." or p == b or p.startswith(b + ".") or b.startswith(p + "."):
                    continue                           # the button itself, its parts or its parents
                if x < bx + bw and bx < x + w and y < by + bh and by < y + h:
                    over.setdefault((p, b), []).append(ms)
    for (p, b), lst in sorted(over.items(), key=lambda kv: -len(kv[1])):
        problems += 1
        print(f"OVER   {name(p)} over {name(b)}: {len(lst)} frames, first at {lst[0]:.0f} ms")
    if args.csv:
        with open(args.csv, "w") as f:
            f.write("ms,press,widget,x,y,w,h\n")
            for ms, n, s in frames:
                for p, g in s.items():
                    f.write(f"{ms:.1f},{n},{name(p)},{g[0]},{g[1]},{g[2]},{g[3]}\n")
    print("OK: nothing that should stay still moved" if not problems else f"{problems} problem(s)")
    app.on_close()
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
