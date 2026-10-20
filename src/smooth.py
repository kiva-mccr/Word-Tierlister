"""Smooth (anti-aliased) rounded shapes for our canvases.

Why: Tk draws canvas shapes without anti-aliasing. On Windows a rounded button, pill or bar has jagged
corners (and the old trick, a polygon with smooth=True, even left little bumps on the bars' corners), and
a curve looks like a staircase. Tk 8.6 cannot draw SVG, but its photo images blend partly transparent
pixels with whatever is under them, so each rounded shape is drawn here, pixel by pixel with soft edges,
into a small PNG, and shown as an image.

    class Pill(SmoothCanvas): ...
    item = self.round_rect(x1, y1, x2, y2, r, fill="#FFB3C1", outline="#E09AA8", tags=("pill", "pill0"))
    self.itemconfigure("pill0", fill="#FFC2CD")      # works as before: the image is redrawn
    self.round_rect_coords(item, x1, y1, x2, y2)     # a new size (an animation): the image follows

How it fits in without changing the rest of the code: each shape is still a canvas polygon (so tags,
coords, bbox, find_withtag, move, delete and stacking all work as before), but drawn invisibly; its own
image sits straight above it and follows it (move, delete, raise / lower, state). itemcget(item, "fill")
gives the colour it is drawn in. `radii` gives each corner its own radius (top-left, top-right,
bottom-right, bottom-left): bars are round on top and square at the bottom.

    curve_image(...) does the same for the area under a curve and its line (the queue dialog's shapes).
Images are cached per window (the same shape in the same colours is drawn once).
"""
import base64
import math
import struct
import tkinter as tk
import zlib

_CACHE_MAX = 600


# ---------------------------------------------------------------- pixels -> PNG -> PhotoImage
def _png(w, h, rows):
    """A PNG (8-bit RGBA) from `rows`, each w*4 bytes."""
    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b""))


