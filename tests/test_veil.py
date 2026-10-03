"""test_veil.py - what has to stay true about the folded unit.

Run:  python3 -m pytest tests -q     or     python3 tests/test_veil.py
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import veil as v   # noqa: E402


# --- the brief -------------------------------------------------------------

def test_unit_count_matches_the_paper():
    assert v.N_UNITS == 88
    assert v.N_UNITS * 8 == 704
    assert len(v.unit_positions()) == 88
    assert len(v.facade()) == 88


def test_every_unit_has_eight_faces():
    for f in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert len(v.unit(f).faces) == 8


def test_gradient_endpoints():
    assert math.isclose(v.depth(0.0), 0.12)
    assert math.isclose(v.depth(1.0), 0.90)
    assert math.isclose(v.aperture(0.0), 0.6525)
    assert math.isclose(v.aperture(1.0), 0.315)


def test_coordinate_table_is_mid_gradient():
    """The paper's table lists B points at 0.50, which is not f = 0."""
    f = v.f_of_aperture(0.50)
    assert 0.45 < f < 0.46
    assert not math.isclose(f, 0.0, abs_tol=0.01)


# --- the surface -----------------------------------------------------------

def test_faces_are_planar():
    """Triangles are planar by construction. The quad they replace is not:
    that is the reason the paper triangulates at all."""
    for f in (0.0, 0.5, 1.0):
        u = v.unit(f)
        p = u.points
        for a, b, c in u.faces:
            assert v.tri_area(p[a], p[b], p[c]) > 1e-9
        # the quad (Ai, Aj, Bj, Bi) across one corner, out of plane
        A0, A1, B1, B0 = p[0], p[1], p[5], p[4]
        n = v.tri_normal(A0, A1, B1)
        off = abs(v.dot(n, v.sub(B0, A0)))
        assert off > 1e-3, "quad would be planar, triangulation unnecessary"


def test_aligned_reading_tiles_the_band():
    """B_k on the axis of its own frame edge: the 8 faces cover the band
    between frame and aperture exactly once and leave the aperture clear."""
    for f in (0.0, 0.5, 1.0):
        c = v.plan_cover(v.unit(f), n=200)
        assert c["aperture_blocked"] < 0.01
        assert c["band_covered_once"] > 0.98
        assert c["band_covered_twice_or_more"] < 0.01


def test_pinwheel_reading_is_not_a_surface():
    """B_k swept to the next frame edge does not pinwheel into a chiral part.
    It blocks the aperture and covers the band twice."""
    for f in (0.0, 0.5, 1.0):
        c = v.plan_cover(v.unit(f, pinwheel=True), n=200)
        assert c["aperture_blocked"] > 0.3
        assert c["band_covered_twice_or_more"] > 0.05
        assert not v.tiles(v.unit(f, pinwheel=True))


def test_unit_has_mirror_symmetry():
    """Mirroring x negates x and permutes the vertices. A chiral unit could
    not do this, so the mirrored unit is the same part, not a new one."""
    u = v.unit(0.4)
    pts = {(round(p[0], 9), round(p[1], 9), round(p[2], 9)) for p in u.points}
    mirrored = {(round(-p[0], 9), round(p[1], 9), round(p[2], 9)) for p in u.points}
    assert pts == mirrored


def test_area_factor_is_just_the_rake():
    """Developed area over plan band area is the rake alone for a tiling
    surface, and doubles for the overlapping reading of the same face list."""
    for f in (0.0, 0.5, 1.0):
        assert 1.0 <= v.area_factor(v.unit(f)) <= 2.1
    assert v.area_factor(v.unit(0.0, pinwheel=True)) > 2.2


# --- the measurements ------------------------------------------------------

def test_flange_at_the_shallow_end():
    u = v.unit(0.0)
    assert math.isclose(v.plan_gap(u) * 1000, 97.5, abs_tol=0.1)
    assert math.isclose(v.flange_span(u) * 1000, 154.6, abs_tol=0.5)


def test_flange_at_the_deep_end():
    u = v.unit(1.0)
    assert math.isclose(v.plan_gap(u) * 1000, 435.0, abs_tol=0.1)
    assert math.isclose(v.flange_span(u) * 1000, 999.6, abs_tol=0.5)


def test_span_ratio_across_one_facade():
    ratio = v.flange_span(v.unit(1.0)) / v.flange_span(v.unit(0.0))
    assert 6.4 < ratio < 6.5


