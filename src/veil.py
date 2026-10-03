"""veil.py - Facade Logic 01, Folded Veil. Unit geometry and the measurements.

The brief: a folded metal veil over an 18 x 12 m glazed facade. 6 bays x 4
floors, each 3 x 3 m cell split into four 1.5 x 1.5 m units, 96 positions
less 8 at the 6 x 3 m entrance = 88 units, 8 triangular faces each, 704 faces.

One field value f in 0..1 drives both the depth and the aperture:

    d = D_MIN + (dmax - D_MIN) * f          depth, pushed out along -Y
    r = HALF * (0.87 - 0.45 * f)            aperture half-diagonal

Rhino is not involved and is not installed.

Run:  python3 src/veil.py     (writes results.json)
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import List, Sequence, Tuple

Vec = Tuple[float, float, float]

HALF = 0.75          # frame half-size, m. Unit is 1.5 x 1.5 m.
D_MIN = 0.12         # shallowest depth in the gradient, m
DMAX_DEFAULT = 0.90  # deepest depth, adjustable 0.20 to 0.90

BAYS, FLOORS = 6, 4
CELLS = BAYS * FLOORS
UNITS_PER_CELL = 4
ENTRANCE_UNITS = 8   # the 6 x 3 m entrance, ground floor, two central bays
N_UNITS = CELLS * UNITS_PER_CELL - ENTRANCE_UNITS   # 88

# Fabrication reference values, for reading the numbers against something.
SHEET_W = 1.500      # standard aluminium sheet width, m
SHEET_L = 3.000      # standard aluminium sheet length, m
CREASE_READS = 15.0  # degrees off flat below which a fold stops reading as a fold


def depth(f: float, dmax: float = DMAX_DEFAULT) -> float:
    """Fold depth at field value f."""
    return D_MIN + (dmax - D_MIN) * f


def aperture(f: float) -> float:
    """Aperture half-diagonal at field value f."""
    return HALF * (0.87 - 0.45 * f)


def f_of_aperture(r: float) -> float:
    """Inverse of aperture(), for reading a coordinate table back to its f."""
    return (0.87 - r / HALF) / 0.45


# ---------------------------------------------------------------------------
# Geometry

@dataclass
class Unit:
    """One folded unit: 4 frame corners on the facade plane, 4 diamond
    vertices pushed out along -Y, 8 triangular faces."""
    f: float
    d: float
    r: float
    A: List[Vec]          # frame corners, y = 0
    B: List[Vec]          # diamond vertices, y = -d
    faces: List[Tuple[int, ...]]   # indices into A + B, A is 0..3, B is 4..7
    pinwheel: bool

    @property
    def points(self) -> List[Vec]:
        return list(self.A) + list(self.B)


def unit(f: float, dmax: float = DMAX_DEFAULT, pinwheel: bool = False) -> Unit:
    """Build one unit at field value f.

    Frame corners, counter-clockwise seen from outside (-Y):

        A0 (+h, 0, +h)   A1 (-h, 0, +h)   A2 (-h, 0, -h)   A3 (+h, 0, -h)

    Diamond vertices sit on the axes at distance r, depth -d. Which one is
    called B_k decides whether the unit is mirror-symmetric or a pinwheel:

        pinwheel=False  (the built unit) B_k sits on the axis through the
                      midpoint of edge A_(k-1) A_k, so face (Ai, Aj, Bj)
                      straddles its own frame edge. The 8 faces tile the band
                      between frame and aperture exactly once.
        pinwheel=True   B_k sits on the axis through the midpoint of the NEXT
                      edge. Read this way the faces sweep one edge round, and
                      they no longer tile: they cross the aperture and overlap
                      each other. Kept only so overlap_ratio() can measure it.

    The paper's triangulation, for i in 0..3 with j = (i+1) mod 4:

        (Ai, Aj, Bj)  and  (Ai, Bj, Bi)
    """
    h, d, r = HALF, depth(f, dmax), aperture(f)
    A: List[Vec] = [(h, 0.0, h), (-h, 0.0, h), (-h, 0.0, -h), (h, 0.0, -h)]

    # Axis directions through the midpoint of edge A_k -> A_(k+1).
    edge_axis = [(0.0, 1.0), (-1.0, 0.0), (0.0, -1.0), (1.0, 0.0)]   # (x, z)
    shift = 0 if pinwheel else -1
    B: List[Vec] = []
    for k in range(4):
        ax, az = edge_axis[(k + shift) % 4]
        B.append((ax * r, -d, az * r))

    faces = []
    for i in range(4):
        j = (i + 1) % 4
        faces.append((i, j, 4 + j))
        faces.append((i, 4 + j, 4 + i))
    return Unit(f=f, d=d, r=r, A=A, B=B, faces=faces, pinwheel=pinwheel)


# ---------------------------------------------------------------------------
# Vector helpers

def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a: Vec) -> float:
    return math.sqrt(dot(a, a))


def unitv(a: Vec) -> Vec:
    n = norm(a)
    return (a[0] / n, a[1] / n, a[2] / n)


def tri_area(p: Vec, q: Vec, s: Vec) -> float:
    return 0.5 * norm(cross(sub(q, p), sub(s, p)))


def tri_normal(p: Vec, q: Vec, s: Vec) -> Vec:
    return unitv(cross(sub(q, p), sub(s, p)))


# ---------------------------------------------------------------------------
# The measurements

def plan_gap(u: Unit) -> float:
    """Gap in plan between a diamond vertex and the frame edge it points at."""
    return HALF - u.r


def flange_span(u: Unit) -> float:
    """True span of metal from the frame edge to the aperture vertex, i.e. the
    narrowest place in the folded band. sqrt(gap^2 + depth^2)."""
    return math.hypot(plan_gap(u), u.d)


def metal_area(u: Unit) -> float:
    """Developed surface area of the 8 faces, m2. This is the blank area."""
    p = u.points
    return sum(tri_area(p[a], p[b], p[c]) for a, b, c in u.faces)


def open_area(u: Unit) -> float:
    """Projected area of the diamond aperture, m2."""
    return 2.0 * u.r ** 2


def porosity(u: Unit) -> float:
    """Open area as a fraction of the 1.5 x 1.5 m unit."""
    return open_area(u) / (2 * HALF) ** 2


def fold_edges(u: Unit) -> List[Tuple[int, int, int, int]]:
    """The 8 interior fold lines, as (vertex, vertex, face_a, face_b)."""
    seen = {}
    out = []
    for fi, (a, b, c) in enumerate(u.faces):
        for e in ((a, b), (b, c), (c, a)):
            k = tuple(sorted(e))
            if k in seen:
                out.append((k[0], k[1], seen[k], fi))
            else:
                seen[k] = fi
    return out


def dihedral(u: Unit, e0: int, e1: int, fa: int, fb: int) -> float:
    """Angle between two faces across the shared edge e0-e1, degrees.
    180 is flat. Measured between the two faces themselves rather than
    between their normals, because the paper's face list is not
    consistently wound."""
    p = u.points
    t = unitv(sub(p[e1], p[e0]))

    def arm(fi: int) -> Vec:
        v_op = [k for k in u.faces[fi] if k not in (e0, e1)][0]
        w = sub(p[v_op], p[e0])
        proj = dot(w, t)
        return unitv((w[0] - proj * t[0], w[1] - proj * t[1], w[2] - proj * t[2]))

    c = max(-1.0, min(1.0, dot(arm(fa), arm(fb))))
    return math.degrees(math.acos(c))


def fold_angles(u: Unit) -> List[float]:
    """Dihedral angle at every interior fold line, degrees."""
    return [dihedral(u, e0, e1, fa, fb) for e0, e1, fa, fb in fold_edges(u)]


def rake(u: Unit) -> float:
    """Angle of the folded band away from the facade plane, degrees.
    atan(depth / plan gap) at the pinch point."""
    return math.degrees(math.atan2(u.d, plan_gap(u)))


# ---------------------------------------------------------------------------
# Flat pattern

def area_factor(u: Unit) -> float:
    """Developed metal area over the plan area of the band it covers. For a
    tiling surface this is just the rake: always a little over 1. Far above 1
    means the faces are covering ground twice."""
    band = (2 * HALF) ** 2 - open_area(u)
    return metal_area(u) / band


def plan_cover(u: Unit, n: int = 400) -> dict:
    """Rasterise the plan projection of the 8 faces over the unit square and
    report what they cover. A triangulation that tiles the band covers every
    cell outside the aperture exactly once and covers none inside it."""
    p = u.points
    tris = [[(p[k][0], p[k][2]) for k in t] for t in u.faces]

    def inside(tri, x, z) -> bool:
        (x0, z0), (x1, z1), (x2, z2) = tri
        d1 = (x1 - x0) * (z - z0) - (z1 - z0) * (x - x0)
        d2 = (x2 - x1) * (z - z1) - (z2 - z1) * (x - x1)
        d3 = (x0 - x2) * (z - z2) - (z0 - z2) * (x - x2)
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))

    step = 2 * HALF / n
    in_ap = in_ap_covered = band = band_once = band_multi = 0
    for i in range(n):
        x = -HALF + (i + 0.5) * step
        for j in range(n):
            z = -HALF + (j + 0.5) * step
            hits = sum(1 for t in tris if inside(t, x, z))
            if abs(x) + abs(z) < u.r:                 # inside the diamond
                in_ap += 1
                if hits:
                    in_ap_covered += 1
            else:
                band += 1
                if hits == 1:
                    band_once += 1
                elif hits > 1:
                    band_multi += 1
    return {
        "aperture_blocked": in_ap_covered / max(1, in_ap),
        "band_covered_once": band_once / max(1, band),
        "band_covered_twice_or_more": band_multi / max(1, band),
    }


def tiles(u: Unit, n: int = 200) -> bool:
    """True if the 8 faces tile the band between frame and aperture exactly
    once and leave the aperture clear."""
    c = plan_cover(u, n)
    return (c["aperture_blocked"] < 0.01
            and c["band_covered_once"] > 0.98
            and c["band_covered_twice_or_more"] < 0.01)


def pieces(u: Unit) -> List[Tuple[int, int]]:
    """The unit as 4 identical two-triangle pieces, each with a single fold
    line running from a frame corner to an aperture vertex. This is the part
    a press brake would actually make."""
    return [(2 * i, 2 * i + 1) for i in range(4)]


def piece_blank(u: Unit) -> Tuple[float, float, float]:
    """Flat blank of one piece: long side, short side, area. Metres."""
    fa, fb = pieces(u)[0]
    sub_u = Unit(f=u.f, d=u.d, r=u.r, A=u.A, B=u.B,
                 faces=[u.faces[fa], u.faces[fb]], pinwheel=u.pinwheel)
    pts = [q for tri in unroll(sub_u) for q in tri]
    w = max(q[0] for q in pts) - min(q[0] for q in pts)
    h = max(q[1] for q in pts) - min(q[1] for q in pts)
    area = sum(tri_area(*[sub_u.points[k] for k in t]) for t in sub_u.faces)
    return (max(w, h), min(w, h), area)


def piece_fold_angle(u: Unit) -> float:
    """The single fold angle inside one piece, degrees. 180 is flat."""
    fa, fb = pieces(u)[0]
    shared = [v for v in u.faces[fa] if v in u.faces[fb]]
    return dihedral(u, shared[0], shared[1], fa, fb)


def strip_order(u: Unit) -> List[int]:
    """Walk the 8 faces in ring order, each sharing a fold line with the last.
    The paper lists them in pairs, which is not the order they unfold in."""
    adj = {i: [] for i in range(len(u.faces))}
    for _, _, fa, fb in fold_edges(u):
        adj[fa].append(fb)
        adj[fb].append(fa)
    order = [0]
    seen = {0}
    while len(order) < len(u.faces):
        nxt = [k for k in adj[order[-1]] if k not in seen]
        if not nxt:
            raise RuntimeError("faces do not form a single ring")
        order.append(nxt[0])
        seen.add(nxt[0])
    return order


def unroll(u: Unit) -> List[List[Tuple[float, float]]]:
    """Unfold the ring of 8 triangles into the plane, cutting it open at the
    first fold line. Each triangle is laid down isometrically against the one
    before it, so every edge keeps its true length."""
    p = u.points
    order = strip_order(u)
    flat: List[List[Tuple[float, float]]] = []

    # Lay the first triangle down on its own edge.
    a, b, c = u.faces[order[0]]
    ab = norm(sub(p[b], p[a]))
    ac = norm(sub(p[c], p[a]))
    bc = norm(sub(p[c], p[b]))
    cosA = max(-1.0, min(1.0, (ab * ab + ac * ac - bc * bc) / (2 * ab * ac)))
    A2 = (0.0, 0.0)
    B2 = (ab, 0.0)
    C2 = (ac * cosA, ac * math.sqrt(max(0.0, 1 - cosA * cosA)))
    placed = {a: A2, b: B2, c: C2}
    flat.append([A2, B2, C2])

    prev_tri = u.faces[order[0]]
    for fi in order[1:]:
        tri = u.faces[fi]
        known = [v for v in tri if v in prev_tri]
        new = [v for v in tri if v not in prev_tri]
        if len(known) != 2 or len(new) != 1:
            raise RuntimeError("ring is not a strip")
        k0, k1 = known
        n0 = new[0]
        P0, P1 = placed[k0], placed[k1]
        l0 = norm(sub(p[n0], p[k0]))
        l1 = norm(sub(p[n0], p[k1]))
        base = math.dist(P0, P1)
        # Circle intersection, picking the side away from the placed triangle.
        x = (base * base + l0 * l0 - l1 * l1) / (2 * base)
        y2 = max(0.0, l0 * l0 - x * x)
        y = math.sqrt(y2)
        ex = ((P1[0] - P0[0]) / base, (P1[1] - P0[1]) / base)
        ey = (-ex[1], ex[0])
        cand = [(P0[0] + ex[0] * x + ey[0] * s * y, P0[1] + ex[1] * x + ey[1] * s * y)
                for s in (1.0, -1.0)]
        prev = flat[-1]
        cen = (sum(q[0] for q in prev) / 3.0, sum(q[1] for q in prev) / 3.0)
        pick = max(cand, key=lambda q: math.dist(q, cen))
        placed[n0] = pick
        flat.append([placed[tri[0]], placed[tri[1]], placed[tri[2]]])
        prev_tri = tri
    return flat


def blank_size(u: Unit) -> Tuple[float, float]:
    """Bounding box of the flat pattern, m, long side first."""
    pts = [q for tri in unroll(u) for q in tri]
    w = max(q[0] for q in pts) - min(q[0] for q in pts)
    h = max(q[1] for q in pts) - min(q[1] for q in pts)
    return (max(w, h), min(w, h))


# ---------------------------------------------------------------------------
# The facade

def field(bay: int, floor: int, mode: str = "vertical") -> float:
    """Field value at a unit position. ASSUMPTION for session 1: a plain
    vertical gradient, f = 0 at the bottom, f = 1 at the top. The paper does
    not state the field; nothing measured here depends on the choice except
    the facade totals."""
    if mode == "vertical":
        return floor / (FLOORS * 2 - 1)     # 8 unit rows, 0..7
    raise ValueError(mode)


def unit_positions() -> List[Tuple[int, int]]:
    """The 88 unit positions as (column, row), 12 columns x 8 rows, less the
    8 at the entrance: rows 0-1, columns 4-7 (the 6 x 3 m opening)."""
    out = []
    for row in range(FLOORS * 2):
        for col in range(BAYS * 2):
            if row < 2 and 4 <= col < 8:
                continue
            out.append((col, row))
    return out


def facade(dmax: float = DMAX_DEFAULT, snapped: bool = False) -> List[Unit]:
    """All 88 units. snapped=True quantises f to the five families."""
    levels = [0.0, 0.25, 0.5, 0.75, 1.0]
    out = []
    for col, row in unit_positions():
        f = row / (FLOORS * 2 - 1)
        if snapped:
            f = min(levels, key=lambda L: abs(L - f))
        out.append(unit(f, dmax))
    return out


# ---------------------------------------------------------------------------

def sweep(dmax: float = DMAX_DEFAULT, n: int = 101) -> List[dict]:
    rows = []
    for i in range(n):
        f = i / (n - 1)
        u = unit(f, dmax)
        long_side, short_side, blank_area = piece_blank(u)
        rows.append({
            "f": round(f, 4),
            "depth_mm": round(u.d * 1000, 1),
            "aperture_r_mm": round(u.r * 1000, 1),
            "plan_gap_mm": round(plan_gap(u) * 1000, 1),
            "flange_span_mm": round(flange_span(u) * 1000, 1),
            "rake_deg": round(rake(u), 2),
            "fold_deg": round(piece_fold_angle(u), 2),
            "off_flat_deg": round(180.0 - piece_fold_angle(u), 2),
            "metal_area_m2": round(metal_area(u), 4),
            "area_factor": round(area_factor(u), 4),
            "porosity": round(porosity(u), 4),
            "blank_long_mm": round(long_side * 1000, 1),
            "blank_short_mm": round(short_side * 1000, 1),
            "blank_area_m2": round(blank_area, 4),
        })
    return rows


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)

    rows = sweep()
    lo, hi = unit(0.0), unit(1.0)
    free = facade(snapped=False)
    snap = facade(snapped=True)

    # The paper's own coordinate table sits at r = 0.50, not at f = 0.
    table_f = f_of_aperture(0.50)

    # What the two readings of the face list cost.
    pin = unit(0.0, pinwheel=True)

    results = {
        "brief": {
            "facade_m": [18, 12],
            "bays": BAYS, "floors": FLOORS,
            "units": N_UNITS, "faces": N_UNITS * 8,
            "unit_m": [2 * HALF, 2 * HALF],
            "d_min_m": D_MIN, "d_max_m": DMAX_DEFAULT,
            "field_assumption": "vertical gradient, f = 0 at grade, f = 1 at parapet",
            "coordinate_table_f": round(table_f, 4),
        },
        "face_list_reading": {
            "aligned_tiles": tiles(unit(0.0)),
            "aligned_area_factor": round(area_factor(unit(0.0)), 3),
            "pinwheel_tiles": tiles(pin),
            "pinwheel_area_factor": round(area_factor(pin), 3),
            "aligned_cover": plan_cover(unit(0.0)),
            "pinwheel_cover": plan_cover(pin),
            "note": ("B_k on the axis of its own frame edge tiles the band. "
                     "B_k swept to the next edge blocks the aperture and "
                     "double-covers the band: not a chiral part, an invalid "
                     "surface."),
        },
        "extremes": {
            "shallow": rows[0],
            "deep": rows[-1],
            "flange_span_ratio": round(flange_span(hi) / flange_span(lo), 2),
            "plan_gap_ratio": round(plan_gap(hi) / plan_gap(lo), 2),
            "metal_area_ratio": round(metal_area(hi) / metal_area(lo), 2),
            "fold_angle_range_deg": [rows[0]["fold_deg"], rows[-1]["fold_deg"]],
        },
        "facade_totals": {
            "free_metal_m2": round(sum(metal_area(u) for u in free), 1),
            "snapped_metal_m2": round(sum(metal_area(u) for u in snap), 1),
            "glazed_m2": 18 * 12,
            "pieces": N_UNITS * 4,
            "free_blanks_over_sheet_width": sum(
                1 for u in free if piece_blank(u)[1] > SHEET_W),
            "units_below_crease_threshold": sum(
                1 for u in free if (180.0 - piece_fold_angle(u)) < CREASE_READS),
            "free_families": len({round(u.f, 6) for u in free}),
            "snapped_families": len({round(u.f, 6) for u in snap}),
        },
        "sweep": rows,
    }
    with open(os.path.join(root, "results.json"), "w") as fh:
        json.dump(results, fh, indent=2)

    e, t = results["extremes"], results["facade_totals"]
    print(f"units {N_UNITS}, faces {N_UNITS * 8}, pieces {t['pieces']}")
    print()
    print(f"{'':10} {'gap':>9} {'true span':>10} {'fold':>8} {'off flat':>9} "
          f"{'blank':>16}")
    for tag, r in (("f = 0", rows[0]), ("f = 1", rows[-1])):
        print(f"{tag:10} {r['plan_gap_mm']:>7.1f}mm {r['flange_span_mm']:>8.1f}mm "
              f"{r['fold_deg']:>6.1f}d {r['off_flat_deg']:>7.1f}d "
              f"{r['blank_long_mm']:>7.0f} x {r['blank_short_mm']:<6.0f}mm")
    print()
    print(f"true span ratio  {e['flange_span_ratio']}:1   "
          f"metal area ratio {e['metal_area_ratio']}:1")
    print(f"fold angle runs  {e['fold_angle_range_deg'][0]} to "
          f"{e['fold_angle_range_deg'][1]} degrees")
    print(f"facade metal     {t['free_metal_m2']} m2 free, "
          f"{t['snapped_metal_m2']} m2 snapped, over {t['glazed_m2']} m2 of glass")
    print(f"coordinate table sits at f = {results['brief']['coordinate_table_f']}, "
          f"not f = 0")
    print(f"face list, aligned reading:  area factor "
          f"{results['face_list_reading']['aligned_area_factor']}, "
          f"tiles = {results['face_list_reading']['aligned_tiles']}")
    print(f"face list, pinwheel reading: area factor "
          f"{results['face_list_reading']['pinwheel_area_factor']}, "
          f"tiles = {results['face_list_reading']['pinwheel_tiles']}")


if __name__ == "__main__":
    main()
