#! python3
"""Build FV-folded-veil.gh from native Grasshopper components.

Run inside Rhino 8 (ScriptEditor, Python 3) with Grasshopper already open.
It writes grasshopper/FV-folded-veil.gh next to this script, solves it once
and prints the checks against rhino/FV-folded-veil-reference.json.

The definition reproduces src/veil.py and src/field.py (free radial field):
  f  = distance from unit centre to entrance centre (9, 0, 0), remapped 0..1
  d  = 0.12 + (Dmax - 0.12) f
  r  = 0.75 (0.87 - 0.45 f) = 0.6525 - 0.3375 f
  A  = frame corners (+-0.75, 0, +-0.75) about the unit centre
  B  = diamond vertices on the axes at r, pushed to y = -d
  faces (i, j, 4+j) and (i, 4+j, 4+i), j = i+1 mod 4
Coordinates as the IFC: +X along the facade, -Y outward, +Z up, metres.
"""
import os
import json
import System
from System.Drawing import PointF, RectangleF, Color
import Grasshopper as gh
from Grasshopper.Kernel import GH_Document, GH_DocumentIO, GH_DataMapping
from Grasshopper.Kernel.Data import GH_Path
from Grasshopper.Kernel.Types import GH_Number, GH_Integer
from Grasshopper.Kernel.Special import GH_NumberSlider, GH_Panel, GH_Group
from Grasshopper.Kernel.Parameters import Param_Number, Param_Integer

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "FV-folded-veil.gh")
REF = os.path.join(os.path.dirname(HERE), "rhino", "FV-folded-veil-reference.json")

doc = GH_Document()
GROUPS = []


def impl(o):
    return getattr(o, "__implementation__", o)


def proxy(name, category=None):
    hits = []
    for p in gh.Instances.ComponentServer.ObjectProxies:
        if p.Obsolete or p.Desc.Name != name:
            continue
        if category and p.Desc.Category != category:
            continue
        hits.append(p)
    if not hits:
        raise RuntimeError("Component not found: %s (%s)" % (name, category))
    return hits[0]


def place(obj, col, row, nick=None):
    obj.CreateAttributes()
    if nick:
        obj.NickName = nick
    obj.Attributes.Pivot = PointF(60 + col * 190, 80 + row * 85)
    doc.AddObject(obj, False)
    return obj


def comp(name, col, row, nick=None, category=None):
    return place(proxy(name, category).CreateInstance(), col, row, nick)


def numbers(nick, values, col, row, integer=False):
    p = Param_Integer() if integer else Param_Number()
    for v in values:
        p.PersistentData.Append(GH_Integer(int(v)) if integer else GH_Number(float(v)), GH_Path(0))
    return place(p, col, row, nick)


def find(params, key):
    for p in params:
        if p.NickName == key or p.Name == key:
            return p
    raise RuntimeError("No parameter %s in %s" % (key, [p.NickName for p in params]))


def out(o, key=None):
    if hasattr(o, "Params"):
        return o.Params.Output[0] if key is None else find(o.Params.Output, key)
    return o


def inp(c, key):
    return find(c.Params.Input, key)


def wire(src, dst, key, src_key=None, mapping=None):
    p = inp(dst, key)
    p.AddSource(out(src, src_key))
    if mapping == "graft":
        p.DataMapping = GH_DataMapping.Graft
    elif mapping == "flatten":
        p.DataMapping = GH_DataMapping.Flatten
    return p


def const(c, key, value, integer=False):
    p = impl(inp(c, key))
    p.PersistentData.Clear()
    p.PersistentData.Append(GH_Integer(int(value)) if integer else GH_Number(float(value)), GH_Path(0))


def panel(nick, col, row, text="", w=170, h=60):
    p = GH_Panel()
    p.CreateAttributes()
    p.NickName = nick
    p.UserText = text
    p.Attributes.Bounds = RectangleF(60 + col * 190, 80 + row * 85, w, h)
    doc.AddObject(p, False)
    return p


def group(name, colour, members):
    GROUPS.append((name, colour, members))