def _rgb(colour):
    if not colour:
        return None
    c = colour.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _snap(rgb):
    return None if rgb is None else tuple(min(255, (c + 2) // 4 * 4) for c in rgb)


def _pixel(fill, outline, a_fill, a_out):
    """RGBA bytes: the outline over the fill, both with their coverage (0..1)."""
    if fill is None:
        a_fill = 0.0
    if outline is None:
        a_out = 0.0
    a = a_out + a_fill * (1.0 - a_out)
    if a <= 0.002:
        return b"\x00\x00\x00\x00"
    out = []
    for k in range(3):
        f = fill[k] if fill else 0
        o = outline[k] if outline else 0
        out.append(int((o * a_out + f * a_fill * (1.0 - a_out)) / a + 0.5))
    return bytes((out[0], out[1], out[2], int(a * 255 + 0.5)))


def _clamp01(v):
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def control_points(x1, y1, x2, y2, radii):
    """The corner points of a rounded rectangle the way the app has always drawn it (Tk's smoothed polygon):
    each corner's two tangent points doubled, so the curve passes through them, and the corner itself
    between them. A corner radius of 0 gives a square corner. Radii are not limited to half the size: the
    tier pills ask for a huge one and get the rounded-square look they have always had."""
    tl, tr, br, bl = radii
    return [(x1 + tl, y1), (x1 + tl, y1), (x2 - tr, y1), (x2 - tr, y1), (x2, y1), (x2, y1 + tr), (x2, y1 + tr),
            (x2, y2 - br), (x2, y2 - br), (x2, y2), (x2 - br, y2), (x2 - br, y2), (x1 + bl, y2), (x1 + bl, y2),
            (x1, y2), (x1, y2 - bl), (x1, y2 - bl), (x1, y1 + tl), (x1, y1 + tl), (x1, y1)]


def smooth_outline(points, steps=10):
    """Tk's smoothing of a closed polygon: around each point, a quadratic Bezier from the middle of the side
    before it to the middle of the side after it, with the point as its control. Returns a dense polygon."""
    n = len(points)
    out = []
    for i in range(n):
        p0, p1, p2 = points[i - 1], points[i], points[(i + 1) % n]
        a = ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)
        c = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
        if abs(a[0] - c[0]) + abs(a[1] - c[1]) < 1e-9:
            out.append(a)
            continue
        for k in range(steps):
            t = k / steps
            u = 1.0 - t
            out.append((u * u * a[0] + 2 * u * t * p1[0] + t * t * c[0], u * u * a[1] + 2 * u * t * p1[1] + t * t * c[1]))
    clean = [out[0]]                       # drop repeats (doubled points give zero-length pieces)
    for q in out[1:]:
        if abs(q[0] - clean[-1][0]) + abs(q[1] - clean[-1][1]) > 1e-6:
            clean.append(q)
    return clean


def _straighten(poly):
    """Each straight stretch along a side (points with the same y, or the same x) down to its two ends. With a
    corner radius bigger than half the shape (the tier pills) the side's tangent points pass each other, so
    the outline runs back and forth along the top past the corners' curves: no fill, but its hairline
    showed as a stray line along the top and bottom, longer the bigger the zoom."""
    n = len(poly)
    if n < 4:
        return poly
    def same(p, q):
        return abs(p[1] - q[1]) < 1e-9 or abs(p[0] - q[0]) < 1e-9
    start = next((i for i in range(n) if not same(poly[i - 1], poly[i])), None)
    if start is None:
        return poly
    pts = poly[start:] + poly[:start]               # (begin where a straight stretch cannot wrap round)
    out, i = [], 0
    while i < n:
        j = i
        horiz = None
        while j + 1 < n:
            p, q = pts[j], pts[j + 1]
            h = abs(p[1] - q[1]) < 1e-9
            v = abs(p[0] - q[0]) < 1e-9
            kind = "h" if h else ("v" if v else None)
            if kind is None or (horiz is not None and kind != horiz):
                break
            horiz = kind
            j += 1
        out.append(pts[i])
        if j > i:
            out.append(pts[j])
        i = j + 1
    return out


SUB = 4      # sub-rows per pixel row for the fill's soft top / bottom edges


def coverage_mask(poly, w, h, line_width):
    """For a polygon given relative to a w x h image: per row, runs of [count, fill coverage, outline coverage]
    (0..255). The fill is worked out on SUB sub-rows per row (exact left / right edges); the outline from each
    nearby pixel's distance to it, so a hairline stays a soft 1 px line."""
    n = len(poly)
    edges = [(poly[i], poly[(i + 1) % n]) for i in range(n)]
    acc = [[0.0] * (w + 2) for _ in range(h)]         # per row: a difference array of fill coverage
    by_row = [[] for _ in range(h)]                   # the pieces of outline that cross each row
    for e in edges:
        (ax, ay), (bx, by) = e
        if ay != by:
            for j in range(max(0, int(min(ay, by))), min(h - 1, int(max(ay, by))) + 1):
                by_row[j].append(e)
    wgt = 1.0 / SUB
    for j in range(h):
        row = acc[j]
        here = by_row[j]
        for k in range(SUB):
            y = j + (k + 0.5) / SUB
            xs = sorted(ax + (y - ay) * (bx - ax) / (by - ay) for (ax, ay), (bx, by) in here
                        if (ay <= y < by) or (by <= y < ay))
            for m in range(0, len(xs) - 1, 2):
                a, b = max(0.0, xs[m]), min(float(w), xs[m + 1])
                if b <= a:
                    continue
                ia, ib = int(a), int(b)
                if ia == ib:
                    row[ia] += (b - a) * wgt
                    row[ia + 1] -= (b - a) * wgt
                    continue
                row[ia] += (ia + 1 - a) * wgt
                row[ia + 1] -= (ia + 1 - a) * wgt
                row[ia + 1] += wgt
                row[ib] -= wgt
                row[ib] += (b - ib) * wgt
                row[ib + 1] -= (b - ib) * wgt
    near = [dict() for _ in range(h)]                 # pixels within reach of the outline -> pieces near them
    half = line_width / 2.0
    reach = half + 1.0
    if line_width > 0:
        for (ax, ay), (bx, by) in edges:
            lo, hi = int(max(0, min(ay, by) - reach)), int(min(h - 1, max(ay, by) + reach))
            for j in range(lo, hi + 1):
                cy = j + 0.5
                if abs(by - ay) < 1e-9:
                    xa, xb = min(ax, bx), max(ax, bx)
                else:
                    t1 = max(0.0, min(1.0, (cy - reach - ay) / (by - ay)))
                    t2 = max(0.0, min(1.0, (cy + reach - ay) / (by - ay)))
                    xa, xb = sorted((ax + t1 * (bx - ax), ax + t2 * (bx - ax)))
                for i in range(max(0, int(xa - reach)), min(w - 1, int(xb + reach)) + 1):
                    near[j].setdefault(i, []).append((ax, ay, bx, by))
    rows = []
    for j in range(h):
        runs, cov, cur = [], 0.0, None
        nj, aj = near[j], acc[j]
        for i in range(w):
            cov += aj[i]
            qa = int(_clamp01(cov) * 255 + 0.5)
            qo = 0
            if i in nj:
                px, py = i + 0.5, j + 0.5
                d = min(_seg_dist(px, py, *seg) for seg in nj[i])
                qo = int(_clamp01(half + 0.5 - d) * 255 + 0.5)
            if (qa, qo) == cur:
                runs[-1][0] += 1
            else:
                runs.append([1, qa, qo])
                cur = (qa, qo)
        rows.append(runs)
    return rows


def _stretched_mask(x1, y1, x2, y2, radii, width, pad):
    """The coverage mask of a rounded rectangle at (x1, y1)-(x2, y2) in image pixels (the image starts at 0, 0
    and has `pad` pixels round the shape). Away from the corners every row, and every column, is the same:
    so the mask is worked out for a compact copy whose straight sides are a few pixels long, then those
    sides are stretched to the real size by repeating a middle row and widening a middle run. A bar that
    grows, or a message that shrinks, costs almost nothing per frame."""
    tl, tr, br, bl = radii
    top, bottom, left, right = max(tl, tr), max(bl, br), max(tl, bl), max(tr, br)
    ky = int(max(0.0, (y2 - bottom) - (y1 + top) - 6))
    kx = int(max(0.0, (x2 - right) - (x1 + left) - 6))
    w = math.ceil(x2 - kx) + pad
    h = math.ceil(y2 - ky) + pad
    pts = control_points(x1, y1, x2 - kx, y2 - ky, radii)
    steps = max(3, min(10, int(min(max(radii), (x2 - x1) / 2, (y2 - y1) / 2) / 2)))   # small corners: fewer pieces
    rows = coverage_mask(_straighten(smooth_outline(pts, steps)), w, h, width)
    if kx:
        col = int(x1 + left + 3)                   # a column in the straight part of the top and bottom
        out = []
        for runs in rows:
            runs = [list(r) for r in runs]
            seen = 0
            for r in runs:
                if seen <= col < seen + r[0]:
                    r[0] += kx
                    break
                seen += r[0]
            out.append(runs)
        rows = out
    if ky:
        j = int(y1 + top + 3)                      # a row in the straight part of the sides
        rows = rows[:j] + [rows[j]] * ky + rows[j:]
    return rows


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    t = 0.0 if ll == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / ll))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _runs_at(runs, start, width):
    """Runs moved `start` pixels to the right and padded with clear pixels to `width`."""
    out = [[start, 0, 0]] if start else []
    out += [list(r) for r in runs]
    used = start + sum(r[0] for r in runs)
    if used < width:
        out.append([width - used, 0, 0])
    return out


