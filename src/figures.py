"""figures.py - the session 1 figure, rendered from results.json.

Rhino is not involved and is not installed. Run veil.py first.

    python3 src/veil.py
    python3 src/figures.py
"""

from __future__ import annotations

import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt              # noqa: E402
from matplotlib.patches import Polygon, Arc  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
import numpy as np                           # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import veil as v   # noqa: E402

MEDIA = os.path.join(ROOT, "media")
os.makedirs(MEDIA, exist_ok=True)

# Archicoder brand: dark ground, amber accent.
BG = "#12100E"
FG = "#EFE9E1"
MUTED = "#8A8178"
AMBER = "#E0A03C"
COOL = "#4E7C8A"
GRID = "#2A2622"

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": FG, "axes.labelcolor": FG, "axes.edgecolor": GRID,
    "xtick.color": MUTED, "ytick.color": MUTED, "grid.color": GRID,
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.titlesize": 12, "axes.titleweight": "bold",
})

R = json.load(open(os.path.join(ROOT, "results.json")))


def plan(ax, u: v.Unit, label: str) -> None:
    """The unit seen square on. Frame square, fold lines, diamond aperture,
    and the pinch between the aperture vertex and the frame edge."""
    h, r = v.HALF, u.r
    A = [(h, h), (-h, h), (-h, -h), (h, -h)]
    B = [(p[0], p[2]) for p in u.B]

    # the metal band, face by face
    for a, b, c in u.faces:
        pts = [(u.points[k][0], u.points[k][2]) for k in (a, b, c)]
        ax.add_patch(Polygon(pts, closed=True, facecolor="#272119",
                             edgecolor="#4A4036", linewidth=0.9, zorder=1))
    # aperture
    ax.add_patch(Polygon(B, closed=True, facecolor=BG, edgecolor=COOL,
                         linewidth=1.6, zorder=2))
    # frame
    ax.add_patch(Polygon(A, closed=True, facecolor="none", edgecolor=MUTED,
                         linewidth=1.6, zorder=3))

    # the pinch: aperture vertex to the frame edge it points at
    gap = v.plan_gap(u)
    ax.plot([0, 0], [r, h], color=AMBER, linewidth=3.0, zorder=4,
            solid_capstyle="butt")
    ax.annotate(f"{gap * 1000:.1f} mm", xy=(0.01, (r + h) / 2),
                xytext=(0.40, h + 0.16),
                color=AMBER, fontsize=12, fontweight="bold", ha="left",
                arrowprops=dict(arrowstyle="-", color=AMBER, linewidth=0.9,
                                shrinkA=2, shrinkB=1))
    ax.text(0.40, h + 0.05, "in plan", color=MUTED, fontsize=9, ha="left")

    ax.set_title(label, color=FG, pad=14, loc="left")
    ax.set_xlim(-1.02, 1.02)
    ax.set_ylim(-0.95, 1.10)
    ax.set_aspect("equal")
    ax.axis("off")


def section(ax, u: v.Unit) -> None:
    """Cut through the aperture on the vertical axis. Same scale as the plan
    above it, and the same scale in both columns."""
    h, r, d = v.HALF, u.r, u.d
    span = v.flange_span(u)

    ax.plot([-1.0, 1.0], [0, 0], color=GRID, linewidth=1.0,
            linestyle=(0, (6, 4)), zorder=1)
    ax.text(-0.98, 0.045, "glass line", color=MUTED, fontsize=8.5)

    for s in (1, -1):
        ax.plot([s * h, s * r], [0, -d], color=AMBER, linewidth=3.2,
                solid_capstyle="round", zorder=4)
    ax.plot([-r, r], [-d, -d], color=COOL, linewidth=1.4,
            linestyle=(0, (2, 3)), zorder=3)
    ax.text(0, -d + 0.045, "aperture", color=COOL, fontsize=8.5, ha="center")

    # depth dimension
    ax.annotate("", xy=(h + 0.13, 0), xytext=(h + 0.13, -d),
                arrowprops=dict(arrowstyle="<->", color=MUTED, linewidth=0.9))
    ax.text(h + 0.18, -d / 2, f"{d * 1000:.0f} mm\ndeep", color=MUTED,
            fontsize=9, va="center")

    # true span
    mx, my = -(h + r) / 2, -d / 2
    ax.annotate(f"{span * 1000:.0f} mm true", xy=(mx, my),
                xytext=(mx - 0.22, my - 0.34),
                color=AMBER, fontsize=12.5, fontweight="bold", ha="center",
                arrowprops=dict(arrowstyle="-", color=AMBER, linewidth=0.9,
                                shrinkA=3, shrinkB=3))

    # rake
    rake = v.rake(u)
    ax.add_patch(Arc((h, 0), 0.30, 0.30, angle=0, theta1=180 - rake, theta2=180,
                     color=MUTED, linewidth=0.9))
    ax.text(h - 0.20, -0.075, f"{rake:.0f}°", color=MUTED, fontsize=9)

    ax.set_xlim(-1.02, 1.02)
    ax.set_ylim(-1.05, 0.13)
    ax.set_aspect("equal")
    ax.axis("off")


