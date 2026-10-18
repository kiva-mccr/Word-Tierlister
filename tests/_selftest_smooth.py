import _paths  # noqa: F401  (puts src/ and the top folder on the import path)
"""smooth.py: soft-edged rounded shapes drawn as images, standing in for Tk's jagged canvas polygons."""
import tkinter as tk
import smooth as SM
from smooth import SmoothCanvas

# ---- the pixels: inside solid, outside clear, the edge in between
mask = SM._stretched_mask(1.0, 1.0, 41.0, 21.0, (8, 8, 8, 8), 0, 1)
w, h = sum(r[0] for r in mask[0]), len(mask)
assert (w, h) == (42, 22)


def at(m, i, j):
    seen = 0
    for n, qa, qo in m[j]:
        if seen <= i < seen + n:
            return qa
        seen += n


assert at(mask, 20, 10) == 255 and at(mask, 0, 0) == 0                          # middle solid, outside clear
assert 0 < at(mask, 1, 2) < 255 or 0 < at(mask, 2, 1) < 255                       # the round corner is soft
assert at(mask, 1, 10) == 255 and at(mask, 0, 10) == 0                            # a straight side on a pixel line: crisp
# stretching the straight sides gives exactly what working out the whole shape would
pts = SM.control_points(1.0, 1.0, 81.0, 51.0, (8, 8, 8, 8))
direct = SM.coverage_mask(SM.smooth_outline(pts, 4), 82, 52, 1)
stretched = SM._stretched_mask(1.0, 1.0, 81.0, 51.0, (8, 8, 8, 8), 1, 1)
flat = lambda m: [[(qa, qo) for n, qa, qo in row for _ in range(n)] for row in m]
fd, fs = flat(direct), flat(stretched)
assert len(fd) == len(fs) and all(len(a) == len(b) for a, b in zip(fd, fs))
assert max(abs(p[0] - q[0]) + abs(p[1] - q[1]) for a, b in zip(fd, fs) for p, q in zip(a, b)) <= 2   # (rounding)
# a square corner (radius 0) stays square; a huge radius gives the tier pills' rounded square, not a circle
sq = SM._stretched_mask(1.0, 1.0, 21.0, 21.0, (0, 0, 0, 0), 0, 1)
assert at(sq, 1, 1) == 255
pill = SM._stretched_mask(1.0, 1.0, 61.0, 71.0, (35, 35, 35, 35), 0, 1)
assert at(pill, 8, 12) == 255                                                      # (a circle would leave it clear)
# painted: a known backdrop means solid-or-clear pixels only (cheap for Tk); without one, a soft alpha edge
rows = SM.paint_mask(mask, (255, 179, 193), None, backdrop=(251, 247, 244))
assert all(px in (0, 255) for row in rows for px in row[3::4])
rows = SM.paint_mask(mask, (255, 179, 193), None)
assert any(0 < px < 255 for row in rows for px in row[3::4])
assert SM._snap((1, 2, 254)) == (0, 4, 255)

# ---- on a canvas: an invisible polygon (tags, coords, bbox, stacking) with its image just above it
root = tk.Tk()
c = SmoothCanvas(root, width=300, height=200, bg="#FBF7F4", highlightthickness=0); c.pack(); root.update()
item = c.round_rect(10, 10, 110, 60, 12, fill="#FFB3C1", outline="#C08090", tags=("pill", "p0"))
img = c.smooth_image("p0")
assert img and c.type(img) == "image" and c.itemcget("p0", "fill") == "#FFB3C1"     # the colour it is drawn in
assert tk.Canvas.itemcget(c, item, "fill") == ""                                        # the polygon itself: invisible
assert c.find_all().index(img) == c.find_all().index(item) + 1
c.itemconfigure("p0", fill="#FFC9D3"); assert c.itemcget("p0", "fill") == "#FFC9D3" and c.smooth_image("p0") == img
x0 = c.coords(img)[0]; c.move("pill", 15, 0); assert c.coords(img)[0] == x0 + 15     # it follows a move
c.round_rect_coords("p0", 20, 20, 200, 80, r=20); assert c.bbox("p0")[2] >= 199
t = c.create_text(50, 30, text="S")
c.tag_raise(t, "p0"); assert c.find_all().index(t) > c.find_all().index(img)          # above the shape = above its image
c.tag_lower("p0"); assert c.find_all().index(img) == c.find_all().index(item) + 1     # lowered together
c.itemconfigure("p0", state="hidden"); assert c.itemcget(img, "state") == "hidden"
c.itemconfigure("p0", state="normal")
# the same shape and colours are drawn once and reused (a hover tint going back and forth)
a = c.round_rect(10, 100, 60, 130, 8, fill="#DDE7FB"); b = c.round_rect(70, 100, 120, 130, 8, fill="#DDE7FB")
assert c._rr[a]["photo"] is c._rr[b]["photo"]
# over another shape the edge stays see-through; on the plain canvas it is blended in advance
under = c.round_rect(150, 120, 290, 190, 10, fill="#3D3A4B")
over = c.round_rect(160, 130, 280, 180, 10, fill="#FFB3C1")
assert c._backdrop(over, 160, 130, 280, 180) is None and c._backdrop(under, 150, 120, 290, 190) is not None
# deleting removes the image too
c.delete("pill"); assert not c.find_withtag("p0") and img not in c.find_all()
# a built-in shadow: one solid image, larger by the offset
card = c.round_rect(10, 140, 100, 180, 10, fill="#FFFFFF", outline="#E6DFEA", shadow=("#E9E2E6", 4, 4))
ph = c._rr[card]["photo"]
assert ph.width() == 90 + 2 * 2 + 4 and ph.height() == 40 + 2 * 2 + 4
c.delete("all"); assert not c._rr
root.destroy()

# ---- the curve image (queue dialog): the area under the curve solid, above it clear, with a soft line
ys = [10 + i * 0.5 for i in range(41)]
rows = SM.curve_rows(40, 40, ys, "#FFCBA4", "#806050", 2)
assert rows[39][4 * 20 + 3] == 255 and rows[0][4 * 20 + 3] == 0
assert any(0 < rows[j][4 * 20 + 3] < 255 for j in range(15, 25))
print("SMOOTH OK")
