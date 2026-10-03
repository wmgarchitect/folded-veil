"""nest.py - the 352 pieces on real sheet. Session 3.

Each unit is four identical pieces, and each piece unrolls to one flat
quadrilateral: the frame edge, two fold edges, and the aperture edge.

The quadrilateral is concave while the fold is shallow and turns convex at
about f = 0.4. That split is the story of this session. A shallow blank fills
barely a third of its own bounding box, and the notch that makes it concave is
exactly the shape of the next blank's point, so pairing rescues it. The deepest
blank is convex, already fills more of its box, and pairing does nothing for
it at all.

Sheet: 1500 x 3000 mm mill finish aluminium, the common stock size, with the
1500 mm dimension across the coil so the grain runs the long way.
Rotating a blank by 180 degrees keeps the grain running the same way. Rotating
it by 90 degrees does not, so only 180 is allowed here.

Run:  python3 src/nest.py      (writes nest_results.json, fabrication_schedule.csv)
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys
from typing import Dict, List, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import veil as v      # noqa: E402
import field as fl    # noqa: E402

Pt = Tuple[float, float]
Tri = Tuple[Pt, Pt, Pt]

# Two standard aluminium stock sizes, both common in Turkish fabrication.
STOCK = {
    "1500 x 3000": (1.500, 3.000),
    "2000 x 4000": (2.000, 4.000),
}
MARGIN = 0.010                    # trim allowance at the sheet edge, m
KERF = 0.003                      # laser kerf, m. Also the minimum part gap.


# ---------------------------------------------------------------------------
# The blank

def piece_triangles(f: float, dmax: float = v.DMAX_DEFAULT) -> List[Tri]:
    """The two triangles of one piece, unrolled flat and isometric."""
    u = v.unit(f, dmax)
    fa, fb = v.pieces(u)[0]
    sub = v.Unit(f=u.f, d=u.d, r=u.r, A=u.A, B=u.B,
                 faces=[u.faces[fa], u.faces[fb]], pinwheel=False)
    return [tuple(t) for t in v.unroll(sub)]


def piece_outline(f: float, dmax: float = v.DMAX_DEFAULT) -> List[Pt]:
    """The blank as one closed quadrilateral, in cut order.

    The two triangles are (A0, A1, B1) and (A0, B1, B0), sharing A0-B1. The
    outline is therefore A1 -> A0 -> B0 -> B1 -> A1: frame edge, fold, aperture
    edge, fold.
    """
    t1, t2 = piece_triangles(f, dmax)
    A0, A1, B1 = t1
    _, _, B0 = t2
    return [A1, A0, B0, B1]


def poly_area(p: Sequence[Pt]) -> float:
    s = 0.0
    for i in range(len(p)):
        x1, y1 = p[i]
        x2, y2 = p[(i + 1) % len(p)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def bbox(pts: Sequence[Pt]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def concave_crossover(dmax: float = v.DMAX_DEFAULT, n: int = 400) -> float:
    """The f at which the blank stops being concave and becomes convex."""
    prev, out = None, 1.0
    for i in range(n + 1):
        f = i / n
        c = is_concave(piece_outline(f, dmax))
        if prev is not None and c != prev:
            out = round(f, 3)
            break
        prev = c
    return out


def is_concave(p: Sequence[Pt]) -> bool:
    signs = []
    n = len(p)
    for i in range(n):
        ax, ay = p[i]
        bx, by = p[(i + 1) % n]
        cx, cy = p[(i + 2) % n]
        signs.append((bx - ax) * (cy - by) - (by - ay) * (cx - bx))
    return any(s > 0 for s in signs) and any(s < 0 for s in signs)


# ---------------------------------------------------------------------------
# Overlap, by separating axis on triangle pairs

def tri_overlap(a: Tri, b: Tri, gap: float = 0.0) -> bool:
    """True if the two triangles overlap, or come closer than `gap`."""
    for tri in (a, b):
        for i in range(3):
            x1, y1 = tri[i]
            x2, y2 = tri[(i + 1) % 3]
            nx, ny = -(y2 - y1), (x2 - x1)
            n = math.hypot(nx, ny)
            if n < 1e-12:
                continue
            nx, ny = nx / n, ny / n
            pa = [nx * p[0] + ny * p[1] for p in a]
            pb = [nx * p[0] + ny * p[1] for p in b]
            if min(pa) - max(pb) >= -gap or min(pb) - max(pa) >= -gap:
                return False
    return True


def clash(ta: Sequence[Tri], tb: Sequence[Tri], gap: float = KERF) -> bool:
    return any(tri_overlap(x, y, gap) for x in ta for y in tb)


def move(tris: Sequence[Tri], dx: float, dy: float) -> List[Tri]:
    return [tuple((p[0] + dx, p[1] + dy) for p in t) for t in tris]


def turn180(tris: Sequence[Tri]) -> List[Tri]:
    return [tuple((-p[0], -p[1]) for p in t) for t in tris]


# ---------------------------------------------------------------------------
# Pairing: one blank against its own 180 degree rotation

def fits(w: float, h: float, usable_w: float, usable_l: float) -> bool:
    """Strict. No 90 degree turn is allowed anywhere in this module, because
    the finish is directional and a turned blank shows its grain across the
    facade while its neighbours show theirs along it. 180 degrees is free."""
    return w <= usable_w and h <= usable_l


def best_pair(f: float, dmax: float = v.DMAX_DEFAULT,
              usable_w: float = 1.98, usable_l: float = 3.98,
              coarse: int = 60) -> Tuple[float, float, float, float]:
    """Slide the rotated copy over the original and keep the smallest bounding
    box THAT STILL FITS THE STOCK. Minimising area alone finds side-by-side
    placements that are a hair smaller on paper and a disaster on the sheet.
    Returns (dx, dy, box_w, box_h)."""
    base = piece_triangles(f, dmax)
    rot = turn180(base)
    bx0, by0, bx1, by1 = bbox([p for t in base for p in t])
    w, h = bx1 - bx0, by1 - by0

    best = None
    for gi in range(coarse + 1):
        dx = bx0 - (bx1 - bx0) * 0.15 + (w * 1.35) * gi / coarse
        for gj in range(coarse + 1):
            dy = by0 - (by1 - by0) * 0.15 + (h * 1.35) * gj / coarse
            cand = move(rot, dx - (-bx0) + bx0, dy - (-by0) + by0)
            cand = move(rot, dx, dy)
            if clash(base, cand):
                continue
            x0, y0, x1, y1 = bbox([p for t in (list(base) + cand) for p in t])
            bw, bh = x1 - x0, y1 - y0
            if not fits(bw, bh, usable_w, usable_l):
                continue
            area = bw * bh
            if best is None or area < best[0]:
                best = (area, dx, dy, bw, bh)
    if best is None:
        return (0.0, 0.0, w, h * 2)

    # refine around the coarse winner
    _, dx, dy, _, _ = best
    step_x, step_y = (w * 1.35) / coarse, (h * 1.35) / coarse
    for _ in range(3):
        improved = False
        for sx in (-1, 0, 1):
            for sy in (-1, 0, 1):
                nx, ny = dx + sx * step_x, dy + sy * step_y
                cand = move(rot, nx, ny)
                if clash(base, cand):
                    continue
                x0, y0, x1, y1 = bbox([p for t in (list(base) + cand) for p in t])
                bw, bh = x1 - x0, y1 - y0
                if not fits(bw, bh, usable_w, usable_l):
                    continue
                area = bw * bh
                if area < best[0] - 1e-9:
                    best = (area, nx, ny, bw, bh)
                    improved = True
        _, dx, dy, _, _ = best
        step_x, step_y = step_x / 2, step_y / 2
        if not improved:
            step_x, step_y = step_x / 2, step_y / 2
    return (best[1], best[2], best[3], best[4])


# ---------------------------------------------------------------------------
# Sheet packing, shelf by shelf

def pack(cells: Sequence[Tuple[float, float]], sheet: Tuple[float, float]
         ) -> Tuple[int, List[list]]:
    """First-fit shelf packing across all open sheets, tallest cell first.

    No cell is ever turned: the finish is directional. A cell goes into the
    first shelf on any open sheet that still has room beside it, else onto a
    new shelf on the first sheet with vertical room, else onto a new sheet.
    This is a decent nester, not an optimal one, so the sheet counts here are
    an upper bound and the waste figures a worst case.
    """
    sw, sl = sheet
    usable_w = sw - 2 * MARGIN
    usable_l = sl - 2 * MARGIN
    order = sorted(cells, key=lambda c: -c[1])

    sheets: List[list] = []        # each: list of placed rectangles
    shelves: List[list] = []       # each: [sheet_index, y, height, used_x]
    used_l: List[float] = []       # vertical space consumed per sheet

    for cell in order:
        w, h = cell[0], cell[1]
        payload = cell[2] if len(cell) > 2 else None
        if not fits(w, h, usable_w, usable_l):
            return (-1, [])

        spot = None
        for sh in shelves:                       # an existing shelf with room
            if h <= sh[2] + 1e-9 and sh[3] + w <= usable_w + 1e-9:
                spot = sh
                break
        if spot is None:                         # a new shelf on an open sheet
            for si in range(len(sheets)):
                if used_l[si] + h <= usable_l + 1e-9:
                    spot = [si, used_l[si], h, 0.0]
                    shelves.append(spot)
                    used_l[si] += h + KERF
                    break
        if spot is None:                         # a new sheet
            sheets.append([])
            used_l.append(h + KERF)
            spot = [len(sheets) - 1, 0.0, h, 0.0]
            shelves.append(spot)

        si, y, _, x = spot
        sheets[si].append([MARGIN + x, MARGIN + y, w, h, payload, False])
        spot[3] = x + w + KERF

    return len(sheets), sheets


# ---------------------------------------------------------------------------

def run(fs: Sequence[float], label: str, stock_name: str = "1500 x 3000",
        dmax: float = v.DMAX_DEFAULT, cache: dict = None) -> dict:
    """fs is one f per unit. Every unit makes four identical pieces."""
    shapes = sorted(set(round(f, 9) for f in fs))
    counts = {s: 4 * sum(1 for f in fs if round(f, 9) == s) for s in shapes}

    sheet = STOCK[stock_name]
    per_shape = {} if cache is None else cache
    for s in shapes:
        if (s, stock_name) in per_shape:
            continue
        out = piece_outline(s, dmax)
        x0, y0, x1, y1 = bbox(out)
        area = poly_area(out)
        dx, dy, pw, ph = best_pair(s, dmax, sheet[0] - 2 * MARGIN,
                                   sheet[1] - 2 * MARGIN)
        per_shape[(s, stock_name)] = {
            "blank_w": x1 - x0, "blank_h": y1 - y0,
            "blank_area": area,
            "bbox_efficiency": area / ((x1 - x0) * (y1 - y0)),
            "pair_dx": dx, "pair_dy": dy,
            "pair_w": pw, "pair_h": ph,
            "pair_efficiency": 2 * area / (pw * ph),
            "count": counts[s],
        }

    single_cells, pair_cells = [], []
    for s in shapes:
        d = per_shape[(s, stock_name)]
        n = d["count"]
        single_cells += [(d["blank_w"] + KERF, d["blank_h"] + KERF,
                          (s, "single"))] * n
        npairs, leftover = divmod(n, 2)
        pair_cells += [(d["pair_w"] + KERF, d["pair_h"] + KERF,
                        (s, "pair"))] * npairs
        pair_cells += [(d["blank_w"] + KERF, d["blank_h"] + KERF,
                        (s, "single"))] * leftover

    n_single, _ = pack(single_cells, sheet)
    n_pair, pair_layout = pack(pair_cells, sheet)

    metal = sum(per_shape[(round(f, 9), stock_name)]["blank_area"] * 4
                for f in fs)
    sheet_area = sheet[0] * sheet[1]
    usable_w = sheet[0] - 2 * MARGIN
    ok = all(fits(per_shape[(s, stock_name)]["blank_w"],
                  per_shape[(s, stock_name)]["blank_h"],
                  usable_w, sheet[1] - 2 * MARGIN) for s in shapes)
    return {
        "label": label,
        "stock": stock_name,
        "fits_without_turning": all(
            per_shape[(s, stock_name)]["blank_w"] <= usable_w for s in shapes),
        "fits_at_all": ok,
        "shapes": len(shapes),
        "pieces": sum(counts.values()),
        "metal_m2": round(metal, 1),
        "bbox_efficiency_min": round(min(per_shape[(s, stock_name)]["bbox_efficiency"] for s in shapes), 4),
        "bbox_efficiency_max": round(max(per_shape[(s, stock_name)]["bbox_efficiency"] for s in shapes), 4),
        "pair_efficiency_min": round(min(per_shape[(s, stock_name)]["pair_efficiency"] for s in shapes), 4),
        "pair_efficiency_max": round(max(per_shape[(s, stock_name)]["pair_efficiency"] for s in shapes), 4),
        "sheets_one_up": n_single,
        "sheets_paired": n_pair,
        "waste_one_up_pct": (round(100 * (1 - metal / (n_single * sheet_area)), 1)
                             if n_single > 0 else None),
        "waste_paired_pct": (round(100 * (1 - metal / (n_pair * sheet_area)), 1)
                             if n_pair > 0 else None),
        "_per_shape": per_shape,
        "_pair_layout": pair_layout,
    }


def main() -> None:
    rad = fl.radial_field()
    rat = fl.rationalise(fl.depths_from(rad), 5)
    rad5 = [(d - v.D_MIN) / (v.DMAX_DEFAULT - v.D_MIN) for d in rat]

    cache = {}
    runs = []
    for stock in STOCK:
        runs.append(run(rad, "free, 26 shapes", stock, cache=cache))
        runs.append(run(rad5, "five families", stock, cache=cache))

    out0 = piece_outline(0.0)
    x0, y0, x1, y1 = bbox(out0)
    results = {
        "blank": {
            "frame_edge_mm": 1500.0,
            "is_concave_at_f0": is_concave(out0),
            "concave_below_f": concave_crossover(),
            "long_side_mm": round((x1 - x0) * 1000, 1),
            "note": ("The frame edge is 1500.0 mm and the standard sheet is "
                     "1500 mm wide. The blank cannot be cut from it with any "
                     "trim allowance unless it is turned, and turning it turns "
                     "the grain."),
        },
        "margin_mm": MARGIN * 1000, "kerf_mm": KERF * 1000,
        "rotation_note": ("180 degrees keeps the grain running the same way on "
                          "a directional finish. 90 degrees does not."),
        "runs": [{k: r[k] for k in r if not k.startswith("_")} for r in runs],
    }
    with open(os.path.join(ROOT, "nest_results.json"), "w") as fh:
        json.dump(results, fh, indent=2)

    # the schedule a fabricator would actually be sent
    shapes = sorted({k[0] for k in cache})
    fives = sorted(set(rat))
    rows = []
    for i, (fv, (col, row)) in enumerate(zip(rad, v.unit_positions())):
        d = cache[(round(fv, 9), "2000 x 4000")]
        rows.append({
            "unit": "FV-%03d" % (i + 1),
            "bay_col": col, "row": row,
            "f": round(fv, 4),
            "depth_mm": round(v.depth(fv) * 1000, 1),
            "aperture_r_mm": round(v.aperture(fv) * 1000, 1),
            "family_free": "T%02d" % (shapes.index(round(fv, 9)) + 1),
            "family_five": "F%d" % (fives.index(rat[i]) + 1),
            "pieces": 4,
            "bend_deg": round(v.piece_fold_angle(v.unit(fv)), 2),
            "blank_w_mm": round(d["blank_w"] * 1000, 1),
            "blank_h_mm": round(d["blank_h"] * 1000, 1),
            "blank_area_m2": round(d["blank_area"], 4),
        })
    with open(os.path.join(ROOT, "fabrication_schedule.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    b = results["blank"]
    print("THE BLANK")
    print("  concave below f = %s, convex above.  frame edge %.1f mm"
          % (b["concave_below_f"], b["frame_edge_mm"]))
    print()
    for r in runs:
        tag = "%s on %s" % (r["label"], r["stock"])
        print("%-34s shapes %3d  pieces %3d  metal %6.1f m2" %
              (tag, r["shapes"], r["pieces"], r["metal_m2"]))
        print("   fits without turning: %s" % r["fits_without_turning"])
        print("   blank fills its bounding box  %.1f%% to %.1f%%"
              % (100 * r["bbox_efficiency_min"], 100 * r["bbox_efficiency_max"]))
        print("   paired with its 180 rotation  %.1f%% to %.1f%%"
              % (100 * r["pair_efficiency_min"], 100 * r["pair_efficiency_max"]))
        print("   sheets one up %3d  waste %s   |   paired %3d  waste %s"
              % (r["sheets_one_up"],
                 ("%4.1f%%" % r["waste_one_up_pct"]) if r["waste_one_up_pct"] else " n/a ",
                 r["sheets_paired"],
                 ("%4.1f%%" % r["waste_paired_pct"]) if r["waste_paired_pct"] else " n/a "))
        print()
    print("schedule written: fabrication_schedule.csv, %d units" % len(rows))


if __name__ == "__main__":
    main()