def fold_strip(ax) -> None:
    """The thing that does not change while everything else does."""
    f = [r["f"] for r in R["sweep"]]
    a = [r["fold_deg"] for r in R["sweep"]]
    dep = [r["depth_mm"] for r in R["sweep"]]

    ax.plot(f, a, color=AMBER, linewidth=2.4, zorder=3)
    ax.fill_between(f, 90, a, color=AMBER, alpha=0.07, zorder=1)
    ax.set_ylim(90, 180)
    ax.set_xlim(0, 1)
    ax.set_yticks([90, 135, 180])
    ax.set_yticklabels(["90°", "135°", "180° flat"], fontsize=8.5)
    ax.set_xticks([0, 0.5, 1])
    ax.set_xticklabels(["f = 0", "", "f = 1"], fontsize=8.5)
    ax.grid(True, linewidth=0.6, alpha=0.5)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)

    ax2 = ax.twinx()
    ax2.plot(f, dep, color=COOL, linewidth=1.6, linestyle=(0, (4, 3)), zorder=2)
    ax2.set_ylim(0, 1080)
    ax2.set_yticks([])
    ax2.text(0.99, 905, "900 mm", color=COOL, fontsize=8.5, ha="right",
             va="bottom")
    for side in ("top", "right", "left", "bottom"):
        ax2.spines[side].set_visible(False)

    ax.set_title("bend angle, every piece on the facade", color=FG,
                 fontsize=10.5, loc="left", pad=8)
    ax.text(0.03, 150, "bend angle", color=AMBER, fontsize=9.5,
            fontweight="bold")
    ax.text(0.62, 108, "depth", color=COOL, fontsize=9.5, fontweight="bold")


def figure_one() -> str:
    lo, hi = v.unit(0.0), v.unit(1.0)
    fig = plt.figure(figsize=(13.2, 9.6), dpi=120)
    gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 0.72, 0.52],
                          hspace=0.12, wspace=0.06,
                          left=0.05, right=0.95, top=0.86, bottom=0.09)

    plan(fig.add_subplot(gs[0, 0]), lo,
         "SHALLOWEST UNIT   f = 0   120 mm deep")
    plan(fig.add_subplot(gs[0, 1]), hi,
         "DEEPEST UNIT   f = 1   900 mm deep")
    section(fig.add_subplot(gs[1, 0]), lo)
    section(fig.add_subplot(gs[1, 1]), hi)
    fold_strip(fig.add_subplot(gs[2, 0]))

    ax = fig.add_subplot(gs[2, 1])
    ax.axis("off")
    e = R["extremes"]
    lines = [
        ("6.5 : 1", "the true span of folded metal between frame edge and\n"
                    "aperture, across one facade: 155 mm to 1000 mm"),
        ("3.1°", "how much the bend angle moves over that same range.\n"
                      "136.6° at the shallow end, 139.7° at the deep end"),
    ]
    y = 0.88
    for big, small in lines:
        ax.text(0.0, y, big, color=AMBER, fontsize=26, fontweight="bold",
                va="top", transform=ax.transAxes)
        ax.text(0.23, y - 0.03, small, color=FG, fontsize=10.5, va="top",
                linespacing=1.5, transform=ax.transAxes)
        y -= 0.48
    ax.text(0.0, -0.10, "352 pieces. One bend angle. 352 different blanks.",
            color=MUTED, fontsize=10.5, style="italic", va="top",
            transform=ax.transAxes)

    fig.text(0.05, 0.945, "FACADE LOGIC 01  ·  FOLDED VEIL",
             color=MUTED, fontsize=11, fontweight="bold")
    fig.text(0.05, 0.905,
             "The gradient changes the depth by 7.5 times. It barely touches "
             "the bend.",
             color=FG, fontsize=17, fontweight="bold")
    fig.text(0.95, 0.945, "archicoder.com", color=MUTED, fontsize=10, ha="right")

    out = os.path.join(MEDIA, "FV-01-narrow-and-wide.png")
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out