def dec(t):
    return System.Decimal.Parse(t, System.Globalization.CultureInfo.InvariantCulture)


# 01 Inputs -------------------------------------------------------------
dmax = GH_NumberSlider()
dmax.CreateAttributes()
dmax.NickName = "Dmax (m)"
dmax.Slider.Type = gh.GUI.Base.GH_SliderAccuracy.Float
dmax.Slider.DecimalPlaces = 2
dmax.Slider.Minimum = dec("0.20")
dmax.Slider.Maximum = dec("0.90")
dmax.SetSliderValue(dec("0.90"))
dmax.Attributes.Pivot = PointF(60, 80)
doc.AddObject(dmax, False)

ent = comp("Construct Point", 0, 1, "Entrance centre", "Vector")
const(ent, "X", 9.0)
group("01 Inputs: Dmax and entrance centre (9, 0, 0)", Color.FromArgb(150, 255, 214, 120), [dmax, ent])

# 02 Unit grid: 12 columns x 8 rows, entrance removed -------------------
rows = comp("Series", 1, 0, "Rows 0..7", "Sets")
const(rows, "C", 8, integer=True)
cols = comp("Series", 1, 1, "Cols 0..11", "Sets")
const(cols, "C", 12, integer=True)
xref = comp("Cross Reference", 2, 0, "Row-major", "Sets")
# Holistic: input A varies fastest, so cols go in A to get row-major order
wire(cols, xref, "A")
wire(rows, xref, "B")
ent_idx = numbers("Entrance indices", [4, 5, 6, 7, 16, 17, 18, 19], 2, 2, integer=True)
cull_r = comp("Cull Index", 3, 0, "Rows (88)", "Sets")
wire(xref, cull_r, "L", "B")
wire(ent_idx, cull_r, "I")
cull_c = comp("Cull Index", 3, 1, "Cols (88)", "Sets")
wire(xref, cull_c, "L", "A")
wire(ent_idx, cull_c, "I")
cx0 = comp("Addition", 4, 1, "col + 0.5", "Maths")
wire(cull_c, cx0, "A"); const(cx0, "B", 0.5)
cx = comp("Multiplication", 5, 1, "cx", "Maths")
wire(cx0, cx, "A"); const(cx, "B", 1.5)
cz0 = comp("Addition", 4, 0, "row + 0.5", "Maths")
wire(cull_r, cz0, "A"); const(cz0, "B", 0.5)
cz = comp("Multiplication", 5, 0, "cz", "Maths")
wire(cz0, cz, "A"); const(cz, "B", 1.5)
centres = comp("Construct Point", 6, 0, "Unit centres", "Vector")
wire(cx, centres, "X"); wire(cz, centres, "Z")
group("02 Unit grid: 96 positions less 8 at the 6 x 3 m entrance = 88, FV-001 to FV-088 order",
      Color.FromArgb(150, 170, 210, 255),
      [rows, cols, xref, ent_idx, cull_r, cull_c, cx0, cx, cz0, cz, centres])

# 03 Radial field ------------------------------------------------------
dist = comp("Distance", 7, 0, "Distance to entrance", "Vector")
wire(centres, dist, "A"); wire(ent, dist, "B")
bnd = comp("Bounds", 8, 0, "Range", "Maths")
wire(dist, bnd, "N")
remap = comp("Remap Numbers", 9, 0, "f", "Maths")
wire(dist, remap, "V"); wire(bnd, remap, "S")
group("03 Radial field f: a design decision, not a solar result", Color.FromArgb(150, 255, 170, 170),
      [dist, bnd, remap])

