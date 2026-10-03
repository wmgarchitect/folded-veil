"""Build the Folded Veil reference Rhino file from the IFC read-back.

The file is the project's Rhino reference, not a design source. Geometry
comes from exports/FV-05-readback.json, so it is the published model
exactly. The Grasshopper definition regenerates the same veil and is
checked against this file.

Coordinates as in the IFC: metres, +X along the facade, -Y outward,
+Z up. Facade 18 x 12 m, glass plane at Y = 0.

Run:  python src/make_project_3dm.py
"""
from pathlib import Path
import csv
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
try:
    import rhino3dm as rh
except ImportError:
    sys.path.insert(0, str(ROOT / '.deps'))
    import rhino3dm as rh

LAYERS = [
    ('01_Veil_FreeRadial', (190, 156, 95)),
    ('02_Glass', (114, 177, 203)),
    ('03_Unit_Frames', (90, 90, 90)),
    ('04_Entrance', (200, 70, 60)),
    ('05_Slab_Edges_Indicative', (150, 150, 150)),
    ('06_Labels', (40, 40, 40)),
]
SLAB_T, SLAB_D = 0.25, 1.0   # indicative slab edge only, not designed


def tri_area(a, b, c):
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    x = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    return .5 * math.sqrt(sum(t * t for t in x))


def main():
    source = ROOT / 'exports' / 'FV-05-readback.json'
    units = json.loads(source.read_text(encoding='utf-8'))
    out = ROOT / 'rhino' / 'FV-folded-veil-reference.3dm'

    model = rh.File3dm()
    model.Settings.ModelUnitSystem = rh.UnitSystem.Meters
    model.Settings.ModelAbsoluteTolerance = 0.001
    idx = {}
    for name, (r, g, b) in LAYERS:
        layer = rh.Layer()
        layer.Name, layer.Color = name, (r, g, b, 255)
        if name == '06_Labels':
            layer.Visible = False
        idx[name] = model.Layers.Add(layer)

    def attrs(layer, name, strings=None):
        a = rh.ObjectAttributes()
        a.LayerIndex = idx[layer]
        a.Name = name
        for k, v in (strings or {}).items():
            a.SetUserString(k, str(v))
        return a

    def polyline(pts):
        return rh.PolylineCurve([rh.Point3d(*p) for p in pts])

    def box_mesh(x0, x1, y0, y1, z0, z1):
        m = rh.Mesh()
        for z in (z0, z1):
            for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                m.Vertices.Add(x, y, z)
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            m.Faces.AddFace(*f)
        m.Normals.ComputeNormals()
        return m

    veil_area = 0.0
    for u in units:
        p = u['properties']
        m = rh.Mesh()
        for x, y, z in u['vertices']:
            m.Vertices.Add(x, y, z)
        for a, b, c in u['faces']:
            m.Faces.AddFace(a, b, c)
            veil_area += tri_area(u['vertices'][a], u['vertices'][b], u['vertices'][c])
        m.Normals.ComputeNormals()
        assert m.IsValid, u['id']
        strings = {k: v for k, v in p.items() if k != 'id'}
        strings['ifc_guid'] = u['guid']
        strings['source'] = 'FV-05-readback.json'
        model.Objects.AddMesh(m, attrs('01_Veil_FreeRadial', u['id'], strings))

        x0 = p['bay_col'] * 1.5
        z0 = p['row'] * 1.5
        sq = [(x0, 0, z0), (x0 + 1.5, 0, z0), (x0 + 1.5, 0, z0 + 1.5), (x0, 0, z0 + 1.5)]
        g = rh.Mesh()
        for q in sq:
            g.Vertices.Add(*q)
        g.Faces.AddFace(0, 1, 2, 3)   # normal -Y, outward
        g.Normals.ComputeNormals()
        model.Objects.AddMesh(g, attrs('02_Glass', u['id'] + '_glass', {'unit': u['id']}))
        model.Objects.AddCurve(polyline(sq + [sq[0]]), attrs('03_Unit_Frames', u['id'] + '_frame'))
        model.Objects.AddTextDot(u['id'], rh.Point3d(x0 + .75, 0, z0 + .75),
                                 attrs('06_Labels', u['id'] + '_label'))

    ent = [(6, 0, 0), (12, 0, 0), (12, 0, 3), (6, 0, 3), (6, 0, 0)]
    model.Objects.AddCurve(polyline(ent), attrs('04_Entrance', 'Entrance_6x3m'))
    for lvl in range(1, 5):
        z = lvl * 3.0
        model.Objects.AddMesh(box_mesh(0, 18, 0, SLAB_D, z - SLAB_T, z),
                              attrs('05_Slab_Edges_Indicative', f'Slab_L{lvl}',
                                    {'note': 'Indicative slab edge for reading floors. Not designed.'}))

    assert model.Write(str(out), 8)

    # Read back and check against the source and the schedule.
    check = rh.File3dm.Read(str(out))
    veil = [o for o in check.Objects if o.Attributes.LayerIndex == idx['01_Veil_FreeRadial']]
    glass = [o for o in check.Objects if o.Attributes.LayerIndex == idx['02_Glass']]
    assert len(veil) == len(glass) == 88
    faces = sum(len(o.Geometry.Faces) for o in veil)
    assert faces == 704
    by_id = {u['id']: u for u in units}
    worst = 0.0
    for o in veil:
        src = by_id[o.Attributes.Name]['vertices']
        for i, v in enumerate(o.Geometry.Vertices):
            worst = max(worst, max(abs(v.X - src[i][0]), abs(v.Y - src[i][1]), abs(v.Z - src[i][2])))
    with (ROOT / 'fabrication_schedule.csv').open(newline='') as s:
        schedule_area = sum(4 * float(r['blank_area_m2']) for r in csv.DictReader(s))
    depths = [float(by_id[o.Attributes.Name]['properties']['depth_mm']) for o in veil]
    assert check.Settings.ModelUnitSystem == rh.UnitSystem.Meters
    report = {
        'model': 'rhino/' + out.name,
        'source': 'exports/FV-05-readback.json',
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'units': 'metres', 'axes': '+X along facade, -Y outward, +Z up',
        'layers': [n for n, _ in LAYERS],
        'veil_meshes': len(veil), 'veil_triangles': faces, 'glass_panels': len(glass),
        'max_vertex_deviation_m': worst,
        'veil_area_m2_mesh': round(veil_area, 2),
        'veil_area_m2_schedule': round(schedule_area, 2),
        'depth_mm_min_max': [min(depths), max(depths)],
        'limits': 'Open midsurfaces. No metal thickness, bend allowances, joints, glazing '
                  'build-up or supports. Slab edges are indicative only.',
    }
    (ROOT / 'rhino' / 'FV-folded-veil-reference.json').write_text(
        json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