if __name__ == "__main__":
    print(figure_one())


# ---------------------------------------------------------------------------
# Session 2: where the field comes from

import field as fl   # noqa: E402

F = json.load(open(os.path.join(ROOT, "field_results.json")))
DEPTHMAP = LinearSegmentedColormap.from_list(
    "depth", ["#1B2E33", COOL, "#8E7C46", AMBER, "#F2C87E"])


def elevation(ax, fs, title, sub, show_scale=False):
    """The 18 x 12 m elevation drawn as it is: every unit with its real
    aperture, toned by its fold depth."""
    centres = fl.unit_centres()
    dmax = v.DMAX_DEFAULT
    for (col, row, y, z), f in zip(centres, fs):
        d = v.depth(f, dmax)
        r = v.aperture(f)
        col_rgba = DEPTHMAP((d - v.D_MIN) / (dmax - v.D_MIN))
        ax.add_patch(Polygon(
            [(y - 0.75, z - 0.75), (y + 0.75, z - 0.75),
             (y + 0.75, z + 0.75), (y - 0.75, z + 0.75)],
            closed=True, facecolor=col_rgba, edgecolor=BG, linewidth=0.7, zorder=2))
        ax.add_patch(Polygon(
            [(y, z + r), (y + r, z), (y, z - r), (y - r, z)],
            closed=True, facecolor=BG, edgecolor="none", zorder=3))

    ax.add_patch(Polygon([(-3, 0), (3, 0), (3, 3), (-3, 3)], closed=True,
                         facecolor="#191510", edgecolor=GRID,
                         linewidth=0.9, zorder=1))
    ax.text(0, 1.4, "entrance", color=MUTED, fontsize=7.5, ha="center", zorder=4)

    ax.plot([-9.4, 9.4], [0, 0], color=MUTED, linewidth=1.0, zorder=1)
    ax.set_title(title, color=FG, fontsize=11.5, loc="left", pad=28)
    ax.text(0, 1.012, sub, color=MUTED, fontsize=9, transform=ax.transAxes,
            ha="left", va="bottom")
    ax.set_xlim(-10.2, 10.2)
    ax.set_ylim(-1.4, 13.2)
    ax.set_aspect("equal")
    ax.axis("off")

    if show_scale:
        ax.plot([-9.4, -6.4], [-0.9, -0.9], color=MUTED, linewidth=1.4)
        ax.text(-7.9, -1.35, "3 m", color=MUTED, fontsize=8, ha="center")


