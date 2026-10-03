#! python3
"""LB-01: potential direct sun hours at the glass, with and without the veil.

Run inside Rhino 8 with exports/sun-hours/FV-LB01-west-facing-inputs.3dm
open and Grasshopper loaded. Builds grasshopper/FV-LB01-direct-sun-hours.gh,
solves it and prints the comparison.

Assumptions (stated in docs/LB-01-guided-session.md):
  Istanbul as a study location, not a surveyed site. 40.99329, 29.06463, UTC+3.
  West-facing glass, +Y north. 21 June, whole day, 4 steps per hour.
  Geometric sun hours only: no clouds, no diffuse light, no energy.
  Same vectors and timestep for both cases.
  geo_block_ True with a 10 mm offset. Corrected 2026-10-01: the planned
  geo_block_ False also drops Ladybug's facing check, so west glass counted
  morning sun from behind (15.0 h, every sun-up hour). With geo_block_ True
  the glass blocks rays from behind, and the 10 mm offset keeps the test
  points just outside the glass so they do not hit their own face.
  The test meshes are pre-divided (0.25 m); _grid_size does not re-mesh them.
"""
import os
import Rhino
import Grasshopper as gh
from System.Drawing import PointF, RectangleF, Color
from Grasshopper.Kernel import GH_Document, GH_DocumentIO
from Grasshopper.Kernel.Data import GH_Path
from Grasshopper.Kernel.Types import GH_Number, GH_Integer, GH_Boolean, GH_String, GH_Mesh
from Grasshopper.Kernel.Special import GH_Panel, GH_Group, GH_BooleanToggle, GH_Scribble
from Grasshopper.Kernel.Parameters import Param_Mesh

try:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
except NameError:  # run from an editor without __file__: set LB_ROOT first
    ROOT = globals()["LB_ROOT"]
OUT = os.path.join(ROOT, "grasshopper", "FV-LB01-direct-sun-hours.gh")
MONTH = globals().get("LB_MONTH", 6)
DAY = globals().get("LB_DAY", 21)
TIMESTEP = 4
OFFSET = 0.01         # m, test points just outside the glass
CASE_A_SHIFT = 21.0   # m north, so the no-veil result sits beside the veil case

rhdoc = Rhino.RhinoDoc.ActiveDoc
doc = GH_Document()
GROUPS = []
CW, RH = 220, 80


def impl(o):
    return getattr(o, "__implementation__", o)


def proxy(name):
    for p in gh.Instances.ComponentServer.ObjectProxies:
        if p.Desc.Name == name and not p.Obsolete:
            return p
    raise RuntimeError("Component not found: " + name)


def place(obj, x, y, nick=None):
    obj.CreateAttributes()
    if nick:
        obj.NickName = nick
    obj.Attributes.Pivot = PointF(x, y)
    doc.AddObject(obj, False)
    return obj


def comp(name, c, r, nick=None):
    return place(proxy(name).CreateInstance(), c * CW, r * RH, nick)


def find(params, key):
    for p in params:
        if p.NickName == key or p.Name == key:
            return p
    raise RuntimeError("No parameter %s in %s" % (key, [p.NickName for p in params]))


def out(o, key=None):
    if hasattr(o, "Params"):
        return o.Params.Output[0] if key is None else find(o.Params.Output, key)
    return o


def wire(src, dst, key, src_key=None):
    find(dst.Params.Input, key).AddSource(out(src, src_key))


def const(c, key, goo):
    p = impl(find(c.Params.Input, key))
    p.PersistentData.Clear()
    p.PersistentData.Append(goo, GH_Path(0))


def layer_meshes(layer_name, nick, c, r):
    idx = rhdoc.Layers.FindName(layer_name).Index
    objs = sorted([o for o in rhdoc.Objects if o.Attributes.LayerIndex == idx],
                  key=lambda o: o.Attributes.Name)
    p = Param_Mesh()
    for o in objs:
        g = GH_Mesh(o.Id)
        g.LoadGeometry(rhdoc)
        p.PersistentData.Append(g, GH_Path(0))
    place(p, c * CW, r * RH, nick)
    return p, len(objs)