def test_fold_goes_flat_as_depth_goes_to_zero():
    u = v.unit(0.0)
    shallow = v.Unit(f=0.0, d=1e-4, r=u.r, A=u.A,
                     B=[(b[0], -1e-4, b[2]) for b in u.B],
                     faces=u.faces, pinwheel=False)
    assert v.piece_fold_angle(shallow) > 179.0


def test_fold_angle_barely_moves_across_the_gradient():
    """The finding of session 1: depth ranges 7.5 to 1, the bend angle does
    not follow it."""
    angles = [v.piece_fold_angle(v.unit(i / 20)) for i in range(21)]
    assert min(angles) > 120.0
    assert max(angles) < 145.0
    assert max(angles) - min(angles) < 20.0


def test_unrolling_preserves_every_edge_length():
    u = v.unit(0.7)
    p = u.points
    order = v.strip_order(u)
    flat = v.unroll(u)
    for k, fi in enumerate(order):
        tri = u.faces[fi]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            d3 = v.norm(v.sub(p[tri[a]], p[tri[b]]))
            d2 = math.dist(flat[k][a], flat[k][b])
            assert math.isclose(d3, d2, abs_tol=1e-9)


def test_blank_area_equals_developed_area():
    u = v.unit(0.3)
    _, _, area = v.piece_blank(u)
    assert math.isclose(area * 4, v.metal_area(u), rel_tol=1e-9)


def test_every_piece_blank_fits_a_standard_sheet():
    for f in (0.0, 0.5, 1.0):
        long_side, short_side, _ = v.piece_blank(v.unit(f))
        assert long_side <= v.SHEET_L + 1e-9
        assert short_side <= v.SHEET_W + 1e-9


def test_vertical_field_gives_eight_families_not_eighty_eight():
    """The free gradient is not 88 bespoke units. Under a one dimensional
    field it is one family per row."""
    assert len({round(u.f, 6) for u in v.facade(snapped=False)}) == 8
    assert len({round(u.f, 6) for u in v.facade(snapped=True)}) == 5


# --- the field, session 2 ---------------------------------------------------

def test_bare_elevation_carries_no_field():
    """The finding of session 2: with nothing in the model, every one of the
    88 units receives the same annual irradiation."""
    import field as fl
    vals = fl.solar_field(False)
    assert len(vals) == 88
    assert max(vals) - min(vals) < 1e-6


def test_one_neighbour_makes_the_field_two_dimensional():
    import field as fl
    bare, site = fl.solar_field(False), fl.solar_field(True)
    assert max(site) < max(bare)
    spread = (max(site) - min(site)) / max(site)
    assert spread > 0.30
    assert len({round(x, 1) for x in site}) > 40


def test_radial_field_is_shallow_at_the_entrance():
    import field as fl
    fs = fl.radial_field()
    centres = fl.unit_centres()
    lo = min(range(len(fs)), key=lambda i: fs[i])
    _, _, y, z = centres[lo]
    assert abs(y) <= 4.0 and z <= 3.0


def test_partition_beats_uniform_fifths_on_the_same_five():
    """Why the skin-logic tool is worth importing: same number of families,
    less deviation."""
    import field as fl
    fs = fl.radial_field()
    u = fl.uniform_snap(fs)
    p = fl.rationalised("radial", fs, 5)
    assert u["families_after"] == p["families_after"] == 5
    assert p["rms_deviation_mm"] < u["rms_deviation_mm"]
    assert p["extra_metal_pct"] < u["extra_metal_pct"]


def test_rationalise_never_goes_shallower():
    """Groups are set to their deepest member, so no unit loses depth."""
    import field as fl
    free = fl.depths_from(fl.radial_field())
    rat = fl.rationalise(free, 4)
    assert all(r >= f - 1e-9 for r, f in zip(rat, free))


def test_k_curve_is_monotone():
    """The reason skin-logic chose an exact partition over k-means."""
    rms = [fl_rms(k) for k in range(1, 10)]
    assert all(a >= b - 1e-9 for a, b in zip(rms, rms[1:]))


def fl_rms(k):
    import field as fl
    return fl.rationalised("radial", fl.radial_field(), k)["rms_deviation_mm"]


# --- the cut sheet, session 3 -----------------------------------------------