def figure_two() -> str:
    vert = fl.vertical_field()
    bare = fl.normalise(fl.solar_field(False))
    site = fl.normalise(fl.solar_field(True))
    rad = fl.radial_field()
    rat = fl.rationalise(fl.depths_from(rad), 5)
    rad_s = [(d - v.D_MIN) / (v.DMAX_DEFAULT - v.D_MIN) for d in rat]

    S = F["solar"]
    uv = F["uniform_vs_partition"]

    fig = plt.figure(figsize=(13.4, 11.6), dpi=118)
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 0.50],
                          hspace=0.34, wspace=0.07,
                          left=0.045, right=0.955, top=0.845, bottom=0.055)

    elevation(fig.add_subplot(gs[0, 0]), bare,
              "A   SUN, BARE ELEVATION",
              "88 units, one number: %.1f kWh/m²/yr on every one of them"
              % S["bare_min"], show_scale=True)
    elevation(fig.add_subplot(gs[0, 1]), site,
              "B   SUN, ONE NEIGHBOUR IN THE MODEL",
              "%.0f to %.0f kWh/m²/yr, %d distinct values"
              % (S["site_min"], S["site_max"], S["site_distinct_values"]))
    elevation(fig.add_subplot(gs[1, 0]), rad,
              "C   THE FIELD CHOSEN: RADIAL FROM THE ENTRANCE",
              "a design decision, not a derived one. 26 families, free.")
    elevation(fig.add_subplot(gs[1, 1]), rad_s,
              "D   THE SAME FIELD, FIVE FAMILIES",
              "exact 1D partition. levels at %s mm"
              % ", ".join("%.0f" % x for x in uv["partition"]["levels_mm"]))

    ax = fig.add_subplot(gs[2, 0])
    ax.axis("off")
    rows = [
        ("0.00 %", "the spread of annual sun across\nall 88 units on a bare elevation"),
        ("43.9 %", "the spread once one building\nstands across the street"),
    ]
    y = 0.95
    for big, small in rows:
        ax.text(0.0, y, big, color=AMBER, fontsize=25, fontweight="bold",
                va="top", transform=ax.transAxes)
        ax.text(0.31, y - 0.05, small, color=FG, fontsize=11, va="top",
                linespacing=1.55, transform=ax.transAxes)
        y -= 0.48
    ax.text(0.0, -0.06, "The field cannot be derived from nothing. It is either "
            "the site,\nor a decision you own.", color=MUTED, fontsize=10.5,
            style="italic", va="top", linespacing=1.55, transform=ax.transAxes)

    ax2 = fig.add_subplot(gs[2, 1])
    ks = [r["k"] for r in F["k_curve"]]
    rms = [r["rms_deviation_mm"] for r in F["k_curve"]]
    ax2.plot(ks, rms, color=AMBER, linewidth=2.2, marker="o", markersize=4,
             markerfacecolor=BG, markeredgecolor=AMBER, zorder=3)
    ax2.scatter([5], [uv["uniform"]["rms_deviation_mm"]], s=52, color=COOL,
                zorder=4, marker="D")
    ax2.annotate("uniform fifths\n%.0f mm" % uv["uniform"]["rms_deviation_mm"],
                 xy=(5, uv["uniform"]["rms_deviation_mm"]), xytext=(7.0, 185),
                 color=COOL, fontsize=9.5, va="center",
                 arrowprops=dict(arrowstyle="-", color=COOL, linewidth=0.9))
    ax2.annotate("partition, same five\n%.0f mm"
                 % uv["partition"]["rms_deviation_mm"],
                 xy=(5, uv["partition"]["rms_deviation_mm"]), xytext=(7.0, 95),
                 color=AMBER, fontsize=9.5, fontweight="bold", va="center",
                 arrowprops=dict(arrowstyle="-", color=AMBER, linewidth=0.9))
    ax2.set_xlim(0.5, 12.5)
    ax2.set_ylim(0, 340)
    ax2.set_xticks([1, 5, 12])
    ax2.set_xlabel("families", color=MUTED, fontsize=9)
    ax2.set_ylabel("rms depth deviation, mm", color=MUTED, fontsize=9)
    ax2.tick_params(labelsize=8.5)
    ax2.grid(True, linewidth=0.6, alpha=0.45)
    for side in ("top", "right"):
        ax2.spines[side].set_visible(False)
    ax2.set_title("what five families cost, and how you pick them",
                  color=FG, fontsize=10.5, loc="left", pad=8)

    fig.text(0.045, 0.955, "F A C A D E   L O G I C   0 1   ·   "
             "F O L D E D   V E I L   ·   S E S S I O N   0 2",
             color=MUTED, fontsize=10.5, fontweight="bold")
    fig.text(0.045, 0.915,
             "A gradient needs a field. An empty site cannot give you one.",
             color=FG, fontsize=18, fontweight="bold")
    fig.text(0.955, 0.955, "archicoder.com", color=MUTED, fontsize=10, ha="right")

    out = os.path.join(MEDIA, "FV-02-where-the-field-comes-from.png")
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# Session 3: the cut sheet

