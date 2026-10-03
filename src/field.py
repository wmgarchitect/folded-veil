"""field.py - where the gradient field comes from. Session 2.

The paper never states the field. This asks whether it can be derived at all,
and what it costs to rationalise once it exists.

Three candidate fields over the 88 units:

  vertical   f rises with height. One value per row. The session 1 assumption.
  solar      f from annual irradiation on the west elevation, with and
             without a neighbouring building in the model.
  radial     f from distance to the entrance. A design decision, not a
             derived one: the veil opens where people arrive.

Sun model is skin-logic's, stated plainly: ASHRAE clear sky, twelve design
days, hourly, month-length weighted. Not TMY. It sizes conservatively and
every field here is computed under the same assumption.

Run:  python3 src/field.py      (writes field_results.json)
"""

from __future__ import annotations

import json
import math
import os
import sys
from typing import Dict, List, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import veil as v   # noqa: E402

# Istanbul, the Merdivenkoy fix skin-logic works from.
LAT = 40.99329222222222
LON = 29.064626666666665
TZ = 3.0
ALBEDO = 0.20

SURFACE_AZIMUTH = 270.0          # a west elevation

# The facade in world coordinates: +X east, +Y north, +Z up.
# The glass sits in the plane X = 0 and faces west, so its normal is -X.
FACADE_W, FACADE_H = 18.0, 12.0
UNIT = 1.5

# One neighbour across the street, to show what a site does to the field.
# (xmin, xmax, ymin, ymax, zmin, zmax) in metres.
NEIGHBOUR = (-27.0, -15.0, -26.0, 3.0, 0.0, 21.0)


# ---------------------------------------------------------------------------
# Sun, lifted from skin-logic/src/skin.py, unchanged

_A = [1230, 1215, 1186, 1136, 1104, 1088, 1085, 1107, 1152, 1193, 1221, 1234]
_B = [0.142, 0.144, 0.156, 0.180, 0.196, 0.205,
      0.207, 0.201, 0.177, 0.160, 0.149, 0.142]
_C = [0.058, 0.060, 0.071, 0.097, 0.121, 0.134,
      0.136, 0.122, 0.092, 0.073, 0.063, 0.057]
DESIGN_DAYS = [21, 52, 80, 111, 141, 172, 202, 233, 264, 294, 325, 355]
DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def declination(n: int) -> float:
    return math.radians(23.45) * math.sin(math.radians(360.0 * (284 + n) / 365.0))


def equation_of_time(n: int) -> float:
    b = math.radians(360.0 * (n - 81) / 364.0)
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def sun_alt_az(n: int, local_hour: float) -> Tuple[float, float]:
    """Altitude and azimuth in degrees. Azimuth clockwise from north."""
    solar_time = local_hour + (4.0 * (LON - 15.0 * TZ) + equation_of_time(n)) / 60.0
    ha = math.radians(15.0 * (solar_time - 12.0))
    d, lat = declination(n), math.radians(LAT)
    sin_alt = math.sin(lat) * math.sin(d) + math.cos(lat) * math.cos(d) * math.cos(ha)
    sin_alt = max(-1.0, min(1.0, sin_alt))
    alt = math.asin(sin_alt)
    cos_az = ((math.sin(d) * math.cos(lat) - math.cos(d) * math.sin(lat) * math.cos(ha))
              / max(1e-9, math.cos(alt)))
    az = math.acos(max(-1.0, min(1.0, cos_az)))
    if ha > 0:
        az = 2 * math.pi - az
    return math.degrees(alt), math.degrees(az)


def direct_normal(m: int, alt_deg: float) -> float:
    if alt_deg <= 1.0:
        return 0.0
    return _A[m] * math.exp(-_B[m] / math.sin(math.radians(alt_deg)))


def diffuse_on_vertical(m: int, dni: float) -> float:
    return _C[m] * dni * 0.5


def ground_reflected_on_vertical(m: int, dni: float, alt_deg: float) -> float:
    horiz = dni * math.sin(math.radians(alt_deg)) + _C[m] * dni
    return ALBEDO * horiz * 0.5