def paint_with_shadow(mask, w, fill, outline, shadow, dx, dy, backdrop):
    """Like paint_mask, with a copy of the shape's fill in `shadow` colour, dx, dy pixels down-right, under
    it, all blended into `backdrop`: every pixel solid or clear."""
    width = w + dx
    clear = [[width, 0, 0]]
    memo = {}
    rows = []
    for j in range(len(mask) + dy):
        top = _runs_at(mask[j], 0, width) if j < len(mask) else clear
        under = _runs_at(mask[j - dy], dx, width) if j >= dy else clear
        row = bytearray()
        a = b = 0
        ra, rb = [list(r) for r in top], [list(r) for r in under]
        while a < len(ra) and b < len(rb):
            n = min(ra[a][0], rb[b][0])
            key = (ra[a][1], ra[a][2], rb[b][1])
            px = memo.get(key)
            if px is None:
                qa, qo, qs = key
                if not (qa or qo or qs):
                    px = b"\x00\x00\x00\x00"
                else:
                    base = [backdrop[k] + (shadow[k] - backdrop[k]) * qs / 255.0 for k in range(3)]
                    top_px = _pixel(fill, outline, qa / 255.0, qo / 255.0)
                    t = top_px[3] / 255.0
                    px = bytes([int(base[k] + (top_px[k] - base[k]) * t + 0.5) for k in range(3)] + [255])
                memo[key] = px
            row += px * n
            ra[a][0] -= n
            rb[b][0] -= n
            if not ra[a][0]:
                a += 1
            if not rb[b][0]:
                b += 1
        rows.append(bytes(row))
    return rows