import nest as nz   # noqa: E402


def _placed_polys(entry, cache):
    """Turn one packed rectangle back into the real blank outlines."""
    x, y, w, h, payload, _turned = entry
    if payload is None:
        return []
    f, kind = payload
    d = cache[f]
    base = nz.piece_triangles(f)
    polys = [nz.piece_outline(f)]
    if kind == "pair":
        rot = [(-p[0] + d["pair_dx"], -p[1] + d["pair_dy"])
               for p in nz.piece_outline(f)]
        polys.append(rot)
    allpts = [p for poly in polys for p in poly]
    x0, y0, _, _ = nz.bbox(allpts)
    out = []
    for poly in polys:
        pts = [(p[0] - x0, p[1] - y0) for p in poly]
        out.append([(q[0] + x, q[1] + y) for q in pts])
    return out


def blank_panel(ax, f, paired, title, sub):
    cache = nz.run([f], "one", "2000 x 4000")["_per_shape"]
    d = cache[(round(f, 9), "2000 x 4000")]
    polys = [nz.piece_outline(f)]
    if paired:
        polys.append([(-p[0] + d["pair_dx"], -p[1] + d["pair_dy"])
                      for p in nz.piece_outline(f)])
    allpts = [p for poly in polys for p in poly]
    x0, y0, x1, y1 = nz.bbox(allpts)

    ax.add_patch(Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True,
                         facecolor="none", edgecolor=GRID, linewidth=1.0,
                         linestyle=(0, (5, 4)), zorder=1))
    for i, poly in enumerate(polys):
        ax.add_patch(Polygon(poly, closed=True,
                             facecolor=AMBER if i == 0 else COOL,
                             alpha=0.80, edgecolor=BG, linewidth=1.1, zorder=2))
    eff = d["pair_efficiency"] if paired else d["bbox_efficiency"]
    ax.text(0.5, -0.10, "%s\n%.0f%% of the dashed box is metal"
            % (sub, 100 * eff), color=MUTED, fontsize=9.5, ha="center",
            va="top", linespacing=1.6, transform=ax.transAxes)
    ax.set_title(title, color=FG, fontsize=11, loc="left", pad=10)
    m = 0.10
    ax.set_xlim(x0 - m, x1 + m)
    ax.set_ylim(y0 - m, y1 + m)
    ax.set_aspect("equal")
    ax.axis("off")


def eff_curve(ax):
    """What pairing is worth, across the gradient."""
    fs = [i / 16 for i in range(17)]
    bb, pr = [], []
    for f in fs:
        d = nz.run([f], "c", "2000 x 4000")["_per_shape"][(round(f, 9),
                                                           "2000 x 4000")]
        bb.append(100 * d["bbox_efficiency"])
        pr.append(100 * d["pair_efficiency"])
    ax.fill_between(fs, bb, pr, color=AMBER, alpha=0.13, zorder=1)
    ax.plot(fs, pr, color=AMBER, linewidth=2.3, zorder=3)
    ax.plot(fs, bb, color=COOL, linewidth=1.8, linestyle=(0, (4, 3)), zorder=2)
    x = nz.concave_crossover()
    ax.axvline(x, color=MUTED, linewidth=0.9, linestyle=(0, (2, 3)), zorder=1)
    ax.text(x + 0.02, 22, "concave\u2192convex", color=MUTED, fontsize=8.5)
    ax.text(0.04, 94, "paired", color=AMBER, fontsize=9.5, fontweight="bold")
    ax.text(0.55, 44, "one up", color=COOL, fontsize=9.5, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_ylim(15, 105)
    ax.set_xticks([0, 0.5, 1])
    ax.set_xticklabels(["f = 0", "", "f = 1"], fontsize=8.5)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=8.5)
    ax.grid(True, linewidth=0.6, alpha=0.45)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_title("how much of the box is metal", color=FG, fontsize=10.5,
                 loc="left", pad=8)


