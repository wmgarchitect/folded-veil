"""anim.py - session 4: the Folded Veil in motion.

Two sequences, 60 frames each, 1080 x 1920, vertical. The facade uses the
radial field decided in session 2. Every number on a frame is measured from
veil.py for that frame, nothing is typed in.

  sweep  (4a)  the deepest fold runs 200 -> 900 mm, light fixed.
               Chart: spread of bend angles across the veil.
  light  (4b)  the veil fixed at 900 mm, a low sun rakes across it from
               70 deg left of the facade normal to 70 deg right.
               Chart: share of metal area turned towards the sun.

    python3 src/anim.py sweep            # all 60 sweep frames
    python3 src/anim.py light 0 30       # light frames 0..29 (short shells)

Writes media/anim/<seq>/<seq>_000.png ...
Lighting is Lambert shading with no cast shadows: it shows which faces turn
to the sun, not where the veil shades itself. Stated, not hidden.
"""

from __future__ import annotations

import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import veil as v      # noqa: E402
import field as fd    # noqa: E402

N_FRAMES = 60
D_LO, D_HI = 0.20, 0.90
SUN_ALT = 20.0                       # deg, a low raking sun
AZ_LO, AZ_HI = -70.0, 70.0           # deg from the facade normal

BG = "#12100E"
FG = "#EFE9E1"
MUTED = "#8A8178"
AMBER = "#E0A03C"
GLASS = "#1C2A30"
W = fd.FACADE_W / 2

CENTRES = fd.unit_centres()
FIELD = fd.radial_field()


# ---------------------------------------------------------------------------
# small helpers

def ease(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * t)


def normalised(vec):
    n = math.sqrt(sum(c * c for c in vec))
    return tuple(c / n for c in vec)


def sun(az_deg: float, alt_deg: float = SUN_ALT):
    """Unit vector towards the sun. Facade normal is -X, Y across, Z up.
    az 0 = sun straight in front of the facade."""
    a, h = math.radians(az_deg), math.radians(alt_deg)
    return (-math.cos(h) * math.cos(a), math.cos(h) * math.sin(a), math.sin(h))


FIXED_LIGHT = normalised((-0.55, -0.45, 0.70))   # the 4a key light


def world(p, yc, zc):
    """Unit local (x across, y out, z up) -> world (X out, Y across, Z up)."""
    return (p[1], yc + p[0], zc + p[2])


def outward_normal(tri):
    a, b, c = tri
    n = v.cross(v.sub(b, a), v.sub(c, a))
    ln = v.norm(n)
    if ln < 1e-12:
        return None
    n = tuple(k / ln for k in n)
    return tuple(-k for k in n) if n[0] > 0 else n


def metal(s: float):
    base = (0.937, 0.914, 0.882)
    return tuple(c * s for c in base) + (1.0,)


def facade_tris(dmax: float):
    units = [v.unit(f, dmax) for f in FIELD]
    tris = []
    for u, (_, _, yc, zc) in zip(units, CENTRES):
        pts = [world(p, yc, zc) for p in u.points]
        tris += [[pts[k] for k in fa] for fa in u.faces]
    return units, tris


def bend_range(dmax: float):
    b = [v.piece_fold_angle(v.unit(f, dmax)) for f in FIELD]
    return min(b), max(b)


def sunlit_share(tris, light) -> float:
    """Share of metal area whose outward face turns towards the sun."""
    tot = lit = 0.0
    for t in tris:
        a = v.tri_area(*t)
        n = outward_normal(t)
        tot += a
        if n is not None and v.dot(n, light) > 0:
            lit += a
    return lit / tot


# ---------------------------------------------------------------------------
# the page

def page(tris, light, headline, chart, rows, path):
    fig = plt.figure(figsize=(10.8, 19.2), dpi=100)
    fig.patch.set_facecolor(BG)

    ax = fig.add_axes([-0.22, 0.33, 1.44, 0.52], projection="3d")
    ax.set_facecolor(BG)
    cols = []
    for t in tris:
        n = outward_normal(t)
        lam = 0.5 if n is None else max(0.0, v.dot(n, light))
        cols.append(metal(0.22 + 0.78 * lam))
    glass = [[(0.03, -W, 0), (0.03, W, 0), (0.03, W, 12), (0.03, -W, 12)]]
    ax.add_collection3d(Poly3DCollection(glass, facecolors=GLASS, edgecolors="none"))
    ax.add_collection3d(Poly3DCollection(tris, facecolors=cols,
                                         edgecolors=(0, 0, 0, 0.25), linewidths=0.15))
    ax.set_xlim(-4.5, 4.5)
    ax.set_ylim(-W - 0.3, W + 0.3)
    ax.set_zlim(-1.5, 13.5)
    ax.set_box_aspect((9, 18.6, 15), zoom=1.45)
    ax.view_init(elev=16, azim=-138)
    ax.set_axis_off()

    fig.text(0.07, 0.945, "FOLDED VEIL", color=MUTED, fontsize=20, fontweight="bold")
    fig.text(0.07, 0.915, "one gradient, 88 units, 704 faces", color=MUTED, fontsize=16)
    fig.text(0.07, 0.855, headline, color=AMBER, fontsize=40, fontweight="bold")

    cx = fig.add_axes([0.10, 0.215, 0.83, 0.10])
    cx.set_facecolor(BG)
    for sp in ("top", "right"):
        cx.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        cx.spines[sp].set_color("#3A342E")
    cx.tick_params(colors=MUTED, labelsize=12)
    title = chart(cx)
    fig.text(0.07, 0.335, title, color=MUTED, fontsize=15)

    for k, (lab, val) in enumerate(rows):
        yy = 0.150 - k * 0.038
        fig.text(0.07, yy, lab, color=MUTED, fontsize=20)
        fig.text(0.93, yy, val, color=FG, fontsize=24, fontweight="bold", ha="right")
    fig.text(0.07, 0.035, "archicoder.com   ·   measured in veil.py, no Rhino",
             color=MUTED, fontsize=14)

    fig.savefig(path, dpi=100, facecolor=BG)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# 4a: the fold sweep