def paint_mask(mask, fill, outline, backdrop=None):
    """RGBA rows from a coverage_mask, in these colours (either may be None). With a `backdrop` colour (the
    plain background the shape sits on) the soft edge is blended into it here and every pixel is either
    solid or fully clear: Tk draws such an image much faster than one with partly clear pixels (on Linux it
    reads the screen back to blend those). Without one, the edge stays partly clear and Tk blends it with
    whatever is underneath."""
    memo = {}
    rows = []
    for runs in mask:
        row = bytearray()
        for count, qa, qo in runs:
            px = memo.get((qa, qo))
            if px is None:
                px = _pixel(fill, outline, qa / 255.0, qo / 255.0)
                if backdrop is not None and px[3]:
                    a = px[3] / 255.0
                    px = bytes([int(backdrop[k] + (px[k] - backdrop[k]) * a + 0.5) for k in range(3)] + [255])
                memo[(qa, qo)] = px
            row += px * count
        rows.append(bytes(row))
    return rows


def _photo(master, w, h, rows):
    return tk.PhotoImage(master=master, data=base64.b64encode(_png(w, h, rows)))


def _cache(canvas, kind):
    root = canvas._root()
    stores = getattr(root, "_smooth_cache", None)
    if stores is None:
        stores = root._smooth_cache = {}
    return stores.setdefault(kind, {})