def figure_three() -> str:
    rad = fl.radial_field()
    r = nz.run(rad, "free gradient", "2000 x 4000")
    cache = {k[0]: vv for k, vv in r["_per_shape"].items()}
    sheet = nz.STOCK["2000 x 4000"]
    layout = r["_pair_layout"][0]

    fig = plt.figure(figsize=(13.4, 10.2), dpi=118)
    gs = fig.add_gridspec(2, 3, width_ratios=[1, 1, 1.25],
                          height_ratios=[1, 0.70],
                          hspace=0.46, wspace=0.22,
                          left=0.045, right=0.955, top=0.845, bottom=0.085)

    blank_panel(fig.add_subplot(gs[0, 0]), 0.2, False,
                "ONE SHALLOW BLANK", "concave, and mostly air")
    blank_panel(fig.add_subplot(gs[0, 1]), 0.2, True,
                "TWO, ONE TURNED 180\u00b0", "the notch takes the point")

    ax = fig.add_subplot(gs[:, 2])
    ax.add_patch(Polygon([(0, 0), (sheet[0], 0), (sheet[0], sheet[1]),
                          (0, sheet[1])], closed=True, facecolor="#1A1611",
                         edgecolor=MUTED, linewidth=1.4, zorder=1))
    for entry in layout:
        for poly in _placed_polys(entry, cache):
            ax.add_patch(Polygon(poly, closed=True, facecolor=AMBER, alpha=0.78,
                                 edgecolor=BG, linewidth=0.9, zorder=3))
    ax.set_title("ONE SHEET, 2000 \u00d7 4000", color=FG, fontsize=11,
                 loc="left", pad=10)
    ax.text(0.5, -0.04, "%d sheets carry all 352 pieces" % r["sheets_paired"],
            color=MUTED, fontsize=9.5, ha="center", va="top",
            transform=ax.transAxes)
    ax.set_xlim(-0.12, sheet[0] + 0.12)
    ax.set_ylim(-0.12, sheet[1] + 0.12)
    ax.set_aspect("equal")
    ax.axis("off")

    eff_curve(fig.add_subplot(gs[1, 0]))

    ax3 = fig.add_subplot(gs[1, 1])
    ax3.axis("off")
    lines = [
        ("1500 = 1500", "the frame edge is exactly the width of\n"
                        "standard 1500 stock, so nothing fits it.\n"
                        "The veil moves to 2000 \u00d7 4000."),
        ("%d \u2192 %d" % (r["sheets_one_up"], r["sheets_paired"]),
         "sheets, from turning every second blank\n"
         "by 180\u00b0. That keeps the grain running\n"
         "one way. 90\u00b0 would not."),
    ]
    y = 0.99
    for big, small in lines:
        ax3.text(0.0, y, big, color=AMBER, fontsize=23, fontweight="bold",
                 va="top", transform=ax3.transAxes)
        ax3.text(0.0, y - 0.155, small, color=FG, fontsize=10.5, va="top",
                 linespacing=1.55, transform=ax3.transAxes)
        y -= 0.52

    fig.text(0.045, 0.955, "F A C A D E   L O G I C   0 1   \u00b7   "
             "F O L D E D   V E I L   \u00b7   S E S S I O N   0 3",
             color=MUTED, fontsize=10.5, fontweight="bold")
    fig.text(0.045, 0.912,
             "The shallow blank is more air than metal. Its neighbour is the fix.",
             color=FG, fontsize=18, fontweight="bold")
    fig.text(0.955, 0.955, "archicoder.com", color=MUTED, fontsize=10, ha="right")
    fig.text(0.045, 0.012, "Five families cost 6.8% more metal and one more "
             "sheet than the free gradient. Rationalising buys tooling and "
             "handling, not material.",
             color=MUTED, fontsize=10.5, style="italic")

    out = os.path.join(MEDIA, "FV-03-the-cut-sheet.png")
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out