# 04 Depth and aperture ------------------------------------------------
span = comp("Subtraction", 10, 1, "Dmax - 0.12", "Maths")
wire(dmax, span, "A"); const(span, "B", 0.12)
df = comp("Multiplication", 11, 0, "(Dmax - 0.12) f", "Maths")
wire(remap, df, "A"); wire(span, df, "B")
d = comp("Addition", 12, 0, "d", "Maths")
wire(df, d, "A"); const(d, "B", 0.12)
rf = comp("Multiplication", 11, 1, "-0.3375 f", "Maths")
wire(remap, rf, "A"); const(rf, "B", -0.3375)
r = comp("Addition", 12, 1, "r", "Maths")
wire(rf, r, "A"); const(r, "B", 0.6525)
group("04 Depth d = 0.12 + (Dmax - 0.12) f   Aperture r = 0.75 (0.87 - 0.45 f)",
      Color.FromArgb(150, 200, 255, 190), [span, df, d, rf, r])

# 05 Eight vertices per unit: A0..A3 frame, B0..B3 diamond ---------------
sxh = numbers("A x offsets", [0.75, -0.75, -0.75, 0.75, 0, 0, 0, 0], 13, 3)
szh = numbers("A z offsets", [0.75, 0.75, -0.75, -0.75, 0, 0, 0, 0], 13, 4)
bx = numbers("B x signs", [0, 0, 0, 0, 1, 0, -1, 0], 13, 5)
bz = numbers("B z signs", [0, 0, 0, 0, 0, 1, 0, -1], 13, 6)
by = numbers("B y signs", [0, 0, 0, 0, -1, -1, -1, -1], 13, 7)
bxr = comp("Multiplication", 14, 5, "bx r", "Maths")
wire(bx, bxr, "A"); wire(r, bxr, "B", mapping="graft")
bzr = comp("Multiplication", 14, 6, "bz r", "Maths")
wire(bz, bzr, "A"); wire(r, bzr, "B", mapping="graft")
vy = comp("Multiplication", 15, 7, "y", "Maths")
wire(by, vy, "A"); wire(d, vy, "B", mapping="graft")
x1 = comp("Addition", 14, 3, "cx + A", "Maths")
wire(cx, x1, "A", mapping="graft"); wire(sxh, x1, "B")
vx = comp("Addition", 15, 3, "x", "Maths")
wire(x1, vx, "A"); wire(bxr, vx, "B")
z1 = comp("Addition", 14, 4, "cz + A", "Maths")
wire(cz, z1, "A", mapping="graft"); wire(szh, z1, "B")
vz = comp("Addition", 15, 4, "z", "Maths")
wire(z1, vz, "A"); wire(bzr, vz, "B")
verts = comp("Construct Point", 16, 4, "8 vertices", "Vector")
wire(vx, verts, "X"); wire(vy, verts, "Y"); wire(vz, verts, "Z")
group("05 Eight vertices per unit, one branch per unit", Color.FromArgb(150, 220, 220, 220),
      [sxh, szh, bx, bz, by, bxr, bzr, vy, x1, vx, z1, vz, verts])

# 06 Mesh ----------------------------------------------------------------
fa = numbers("Face A", [0, 0, 1, 1, 2, 2, 3, 3], 16, 6, integer=True)
fb = numbers("Face B", [1, 5, 2, 6, 3, 7, 0, 4], 16, 7, integer=True)
fc = numbers("Face C", [5, 4, 6, 5, 7, 6, 4, 7], 16, 8, integer=True)
tri = comp("Mesh Triangle", 17, 7, "8 faces", "Mesh")
wire(fa, tri, "A"); wire(fb, tri, "B"); wire(fc, tri, "C")
mesh = comp("Construct Mesh", 18, 4, "Veil units", "Mesh")
wire(verts, mesh, "V"); wire(tri, mesh, "F")
mesh.Hidden = True
group("06 Mesh: faces (i, j, 4+j) and (i, 4+j, 4+i)", Color.FromArgb(150, 255, 200, 140),
      [fa, fb, fc, tri, mesh])

# 07 Preview coloured by f ------------------------------------------------
grad = comp("Gradient", 19, 2, "Colour by f", "Params")
wire(remap, grad, "t", mapping="graft")
prev = comp("Custom Preview", 20, 3, "Veil preview", "Display")
wire(mesh, prev, "G"); wire(grad, prev, "M")
group("07 Preview coloured by f", Color.FromArgb(150, 210, 190, 255), [grad, prev])