def test_blank_is_concave_while_shallow_and_convex_when_deep():
    """The split session 3 turns on. It is not concave all the way."""
    import nest as nz
    for f in (0.0, 0.2, 0.35):
        assert len(nz.piece_outline(f)) == 4
        assert nz.is_concave(nz.piece_outline(f))
    for f in (0.5, 0.8, 1.0):
        assert not nz.is_concave(nz.piece_outline(f))
    assert 0.35 < nz.concave_crossover() < 0.45


def test_blank_area_matches_the_folded_area():
    import nest as nz
    for f in (0.0, 0.4, 1.0):
        assert math.isclose(nz.poly_area(nz.piece_outline(f)) * 4,
                            v.metal_area(v.unit(f)), rel_tol=1e-9)


def test_frame_edge_is_exactly_the_standard_sheet_width():
    """The collision this session found. The module came from the 3 m bay and
    lands on 1500 mm stock with nothing to spare."""
    import nest as nz
    out = nz.piece_outline(0.0)
    x0, _, x1, _ = nz.bbox(out)
    assert math.isclose((x1 - x0) * 1000, 1500.0, abs_tol=0.01)
    usable = nz.STOCK["1500 x 3000"][0] - 2 * nz.MARGIN
    assert (x1 - x0) > usable


def test_nothing_fits_1500_stock_and_everything_fits_2000():
    import nest as nz, field as fl
    fs = fl.radial_field()
    assert nz.run(fs, "t", "1500 x 3000")["sheets_paired"] == -1
    assert nz.run(fs, "t", "2000 x 4000")["sheets_paired"] > 0


def test_pairing_rescues_the_shallow_blank_and_not_the_deepest():
    import nest as nz
    gains = {}
    for f in (0.0, 0.3, 0.6, 1.0):
        d = nz.run([f], "t", "2000 x 4000")["_per_shape"][(round(f, 9),
                                                           "2000 x 4000")]
        gains[f] = d["pair_efficiency"] - d["bbox_efficiency"]
    assert gains[0.0] > 0.30
    assert gains[0.3] > 0.35
    assert gains[1.0] < 0.05


def test_pairing_cuts_the_sheet_count():
    import nest as nz, field as fl
    r = nz.run(fl.radial_field(), "t", "2000 x 4000")
    assert r["sheets_paired"] < r["sheets_one_up"]


def test_packed_parts_stay_on_the_sheet_and_do_not_overlap():
    import nest as nz, field as fl
    r = nz.run(fl.radial_field(), "t", "2000 x 4000")
    sw, sl = nz.STOCK["2000 x 4000"]
    for sheet in r["_pair_layout"]:
        for x, y, w, h, _, _ in sheet:
            assert x >= nz.MARGIN - 1e-9 and y >= nz.MARGIN - 1e-9
            assert x + w <= sw - nz.MARGIN + 1e-9
            assert y + h <= sl - nz.MARGIN + 1e-9
        for i in range(len(sheet)):
            for j in range(i + 1, len(sheet)):
                ax, ay, aw, ah = sheet[i][:4]
                bx, by, bw, bh = sheet[j][:4]
                apart = (ax + aw <= bx + 1e-9 or bx + bw <= ax + 1e-9
                         or ay + ah <= by + 1e-9 or by + bh <= ay + 1e-9)
                assert apart


def test_five_families_cost_metal_rather_than_saving_it():
    """The correction of session 3: rationalising buys tooling, not material."""
    import nest as nz, field as fl
    rad = fl.radial_field()
    rat = fl.rationalise(fl.depths_from(rad), 5)
    rad5 = [(d - v.D_MIN) / (v.DMAX_DEFAULT - v.D_MIN) for d in rat]
    free = nz.run(rad, "free", "2000 x 4000")
    five = nz.run(rad5, "five", "2000 x 4000")
    assert five["metal_m2"] > free["metal_m2"]
    assert five["sheets_paired"] >= free["sheets_paired"]


if __name__ == "__main__":
    import types
    mod = sys.modules["__main__"]
    fails = 0
    for name in sorted(dir(mod)):
        if name.startswith("test_"):
            fn = getattr(mod, name)
            if isinstance(fn, types.FunctionType):
                try:
                    fn()
                    print(f"  ok   {name}")
                except AssertionError as e:
                    fails += 1
                    print(f"  FAIL {name}  {e}")
    print(f"\n{'all passed' if not fails else str(fails) + ' failed'}")
    sys.exit(1 if fails else 0)