def panel(nick, c, r, w=200, h=40, src=None, text=""):
    p = GH_Panel()
    p.CreateAttributes()
    p.NickName = nick
    p.UserText = text
    p.Attributes.Pivot = PointF(c * CW, r * RH)
    p.Attributes.Bounds = RectangleF(c * CW, r * RH, w, h)
    doc.AddObject(p, False)
    if src is not None:
        p.AddSource(src)
    return p


# 01 Sun ------------------------------------------------------------------
loc = comp("LB Construct Location", 0, 0, "Istanbul (study)")
const(loc, "_name_", GH_String("Istanbul study location"))
const(loc, "_latitude_", GH_Number(40.99329222222222))
const(loc, "_longitude_", GH_Number(29.064626666666665))
const(loc, "_time_zone_", GH_Number(3))
per = comp("LB Analysis Period", 0, 2, "21 June, 4/h")
for k, v in [("_start_month_", MONTH), ("_start_day_", DAY), ("_start_hour_", 0),
             ("_end_month_", MONTH), ("_end_day_", DAY), ("_end_hour_", 23),
             ("_timestep_", TIMESTEP)]:
    const(per, k, GH_Integer(v))
sun = comp("LB SunPath", 1, 0.5, "Sun path")
wire(loc, sun, "_location"); wire(per, sun, "hoys_", "hoys")
sun.Hidden = True
GROUPS.append(("01 Sun: Istanbul study location, 21 June, 4 steps per hour", Color.FromArgb(150, 255, 214, 120), [loc, per, sun]))

# 02 Shared inputs ----------------------------------------------------------
glass, n_glass = layer_meshes("02_Glass_TestGrid_250mm", "Glass (88)", 2, 0)
veil, n_veil = layer_meshes("01_Veil_Context", "Veil context (88)", 2, 1.5)
run = GH_BooleanToggle(); run.Value = True
place(run, 2 * CW, 3 * RH, "_run")
leg = comp("LB Legend Parameters", 2, 4.2, "Shared legend 0 to max")
const(leg, "min_", GH_Number(0))
GROUPS.append(("02 Shared inputs: same glass, same vectors, same legend", Color.FromArgb(150, 170, 210, 255), [glass, veil, run, leg]))


def case(nick, r, with_context):
    dsh = comp("LB Direct Sun Hours", 3.2, r, nick)
    wire(sun, dsh, "_vectors", "vectors")
    const(dsh, "_timestep_", GH_Integer(TIMESTEP))
    wire(glass, dsh, "_geometry")
    if with_context:
        wire(veil, dsh, "context_")
    const(dsh, "_grid_size", GH_Number(0.25))
    const(dsh, "_offset_dist_", GH_Number(OFFSET))
    const(dsh, "geo_block_", GH_Boolean(True))
    wire(leg, dsh, "legend_par_")
    wire(run, dsh, "_run")
    avg = comp("Average", 4.4, r - 0.3, nick + " mean")
    find(avg.Params.Input, "I").DataMapping = gh.Kernel.GH_DataMapping.Flatten
    wire(dsh, avg, "I", "results")
    bnd = comp("Bounds", 4.4, r + 0.7, nick + " range")
    find(bnd.Params.Input, "N").DataMapping = gh.Kernel.GH_DataMapping.Flatten
    wire(dsh, bnd, "N", "results")
    p1 = panel(nick + " mean h", 5.4, r - 0.5, 160, 36, out(avg, "AM") if any(o.NickName == "AM" for o in avg.Params.Output) else out(avg))
    p2 = panel(nick + " min to max h", 5.4, r + 0.5, 160, 36, out(bnd))
    return dsh, [dsh, avg, bnd, p1, p2]


dsh_a, mem_a = case("A glass only", 1, False)
dsh_b, mem_b = case("B glass + veil", 3.5, True)