class SunStep:
    __slots__ = ("m", "alt", "az", "dni", "hours", "vec")

    def __init__(self, m, alt, az, dni, hours):
        self.m, self.alt, self.az, self.dni, self.hours = m, alt, az, dni, hours
        a, z = math.radians(alt), math.radians(az)
        self.vec = (math.cos(a) * math.sin(z), math.cos(a) * math.cos(z), math.sin(a))


def sun_sample() -> List[SunStep]:
    out = []
    for m, n in enumerate(DESIGN_DAYS):
        for hour in range(24):
            alt, az = sun_alt_az(n, hour + 0.5)
            if alt <= 1.0:
                continue
            dni = direct_normal(m, alt)
            if dni <= 0.0:
                continue
            out.append(SunStep(m, alt, az, dni, float(DAYS_IN_MONTH[m])))
    return out


# ---------------------------------------------------------------------------
# Shading by one rectangular block

def ray_hits_box(origin, d, box) -> bool:
    """Slab test. True if the ray from origin along d meets the box ahead."""
    xmin, xmax, ymin, ymax, zmin, zmax = box
    lo, hi = 0.0, float("inf")
    for i, (a, b) in enumerate(((xmin, xmax), (ymin, ymax), (zmin, zmax))):
        if abs(d[i]) < 1e-12:
            if origin[i] < a or origin[i] > b:
                return False
        else:
            t1 = (a - origin[i]) / d[i]
            t2 = (b - origin[i]) / d[i]
            if t1 > t2:
                t1, t2 = t2, t1
            lo = max(lo, t1)
            hi = min(hi, t2)
            if lo > hi:
                return False
    return hi > 1e-6


# ---------------------------------------------------------------------------
# The 88 unit centres

def unit_centres() -> List[Tuple[int, int, float, float]]:
    """(col, row, y, z) for each unit, in world coordinates."""
    out = []
    for col, row in v.unit_positions():
        y = -FACADE_W / 2 + UNIT / 2 + col * UNIT
        z = UNIT / 2 + row * UNIT
        out.append((col, row, y, z))
    return out


# ---------------------------------------------------------------------------
# The fields

def solar_field(with_neighbour: bool) -> List[float]:
    """Annual irradiation on each unit, kWh/m2/yr."""
    sun = sun_sample()
    box = NEIGHBOUR if with_neighbour else None
    out = []
    for _, _, y, z in unit_centres():
        p = (0.0, y, z)
        total = 0.0
        for s in sun:
            cos_inc = -s.vec[0]          # facade normal is -X
            sky = diffuse_on_vertical(s.m, s.dni) + \
                ground_reflected_on_vertical(s.m, s.dni, s.alt)
            beam = 0.0
            if cos_inc > 0.0:
                if box is None or not ray_hits_box(p, s.vec, box):
                    beam = s.dni * cos_inc
            total += (beam + sky) * s.hours
        out.append(total / 1000.0)
    return out


def vertical_field() -> List[float]:
    rows = v.FLOORS * 2 - 1
    return [row / rows for _, row, _, _ in unit_centres()]


def radial_field() -> List[float]:
    """Distance from the entrance, normalised. The veil opens where people
    arrive and closes as it climbs away. A design decision, stated as one."""
    ey, ez = 0.0, 0.0            # centre of the 6 x 3 m entrance, at grade
    ds = [math.hypot(y - ey, z - ez) for _, _, y, z in unit_centres()]
    lo, hi = min(ds), max(ds)
    return [(d - lo) / (hi - lo) for d in ds]


def normalise(vals: Sequence[float]) -> List[float]:
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-12:
        return [0.0 for _ in vals]
    return [(x - lo) / (hi - lo) for x in vals]


# ---------------------------------------------------------------------------
# Rationalisation. Lifted verbatim from skin-logic/src/schemes.py, which chose
# an exact 1D dynamic programming partition over k-means because k-means made
# the sweep curve non-monotone. Groups are set to their deepest member.