TRACK_D = [D_LO + (D_HI - D_LO) * k / 140 for k in range(141)]
TRACK_B = [bend_range(d) for d in TRACK_D]


def sweep_frame(i: int, out: str) -> str:
    dmax = D_LO + (D_HI - D_LO) * ease(i / (N_FRAMES - 1))
    units, tris = facade_tris(dmax)
    spans = [v.flange_span(u) * 1000 for u in units]
    lo, hi = bend_range(dmax)
    area = sum(v.metal_area(u) for u in units)

    def chart(cx):
        xs = [d * 1000 for d in TRACK_D]
        cx.fill_between(xs, [b[0] for b in TRACK_B], [b[1] for b in TRACK_B],
                        color=AMBER, alpha=0.18, linewidth=0)
        cx.plot(xs, [b[0] for b in TRACK_B], color=AMBER, lw=1.2, alpha=0.6)
        cx.plot(xs, [b[1] for b in TRACK_B], color=AMBER, lw=1.2, alpha=0.6)
        cx.plot([dmax * 1000] * 2, [lo, hi], color=AMBER, lw=3.5)
        cx.axvline(dmax * 1000, color=FG, lw=0.6, alpha=0.4)
        cx.set_xlim(D_LO * 1000, D_HI * 1000)
        cx.set_ylim(130, 170)
        cx.set_xlabel("deepest fold, mm", color=MUTED, fontsize=12)
        cx.set_ylabel("bend, deg", color=MUTED, fontsize=12)
        return "spread of bend angles across the veil"

    rows = [
        ("flange span", f"{min(spans):.0f} - {max(spans):.0f} mm"),
        ("bend angle", f"{lo:.1f} - {hi:.1f} deg  ({hi - lo:.1f})"),
        ("metal, whole veil", f"{area:.0f} m2"),
    ]
    return page(tris, FIXED_LIGHT, f"deepest fold   {dmax*1000:4.0f} mm", chart, rows,
                os.path.join(out, f"sweep_{i:03d}.png"))


# ---------------------------------------------------------------------------
# 4b: the raking light

_, LIGHT_TRIS = facade_tris(D_HI)
TRACK_AZ = [AZ_LO + (AZ_HI - AZ_LO) * k / 140 for k in range(141)]
TRACK_LIT = [sunlit_share(LIGHT_TRIS, sun(a)) for a in TRACK_AZ]


def light_frame(i: int, out: str) -> str:
    az = AZ_LO + (AZ_HI - AZ_LO) * ease(i / (N_FRAMES - 1))
    L = sun(az)
    share = sunlit_share(LIGHT_TRIS, L)
    side = "left" if az < -0.5 else ("right" if az > 0.5 else "front")

    def chart(cx):
        cx.plot(TRACK_AZ, [s * 100 for s in TRACK_LIT], color=AMBER, lw=1.6, alpha=0.7)
        cx.plot([az], [share * 100], "o", color=AMBER, ms=11)
        cx.axvline(az, color=FG, lw=0.6, alpha=0.4)
        cx.set_xlim(AZ_LO, AZ_HI)
        cx.set_ylim(0, 100)
        cx.set_xlabel("sun, deg from the facade normal", color=MUTED, fontsize=12)
        cx.set_ylabel("% of metal", color=MUTED, fontsize=12)
        return "metal turned towards a 20 deg sun"

    rows = [
        ("sun", f"{abs(az):.0f} deg {side}, 20 deg up"),
        ("metal facing the sun", f"{share*100:.0f} %"),
        ("deepest fold", f"{D_HI*1000:.0f} mm"),
    ]
    return page(LIGHT_TRIS, L, "raking light", chart, rows,
                os.path.join(out, f"light_{i:03d}.png"))


def main() -> None:
    seq = sys.argv[1] if len(sys.argv) > 1 else "sweep"
    a = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    b = int(sys.argv[3]) if len(sys.argv) > 3 else N_FRAMES
    out = os.path.join(ROOT, "media", "anim", seq)
    os.makedirs(out, exist_ok=True)
    fn = {"sweep": sweep_frame, "light": light_frame}[seq]
    for i in range(a, b):
        print(fn(i, out))


if __name__ == "__main__":
    main()