def _cached(canvas, key, make):
    """Per window and per kind (key[0]: masks, which are cheap to keep, and images, kept fewer), the oldest
    quarter dropped when full (an image still on screen stays alive through its canvas)."""
    store = _cache(canvas, key[0])
    value = store.get(key)
    if value is None:
        limit = _CACHE_MAX * 4 if key[0] == "mask" else _CACHE_MAX
        if len(store) >= limit:
            for k in list(store)[: limit // 4]:
                del store[k]
        value = store[key] = make()
    return value


# ---------------------------------------------------------------- the canvas
class SmoothCanvas(tk.Canvas):
    """A Canvas whose round_rect() shapes are drawn smooth. Everything else is an ordinary Canvas."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._rr = {}                  # polygon id -> {"box", "radii", "fill", "outline", "width", "img", "state"}

    # -- making and changing shapes
    def round_rect(self, x1, y1, x2, y2, r, fill="", outline="", width=1, tags=(), radii=None, state="normal",
                   shadow=None):
        """A rounded rectangle (corner radius r, or `radii` = (tl, tr, br, bl)); returns its canvas item.
        `shadow` = (colour, dx, dy): a soft copy of the shape, offset by whole pixels, drawn under it in the
        same image (one solid image is much cheaper for Tk to draw than a shape over a separate shadow)."""
        if isinstance(tags, str):
            tags = (tags,)
        item = super().create_polygon(*_outline_points(x1, y1, x2, y2), fill="", outline="", tags=tuple(tags),
                                      state=state)
        self._rr[item] = {"box": (x1, y1, x2, y2), "radii": tuple(radii) if radii else (r, r, r, r),
                          "fill": fill or "", "outline": outline or "", "width": width, "img": None,
                          "state": state, "photo": None, "shadow": shadow}
        self._render(item)
        return item

    def round_rect_coords(self, tag_or_id, x1, y1, x2, y2, r=None, radii=None):
        """Move / resize a round_rect (and change its radius, if given)."""
        for item in self._rr_items(tag_or_id):
            rec = self._rr[item]
            rec["box"] = (x1, y1, x2, y2)
            if radii is not None:
                rec["radii"] = tuple(radii)
            elif r is not None:
                rec["radii"] = (r, r, r, r)
            super().coords(item, *_outline_points(x1, y1, x2, y2))
            self._render(item)

    def _rr_items(self, tag_or_id):
        try:
            found = super().find_withtag(tag_or_id)
        except tk.TclError:
            return []
        return [i for i in found if i in self._rr]

    def _render(self, item, force=False):
        rec = self._rr[item]
        x1, y1, x2, y2 = (round(v * 4) / 4.0 for v in rec["box"])     # quarter pixels: animations reuse shapes
        # colours snapped to steps of 4 (invisible): a fade or a hover tint then reuses the same few images
        fill, outline = _snap(_rgb(rec["fill"])), _snap(_rgb(rec["outline"]))
        sig = (x1, y1, x2, y2, rec["radii"], fill, outline, rec["width"], rec["state"])
        if not force and rec.get("sig") == sig:
            return                                     # nothing changed (a redraw of the rest of the canvas)
        rec["sig"] = sig
        if x2 - x1 < 0.5 or y2 - y1 < 0.5 or (fill is None and outline is None):
            self._show_image(item, None, 0, 0)
            return
        width = rec["width"] if outline else 0
        pad = math.ceil(width / 2.0) + 1
        ox, oy = math.floor(x1) - pad, math.floor(y1) - pad
        shape = ("mask", x1 - ox, y1 - oy, x2 - x1, y2 - y1, rec["radii"], width)
        m = _cached(self, shape, lambda: _stretched_mask(x1 - ox, y1 - oy, x2 - ox, y2 - oy, rec["radii"], width, pad))
        w, h = sum(run[0] for run in m[0]), len(m)
        sh = rec["shadow"]
        if sh:
            dx, dy = int(sh[1]), int(sh[2])
            backdrop = self._backdrop(item, ox, oy, ox + w + dx, oy + h + dy) or self._canvas_rgb()
            photo = _cached(self, ("photo",) + shape + (fill, outline, backdrop, sh),
                            lambda: _photo(self, w + dx, h + dy, paint_with_shadow(m, w, fill, outline, _rgb(sh[0]),
                                                                                    dx, dy, backdrop)))
        else:
            backdrop = self._backdrop(item, ox, oy, ox + w, oy + h)
            photo = _cached(self, ("photo",) + shape + (fill, outline, backdrop),
                            lambda: _photo(self, w, h, paint_mask(m, fill, outline, backdrop)))
        self._show_image(item, photo, ox, oy)

    def _backdrop(self, item, x1, y1, x2, y2):
        """The canvas colour (r, g, b) when nothing visible lies under the shape (so its edge can be blended in
        advance), else None (a shadow, a track: Tk blends the edge with it)."""
        try:
            bg = super().cget("bg")            # (the canvas's own: RoundButton.cget("bg") is its fill colour)
            images = {rec["img"]: rec for rec in self._rr.values() if rec["img"] is not None}
            for other in super().find_overlapping(x1, y1, x2, y2):
                if other == item:
                    break                              # (lowest first: the rest are above it)
                if other in self._rr or super().type(other) in ("text", "line", "window"):
                    continue                           # invisible stand-ins; text and lines go on top / at edges
                if super().itemcget(other, "state") == "hidden":
                    continue
                rec = images.get(other)
                if rec is not None and not rec["outline"] and rec["fill"] in (bg, ""):
                    continue                           # a shape in the canvas colour (a button's resting shadow)
                return None
            return self._canvas_rgb()
        except tk.TclError:
            return None

    def _canvas_rgb(self):
        bg = super().cget("bg")
        if getattr(self, "_bg_rgb", (None,))[0] != bg:
            self._bg_rgb = (bg, tuple(v // 257 for v in self.winfo_rgb(bg)))
        return self._bg_rgb[1]

    def _show_image(self, item, photo, ox, oy):
        rec = self._rr[item]
        if photo is not None and rec["img"] is not None and rec["photo"] is photo and rec.get("at") == (ox, oy) \
                and rec.get("shown_state") == rec["state"]:
            return                                            # nothing changed: no work for Tk either
        rec["photo"], rec["at"], rec["shown_state"] = photo, (ox, oy), rec["state"]   # (keeps the image alive)
        if photo is None:
            if rec["img"] is not None:
                super().itemconfigure(rec["img"], state="hidden")
            return
        if rec["img"] is None:
            rec["img"] = super().create_image(ox, oy, image=photo, anchor="nw", state=rec["state"])
            super().tag_raise(rec["img"], item)
        else:
            super().coords(rec["img"], ox, oy)
            super().itemconfigure(rec["img"], image=photo, state=rec["state"])

    def _restack(self, items):
        for item in items:
            img = self._rr[item]["img"]
            if img is not None:
                super().tag_raise(img, item)
        touched = set(items)                           # what lies under these, and the shapes over them, changed
        for item in items:
            x1, y1, x2, y2 = self._rr[item]["box"]
            touched.update(i for i in super().find_overlapping(x1, y1, x2, y2) if i in self._rr)
        for item in touched:
            self._render(item, force=True)

    # -- the ordinary Canvas methods, kept working for these shapes
    def itemconfigure(self, tag_or_id, cnf=None, **kw):
        kw = dict(cnf or {}, **kw)
        rr = self._rr_items(tag_or_id) if kw else []
        if not rr:
            return super().itemconfigure(tag_or_id, kw or None) if kw else super().itemconfigure(tag_or_id)
        mine = {k: kw.pop(k) for k in ("fill", "outline", "width", "state") if k in kw}
        for item in super().find_withtag(tag_or_id):
            if item in self._rr:
                if kw:
                    super().itemconfigure(item, **kw)
                rec = self._rr[item]
                for k, v in mine.items():
                    rec[k] = v
                if "state" in mine:
                    super().itemconfigure(item, state=mine["state"])
                self._render(item)
            elif kw or mine:
                super().itemconfigure(item, **kw, **mine)

    itemconfig = itemconfigure

    def itemcget(self, tag_or_id, option):
        rr = self._rr_items(tag_or_id)
        if rr and option in ("fill", "outline", "width", "state"):
            return self._rr[rr[0]][option]
        return super().itemcget(tag_or_id, option)

    def coords(self, tag_or_id, *args):
        out = super().coords(tag_or_id, *args)
        if args:
            pts = list(args[0]) if len(args) == 1 and isinstance(args[0], (list, tuple)) else list(args)
            xs, ys = pts[0::2], pts[1::2]
            for item in self._rr_items(tag_or_id):
                self._rr[item]["box"] = (min(xs), min(ys), max(xs), max(ys))
                self._render(item)
        return out

    def move(self, tag_or_id, dx, dy):
        super().move(tag_or_id, dx, dy)
        for item in self._rr_items(tag_or_id):
            rec = self._rr[item]
            x1, y1, x2, y2 = rec["box"]
            rec["box"] = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
            self._render(item)

    def delete(self, *args):
        gone = set()
        for a in args:
            gone.update(self._rr_items(a))
        for item in gone:
            img = self._rr.pop(item)["img"]
            if img is not None:
                super().delete(img)
        super().delete(*args)

    def tag_raise(self, tag_or_id, above=None):
        if above is not None:
            if self._rr_items(above):           # above a shape means above its image too
                marks = [(self._rr[i]["img"] or i) if i in self._rr else i for i in super().find_withtag(above)]
                above = max(marks, key=self._stack_index)
            super().tag_raise(tag_or_id, above)
        else:
            super().tag_raise(tag_or_id)
        self._restack(self._rr_items(tag_or_id))

    def tag_lower(self, tag_or_id, below=None):
        if below is not None:
            super().tag_lower(tag_or_id, below)
        else:
            super().tag_lower(tag_or_id)
        self._restack(self._rr_items(tag_or_id))

    lift = tkraise = tag_raise
    lower = tag_lower

    def _stack_index(self, item):
        return super().find_all().index(item)

    def triangle_image(self, w, h, fill, right=None):
        """A small soft-edged triangle pointing down (w x h), blended onto the canvas colour: for marks. With
        `right`, the right half is in that colour (split down the middle; an odd middle column is half each)."""
        bg = self._canvas_rgb()
        key = ("photo", "triangle", w, h, fill, right, bg)

        def make():
            mask = coverage_mask([(0.5, 0.5), (w - 0.5, 0.5), (w / 2.0, h - 0.5)], w, h, 0)
            rows = paint_mask(mask, _rgb(fill), None, bg)
            if right is not None and right != fill:
                other, half = paint_mask(mask, _rgb(right), None, bg), w // 2
                mixed = []
                for a, b in zip(rows, other):
                    mid = b""
                    if w % 2:
                        mid = bytes((a[4 * half + k] + b[4 * half + k] + 1) // 2 for k in range(4))
                    mixed.append(a[:4 * half] + mid + b[4 * (w - half):])
                rows = mixed
            return _photo(self, w, h, rows)
        return _cached(self, key, make)

    def icon_image(self, name, size, fill):
        """A small soft-edged icon (ICONS: home, desktop, documents, downloads, folder, file, book), size x size
        pixels, in `fill`, see-through around it so it sits on any row colour (a selected row too)."""
        key = ("photo", "icon", name, size, fill)

        def make():
            k = size / 16.0
            grids = [coverage_mask([(x * k, y * k) for x, y in poly], size, size, 0) for poly in ICONS[name]]
            rows = []
            for j in range(size):                       # the shapes' coverage together (they never overlap)
                cov = [0] * size
                for g in grids:
                    i = 0
                    for n, qa, _qo in g[j]:
                        if qa:
                            for x in range(i, i + n):
                                cov[x] = max(cov[x], qa)
                        i += n
                runs = []
                for v in cov:
                    if runs and runs[-1][1] == v:
                        runs[-1][0] += 1
                    else:
                        runs.append([1, v, 0])
                rows.append(runs)
            return _photo(self, size, size, paint_mask(rows, _rgb(fill), None))
        return _cached(self, key, make)

    def smooth_image(self, tag_or_id):
        """The image item drawn for a round_rect (tests), or None."""
        rr = self._rr_items(tag_or_id)
        return self._rr[rr[0]]["img"] if rr else None


def _ring(cx, cy, outer, inner, n=24):
    """A ring as one polygon: round the outer circle, then back round the inner one (the even-odd fill leaves the
    middle clear)."""
    pts = [(cx + outer * math.cos(2 * math.pi * k / n), cy + outer * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]
    return pts + [(cx + inner * math.cos(2 * math.pi * k / n), cy + inner * math.sin(2 * math.pi * k / n))
                  for k in range(n, -1, -1)]


# little filled icons on a 16 x 16 grid, one style (UI-42's file picker, M-8); each is a list of polygons that
# do not overlap
ICONS = {
    "home": [[(8, 1.5), (15, 8), (13, 8), (13, 14.5), (9.6, 14.5), (9.6, 10.2), (6.4, 10.2), (6.4, 14.5),
              (3, 14.5), (3, 8), (1, 8)]],
    "desktop": [[(1, 2.5), (15, 2.5), (15, 11), (9.5, 11), (9.5, 12.8), (11.8, 12.8), (11.8, 14.5), (4.2, 14.5),
                 (4.2, 12.8), (6.5, 12.8), (6.5, 11), (1, 11)]],
    "documents": [[(3, 1.5), (9.5, 1.5), (13.5, 5.5), (13.5, 14.5), (3, 14.5)]],
    "file": [[(3.5, 2), (9.5, 2), (12.5, 5), (12.5, 14), (3.5, 14)]],
    "downloads": [[(6.6, 1.5), (9.4, 1.5), (9.4, 6.5), (12.5, 6.5), (8, 11), (3.5, 6.5), (6.6, 6.5)],
                  [(1.5, 10.5), (3.3, 10.5), (3.3, 12.8), (12.7, 12.8), (12.7, 10.5), (14.5, 10.5), (14.5, 14.5),
                   (1.5, 14.5)]],
    "folder": [[(1, 3), (6.2, 3), (7.8, 4.8), (15, 4.8), (15, 13.5), (1, 13.5)]],
    "book": [[(2.5, 1.5), (4.6, 1.5), (4.6, 14.5), (2.5, 14.5)], [(5.6, 1.5), (13.5, 1.5), (13.5, 14.5), (5.6, 14.5)]],
    # a magnifier (UI-51): a ring, its hole made by tracing the inner circle back the other way, and a handle
    "search": [_ring(6.5, 6.5, 5.0, 3.0),
               [(9.6, 11.0), (11.0, 9.6), (15.0, 13.6), (13.6, 15.0)]],
}


def _outline_points(x1, y1, x2, y2):
    """The invisible polygon behind a smooth shape: its box (for bbox, find and stacking)."""
    return [x1, y1, x2, y1, x2, y2, x1, y2]


# ---------------------------------------------------------------- a sort arrow that fills like a loading bar
def arrow_image(widget, w, h, fill, track, reveal=1.0, up=False):
    """A small soft-edged triangle pointing up or down (w x h, see-through around it), filled with `fill` for
    `reveal` (0..1) of its height and `track` (a paler colour, like an empty bar) for the rest. A down arrow
    fills from the top, an up arrow from the bottom: Browse's sort arrow fills as a sort loads. Cached per
    pixel row of fill."""
    rows_lit = round(max(0.0, min(1.0, reveal)) * h * 4) / 4.0
    key = ("photo", "arrow", w, h, fill, track, rows_lit, up)

    def make():
        tip, base = (0.5, h - 0.5) if up else (h - 0.5, 0.5)
        mask = coverage_mask([(0.5, base), (w - 0.5, base), (w / 2.0, tip)], w, h, 0)
        f, t = _rgb(fill), _rgb(track)
        rows = []
        for j, runs in enumerate(mask):
            k = _clamp01(rows_lit - (h - 1 - j if up else j))       # how much of this pixel row is filled
            colour = tuple(int(t[c] + (f[c] - t[c]) * k + 0.5) for c in range(3))
            rows.append(paint_mask([runs], colour, None)[0])
        return _photo(widget, w, h, rows)
    return _cached(widget, key, make)


# ---------------------------------------------------------------- the area under a curve
def curve_rows(w, h, ys, fill, line, line_width):
    """RGBA rows for the area under a curve and its line: ys[i] is the curve's height (pixels from the top,
    fractional) at the left edge of column i (w + 1 values). The area's top edge and the line are soft."""
    fill_c, line_c = _rgb(fill), _rgb(line)
    half = line_width / 2.0
    rows = []
    for j in range(h):
        py = j + 0.5
        row = bytearray()
        for i in range(w):
            ya, yb = ys[i], ys[i + 1]
            ym = (ya + yb) / 2.0
            slope = yb - ya
            # the area: the share of this pixel below the curve (exact for a straight piece of curve)
            lo, hi = min(ya, yb), max(ya, yb)
            if py - 0.5 >= hi:
                a_fill = 1.0
            elif py + 0.5 <= lo:
                a_fill = 0.0
            else:
                a_fill = _clamp01(py + 0.5 - ym) if hi - lo < 1 else _clamp01((py + 0.5 - lo) / (hi - lo + 1))
            # the line: distance from the pixel centre to the curve, measured square to it
            d = abs(py - ym) / math.sqrt(1.0 + slope * slope)
            a_line = _clamp01(half + 0.5 - d) if line_c else 0.0
            row += _pixel(fill_c, line_c, a_fill if fill_c else 0.0, a_line)
        rows.append(bytes(row))
    return rows


def curve_image(canvas, w, h, ys, fill, line, line_width=2):
    """A PhotoImage of the area under the curve `ys` (see curve_rows) and its line, cached."""
    key = ("curve", w, h, tuple(round(y, 2) for y in ys), fill, line, line_width)
    return _cached(canvas, key, lambda: _photo(canvas, w, h, curve_rows(w, h, ys, fill, line, line_width)))