# 08 Check against the reference Rhino file ------------------------------
n = comp("List Length", 19, 5, "Units", "Sets")
wire(mesh, n, "L", mapping="flatten")
dm = comp("Deconstruct Mesh", 19, 6, "Deconstruct", "Mesh")
wire(mesh, dm, "M")
nf = comp("List Length", 20, 6, "Triangles", "Sets")
wire(dm, nf, "L", "F", mapping="flatten")
area = comp("Area", 19, 7, "Area", "Surface")
wire(mesh, area, "G")
tot = comp("Mass Addition", 20, 7, "Total m2", "Maths")
wire(area, tot, "I", "A", mapping="flatten")
drange = comp("Bounds", 20, 8, "Depth range m", "Maths")
wire(d, drange, "N", mapping="flatten")
ref_text = "Reference (rhino/FV-folded-veil-reference.json)\n88 units, 704 triangles\n249.35 m2\ndepth 0.12 to 0.90 m"
try:
    with open(REF) as s:
        ref = json.load(s)
    ref_text = ("Reference: %d units, %d triangles, %.2f m2, depth %s mm"
                % (ref["veil_meshes"], ref["veil_triangles"], ref["veil_area_m2_mesh"],
                   ref["depth_mm_min_max"]))
except Exception:
    pass
p_ref = panel("Reference", 21, 4, ref_text, 230, 70)
p_n = panel("Units", 21, 5); p_n.AddSource(out(n))
p_f = panel("Triangles", 22, 6); p_f.AddSource(out(nf))
p_a = panel("Total m2", 21, 7); p_a.AddSource(out(tot, "R"))
p_d = panel("Depth range", 22, 8); p_d.AddSource(out(drange))
group("08 Check: must match the reference Rhino file at Dmax 0.90", Color.FromArgb(150, 255, 255, 160),
      [n, dm, nf, area, tot, drange, p_ref, p_n, p_f, p_a, p_d])