def rationalise(depths: Sequence[float], k: int) -> List[float]:
    vals = sorted(set(depths))
    if k >= len(vals):
        return list(depths)
    counts = {x: 0 for x in vals}
    for d in depths:
        counts[d] += 1
    n = len(vals)
    cost = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i, n):
            cost[i][j] = sum((vals[j] - vals[m]) * counts[vals[m]]
                             for m in range(i, j + 1))
    INF = float("inf")
    best = [[INF] * (k + 1) for _ in range(n + 1)]
    cut = [[0] * (k + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    for j in range(1, n + 1):
        for g in range(1, min(k, j) + 1):
            for i in range(g - 1, j):
                if best[i][g - 1] == INF:
                    continue
                c = best[i][g - 1] + cost[i][j - 1]
                if c < best[j][g]:
                    best[j][g] = c
                    cut[j][g] = i
    tops = {}
    j, g = n, k
    while g > 0:
        i = cut[j][g]
        top = vals[j - 1]
        for m in range(i, j):
            tops[vals[m]] = top
        j, g = i, g - 1
    return [tops[d] for d in depths]


# ---------------------------------------------------------------------------

def depths_from(fs: Sequence[float], dmax: float = v.DMAX_DEFAULT) -> List[float]:
    return [round(v.depth(f, dmax), 6) for f in fs]


def describe(name: str, fs: Sequence[float], dmax: float = v.DMAX_DEFAULT) -> dict:
    d = depths_from(fs, dmax)
    metal = sum(v.metal_area(v.unit(f, dmax)) for f in fs)
    return {
        "name": name,
        "families": len(set(d)),
        "depth_min_mm": round(min(d) * 1000, 1),
        "depth_max_mm": round(max(d) * 1000, 1),
        "spread_mm": round((max(d) - min(d)) * 1000, 1),
        "metal_m2": round(metal, 1),
    }


def rationalised(name: str, fs: Sequence[float], k: int,
                 dmax: float = v.DMAX_DEFAULT) -> dict:
    free = depths_from(fs, dmax)
    rat = rationalise(free, k)
    dev = [(r - f) * 1000 for r, f in zip(rat, free)]
    rms = math.sqrt(sum(x * x for x in dev) / len(dev))
    fs_r = [(d - v.D_MIN) / (dmax - v.D_MIN) for d in rat]
    metal_free = sum(v.metal_area(v.unit(f, dmax)) for f in fs)
    metal_rat = sum(v.metal_area(v.unit(f, dmax)) for f in fs_r)
    return {
        "name": name,
        "k": k,
        "families_free": len(set(free)),
        "families_after": len(set(rat)),
        "levels_mm": sorted(round(x * 1000, 1) for x in set(rat)),
        "rms_deviation_mm": round(rms, 1),
        "max_deviation_mm": round(max(dev), 1),
        "units_changed": sum(1 for x in dev if abs(x) > 1e-6),
        "extra_metal_m2": round(metal_rat - metal_free, 1),
        "extra_metal_pct": round(100 * (metal_rat - metal_free) / metal_free, 1),
    }


def uniform_snap(fs: Sequence[float], dmax: float = v.DMAX_DEFAULT) -> dict:
    """The paper's own rationalisation: f snapped to {0, .25, .5, .75, 1}, five
    evenly spaced families. Rounded up, same rule as the partition, so the two
    are compared on equal terms."""
    levels = [0.0, 0.25, 0.5, 0.75, 1.0]
    free = depths_from(fs, dmax)
    up = []
    for f in fs:
        cand = [L for L in levels if L >= f - 1e-12]
        up.append(round(v.depth(cand[0] if cand else 1.0, dmax), 6))
    dev = [(r - f) * 1000 for r, f in zip(up, free)]
    rms = math.sqrt(sum(x * x for x in dev) / len(dev))
    fs_r = [(d - v.D_MIN) / (dmax - v.D_MIN) for d in up]
    metal_free = sum(v.metal_area(v.unit(f, dmax)) for f in fs)
    metal_up = sum(v.metal_area(v.unit(f, dmax)) for f in fs_r)
    return {
        "name": "uniform fifths, the paper's own",
        "families_after": len(set(up)),
        "levels_mm": sorted(round(x * 1000, 1) for x in set(up)),
        "rms_deviation_mm": round(rms, 1),
        "max_deviation_mm": round(max(dev), 1),
        "extra_metal_pct": round(100 * (metal_up - metal_free) / metal_free, 1),
    }


def main() -> None:
    centres = unit_centres()
    vert = vertical_field()
    bare = solar_field(False)
    site = solar_field(True)
    rad = radial_field()

    bare_n, site_n = normalise(bare), normalise(site)

    results = {
        "model_limits": [
            "ASHRAE clear sky, twelve design days, hourly, month-length weighted. Not TMY.",
            "One rectangular neighbour, flat topped, 12 x 29 m in plan and 21 m tall, "
            "15 m west of the glass. A stand-in for a street, not a surveyed site.",
            "Irradiation is on the glass plane. The veil's own self-shading is not in "
            "this number.",
        ],
        "solar": {
            "bare_min": round(min(bare), 1),
            "bare_max": round(max(bare), 1),
            "bare_spread_pct": round(100 * (max(bare) - min(bare)) / max(bare), 2),
            "bare_distinct_values": len(set(round(x, 1) for x in bare)),
            "site_min": round(min(site), 1),
            "site_max": round(max(site), 1),
            "site_spread_pct": round(100 * (max(site) - min(site)) / max(site), 2),
            "site_distinct_values": len(set(round(x, 1) for x in site)),
            "units_shaded": sum(1 for a, b in zip(bare, site) if b < a - 0.5),
        },
        "fields": [
            describe("vertical, 1D", vert),
            describe("solar, bare elevation", bare_n),
            describe("solar, one neighbour", site_n),
            describe("radial from the entrance", rad),
        ],
        "rationalisation": [
            rationalised("vertical, 1D", vert, 5),
            rationalised("solar, one neighbour", site_n, 5),
            rationalised("radial from the entrance", rad, 5),
        ],
        "k_curve": [
            {"k": k, **{kk: vv for kk, vv in rationalised("radial", rad, k).items()
                        if kk in ("rms_deviation_mm", "families_after", "extra_metal_pct")}}
            for k in range(1, 13)
        ],
        "uniform_vs_partition": {
            "uniform": uniform_snap(rad),
            "partition": rationalised("radial from the entrance", rad, 5),
        },
        "chosen_field": "radial from the entrance",
        "per_unit": [
            {"col": c, "row": r, "vertical": round(vert[i], 4),
             "solar_bare_kwh": round(bare[i], 1), "solar_site_kwh": round(site[i], 1),
             "radial": round(rad[i], 4)}
            for i, (c, r, _, _) in enumerate(centres)
        ],
    }
    with open(os.path.join(ROOT, "field_results.json"), "w") as fh:
        json.dump(results, fh, indent=2)

    s = results["solar"]
    print("SOLAR ON THE GLASS, kWh/m2/yr")
    print("  bare elevation   %.1f to %.1f   spread %.2f%%   %d distinct values over 88 units"
          % (s["bare_min"], s["bare_max"], s["bare_spread_pct"], s["bare_distinct_values"]))
    print("  one neighbour    %.1f to %.1f   spread %.2f%%   %d distinct values, %d units shaded"
          % (s["site_min"], s["site_max"], s["site_spread_pct"],
             s["site_distinct_values"], s["units_shaded"]))
    print()
    print("FIELDS")
    for f in results["fields"]:
        print("  %-28s families %3d   depth %6.1f to %6.1f mm   metal %6.1f m2"
              % (f["name"], f["families"], f["depth_min_mm"], f["depth_max_mm"], f["metal_m2"]))
    print()
    print("SNAPPED TO FIVE FAMILIES, exact 1D partition")
    for r in results["rationalisation"]:
        print("  %-28s %3d -> %d   rms dev %5.1f mm   max %5.1f mm   extra metal %+.1f%%"
              % (r["name"], r["families_free"], r["families_after"],
                 r["rms_deviation_mm"], r["max_deviation_mm"], r["extra_metal_pct"]))
    print()
    print("FIVE FAMILIES, CHOSEN TWO WAYS, on the radial field")
    uv = results["uniform_vs_partition"]
    for r in (uv["uniform"], uv["partition"]):
        print("  %-28s rms dev %5.1f mm   max %5.1f mm   extra metal %+.1f%%   levels %s"
              % (r["name"], r["rms_deviation_mm"], r["max_deviation_mm"],
                 r["extra_metal_pct"], r["levels_mm"]))


if __name__ == "__main__":
    main()