# Display: case A moved north beside case B; Ladybug's own previews off
dsh_a.Hidden = True
mv = comp("Move", 6.4, 1, "A shown 21 m north")
uy = comp("Unit Y", 6.4, 2, "21 m")
const(uy, "F", GH_Number(CASE_A_SHIFT))
wire(dsh_a, mv, "G", "mesh"); wire(uy, mv, "T")
mem_a += [mv, uy]
GROUPS.append(("03 Case A: glass with nothing in front (expect a uniform result)", Color.FromArgb(150, 200, 255, 190), mem_a))
GROUPS.append(("04 Case B: same glass, veil as context", Color.FromArgb(150, 255, 190, 170), mem_b))

title = GH_Scribble(); title.Text = "LB-01  Potential direct sun hours at the glass, with and without the Folded Veil. Geometric only."
place(title, 0, -60)

for name, colour, members in GROUPS:
    g = GH_Group(); g.CreateAttributes(); g.NickName = name; g.Colour = colour
    for m in members:
        g.AddObject(m.InstanceGuid)
    doc.AddObject(g, False)

# Solve, set the shared legend max from case A, solve again -----------------
gh.Instances.DocumentServer.AddDocument(doc)
if gh.Instances.ActiveCanvas is not None:
    gh.Instances.ActiveCanvas.Document = doc
doc.Enabled = True
doc.NewSolution(True)


def hours(dsh):
    return [float(getattr(v, "Value", v)) for v in out(dsh, "results").VolatileData.AllData(True)]


a, b = hours(dsh_a), hours(dsh_b)
if a:
    const(leg, "max_", GH_Number(max(a)))
    leg.ExpireSolution(False)
    doc.NewSolution(False)
    a, b = hours(dsh_a), hours(dsh_b)

errors = [(o.NickName, [str(m) for m in o.RuntimeMessages(gh.Kernel.GH_RuntimeMessageLevel.Error)])
          for o in doc.Objects if hasattr(o, "RuntimeMessages")
          and list(o.RuntimeMessages(gh.Kernel.GH_RuntimeMessageLevel.Error))]
print("glass meshes:", n_glass, " veil meshes:", n_veil)
print("sun vectors:", len(list(out(sun, "vectors").VolatileData.AllData(True))))
print("faces A, B:", len(a), len(b))
if a and b:
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    print("A glass only   mean %.3f h  min %.3f  max %.3f" % (ma, min(a), max(a)))
    print("B glass + veil mean %.3f h  min %.3f  max %.3f" % (mb, min(b), max(b)))
    print("reduction of mean: %.1f %%" % (100 * (ma - mb) / ma if ma else 0))
print("errors:", errors or "none")

# Per-unit export: faces follow the glass meshes in name order
import csv, json
idx = rhdoc.Layers.FindName("02_Glass_TestGrid_250mm").Index
gobjs = sorted([o for o in rhdoc.Objects if o.Attributes.LayerIndex == idx], key=lambda o: o.Attributes.Name)
tag = "%02d%02d" % (MONTH, DAY)
rows, i = [], 0
for o in gobjs:
    n = o.Geometry.Faces.Count
    aa, bb = a[i:i + n], b[i:i + n]
    i += n
    rows.append({"unit": o.Attributes.Name.replace("_glass_grid", ""), "faces": n,
                 "a_mean_h": round(sum(aa) / n, 4), "b_mean_h": round(sum(bb) / n, 4),
                 "b_min_h": min(bb), "b_max_h": max(bb)})
assert i == len(a) == len(b)
sun_dir = os.path.join(ROOT, "exports", "sun-hours")
with open(os.path.join(sun_dir, "LB01-%s-per-unit.csv" % tag), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
summary = {"date": "%02d-%02d" % (MONTH, DAY), "timestep": TIMESTEP, "offset_m": OFFSET,
           "sun_vectors": len(list(out(sun, "vectors").VolatileData.AllData(True))),
           "faces": len(a), "a_mean_h": sum(a) / len(a), "a_min_h": min(a), "a_max_h": max(a),
           "b_mean_h": sum(b) / len(b), "b_min_h": min(b), "b_max_h": max(b)}
with open(os.path.join(sun_dir, "LB01-%s-summary.json" % tag), "w") as fh:
    json.dump(summary, fh, indent=2)
dsh_a.NickName, dsh_b.NickName = "A glass only", "B glass + veil"
GH_DocumentIO(doc).SaveQuiet(OUT)
print("Saved:", OUT)