# Layout ------------------------------------------------------------------
# Two bands read left to right. Top: inputs, grid, field, depth/aperture.
# Bottom: vertices, mesh, preview, check. Keys are (nickname, is_panel).
CW, RH = 210, 80          # column width, row height
TOP, BOT = 0, 420         # band origins (y)
LAYOUT = {
    # 01 inputs
    ("Dmax (m)", 0): (0, TOP, 0, 0), ("Entrance centre", 0): (0, TOP, 0, 1.5),
    # 02 grid
    ("Rows 0..7", 0): (300, TOP, 0, 0), ("Cols 0..11", 0): (300, TOP, 0, 1),
    ("Row-major", 0): (300, TOP, 1, 0.5), ("Entrance indices", 0): (300, TOP, 1, 2),
    ("Rows (88)", 0): (300, TOP, 2, 0), ("Cols (88)", 0): (300, TOP, 2, 1),
    ("row + 0.5", 0): (300, TOP, 3, 0), ("col + 0.5", 0): (300, TOP, 3, 1),
    ("cz", 0): (300, TOP, 4, 0), ("cx", 0): (300, TOP, 4, 1),
    ("Unit centres", 0): (300, TOP, 5, 0.5),
    # 03 field
    ("Distance to entrance", 0): (1660, TOP, 0, 0.5), ("Range", 0): (1660, TOP, 1, 0.5),
    ("f", 0): (1660, TOP, 2, 0.5),
    # 04 depth and aperture
    ("Dmax - 0.12", 0): (2390, TOP, 0, 0), ("(Dmax - 0.12) f", 0): (2390, TOP, 1, 0),
    ("d", 0): (2390, TOP, 2, 0), ("-0.3375 f", 0): (2390, TOP, 1, 1.2), ("r", 0): (2390, TOP, 2, 1.2),
    # 05 vertices
    ("A x offsets", 0): (0, BOT, 0, 0), ("A z offsets", 0): (0, BOT, 0, 1),
    ("B x signs", 0): (0, BOT, 0, 2), ("B z signs", 0): (0, BOT, 0, 3), ("B y signs", 0): (0, BOT, 0, 4),
    ("cx + A", 0): (0, BOT, 1, 0), ("cz + A", 0): (0, BOT, 1, 1),
    ("bx r", 0): (0, BOT, 1, 2), ("bz r", 0): (0, BOT, 1, 3), ("y", 0): (0, BOT, 1, 4),
    ("x", 0): (0, BOT, 2, 0.5), ("z", 0): (0, BOT, 2, 2),
    ("8 vertices", 0): (0, BOT, 3, 2),
    # 06 mesh
    ("Face A", 0): (940, BOT, 0, 2), ("Face B", 0): (940, BOT, 0, 3), ("Face C", 0): (940, BOT, 0, 4),
    ("8 faces", 0): (940, BOT, 1, 3), ("Veil units", 0): (940, BOT, 2, 2),
    # 07 preview
    ("Colour by f", 0): (1660, BOT, 0, 1), ("Veil preview", 0): (1660, BOT, 1.4, 1),
    # 08 check
    ("Reference", 1): (2240, BOT, 0, 0),
    ("Units", 0): (2240, BOT, 0, 1.5), ("Deconstruct", 0): (2240, BOT, 0, 2.5),
    ("Area", 0): (2240, BOT, 0, 3.5), ("Depth range m", 0): (2240, BOT, 0, 4.5),
    ("Triangles", 0): (2240, BOT, 1, 2.5), ("Total m2", 0): (2240, BOT, 1, 3.5),
    ("Units", 1): (2240, BOT, 2, 1.5), ("Triangles", 1): (2240, BOT, 2, 2.5),
    ("Total m2", 1): (2240, BOT, 2, 3.5), ("Depth range", 1): (2240, BOT, 2, 4.5),
}
for o in list(doc.Objects):
    is_panel = int(isinstance(o, GH_Panel))
    key = (o.NickName, is_panel)
    if key not in LAYOUT:
        continue
    x0, y0, c, r = LAYOUT[key]
    x, y = x0 + c * CW, y0 + 60 + r * RH
    if is_panel:
        w, h = (300, 70) if o.NickName == "Reference" else (160, 40)
        o.Attributes.Pivot = PointF(x, y)
        o.Attributes.Bounds = RectangleF(x, y, w, h)
    else:
        o.Attributes.Pivot = PointF(x, y)
        o.Attributes.ExpireLayout()
        o.Attributes.PerformLayout()

try:
    from Grasshopper.Kernel.Special import GH_Scribble
    title = GH_Scribble()
    title.CreateAttributes()
    title.Text = "Folded Veil  |  free radial field  |  regenerates rhino/FV-folded-veil-reference.3dm"
    title.Attributes.Pivot = PointF(0, -40)
    doc.AddObject(title, False)
except Exception as e:
    print("Title skipped:", e)

for name, colour, members in GROUPS:
    g = GH_Group()
    g.CreateAttributes()
    g.NickName = name
    g.Colour = colour
    for m in members:
        g.AddObject(m.InstanceGuid)
    doc.AddObject(g, False)

# Solve, report, save -----------------------------------------------------
doc.Enabled = True
doc.NewSolution(True)


def values(o, key=None):
    return [getattr(v, "Value", v) for v in out(o, key).VolatileData.AllData(True)]


errors = [o.NickName for o in doc.Objects
          if hasattr(o, "RuntimeMessageLevel") and str(o.RuntimeMessageLevel) == "Error"]
total = values(tot, "R")
dom = values(drange)
print("Units:", values(n))
print("Triangles:", values(nf))
print("Total area m2:", [round(t, 2) for t in total])
print("Depth range:", [str(x) for x in dom])
print("Components with errors:", errors or "none")

io = GH_DocumentIO(doc)
io.SaveQuiet(OUT)
print("Saved:", OUT)
gh.Instances.DocumentServer.AddDocument(doc)
if gh.Instances.ActiveCanvas is not None:
    gh.Instances.ActiveCanvas.Document = doc
