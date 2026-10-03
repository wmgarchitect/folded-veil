"""Prepare Rhino inputs for the guided Ladybug exercise. No sun analysis is run.

Source IFC coordinates use -Y as outward. Rotate clockwise by 90 degrees
about Z so outward is west (-X), with world +Y = north and +Z = up.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.deps'))
import rhino3dm as rh


def main():
    source = ROOT / 'exports/FV-05-readback.json'
    units = json.loads(source.read_text(encoding='utf-8'))
    out = ROOT / 'exports/sun-hours'
    out.mkdir(exist_ok=True)
    model = rh.File3dm()
    model.Settings.ModelUnitSystem = rh.UnitSystem.Meters
    model.Settings.ModelAbsoluteTolerance = 0.001
    layers = []
    for name, colour in [('01_Veil_Context', (190, 156, 95, 255)),
                         ('02_Glass_TestGrid_250mm', (114, 177, 203, 255))]:
        layer = rh.Layer()
        layer.Name, layer.Color = name, colour
        layers.append(model.Layers.Add(layer))

    def add(mesh, layer_index, name):
        mesh.Normals.ComputeNormals()
        assert mesh.IsValid
        attributes = rh.ObjectAttributes()
        attributes.LayerIndex = layer_index
        attributes.Name = name
        attributes.SetUserString('study', 'Potential direct sun hours; not yet calculated')
        attributes.SetUserString('orientation', 'West-facing; +Y north; +Z up')
        model.Objects.AddMesh(mesh, attributes)

    for unit in units:
        mesh = rh.Mesh()
        for x, y, z in unit['vertices']:
            mesh.Vertices.Add(y, -x, z)
        for a, b, c in unit['faces']:
            mesh.Faces.AddFace(a, b, c)
        add(mesh, layers[0], unit['id'] + '_veil')

        # One test mesh per occupied unit, excluding the entrance.
        # Winding gives west-facing normals (-X); 6 x 6 faces per unit.
        x0 = min(p[0] for p in unit['vertices'])
        z0 = min(p[2] for p in unit['vertices'])
        grid = rh.Mesh()
        for iz in range(7):
            for ix in range(7):
                grid.Vertices.Add(0, -(x0 + ix * .25), z0 + iz * .25)
        for iz in range(6):
            for ix in range(6):
                a = iz * 7 + ix
                grid.Faces.AddFace(a, a + 1, a + 8, a + 7)
        add(grid, layers[1], unit['id'] + '_glass_grid')

    path = out / 'FV-LB01-west-facing-inputs.3dm'
    assert model.Write(str(path), 8)
    check = rh.File3dm.Read(str(path))
    context = [o for o in check.Objects if o.Attributes.LayerIndex == layers[0]]
    grids = [o for o in check.Objects if o.Attributes.LayerIndex == layers[1]]
    assert len(context) == len(grids) == 88
    assert sum(len(o.Geometry.Faces) for o in context) == 704
    assert sum(len(o.Geometry.Faces) for o in grids) == 3168
    assert all(n.X < -.999 for o in grids for n in o.Geometry.Normals)
    assert check.Settings.ModelUnitSystem == rh.UnitSystem.Meters
    manifest = {
        'status': 'Inputs prepared. Grasshopper setup and analysis pending.',
        'model': path.name, 'rhino3dm': rh.__version__,
        'source': 'exports/FV-05-readback.json',
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'units': 'metres', 'orientation': 'west-facing; +Y north; +Z up',
        'transform': '(x, y, z) -> (y, -x, z)',
        'context_meshes': 88, 'context_triangles': 704,
        'test_meshes': 88, 'test_faces': 3168, 'grid_size_m': .25,
        'test_area_m2': 198, 'entrance_excluded': True,
        'location_assumption': {'city': 'Istanbul', 'latitude': 40.99329222222222,
                                'longitude': 29.064626666666665, 'time_zone': 3},
        'limits': 'No site context, thickness or glazing optical properties. No results yet.'
    }
    (out / 'inputs.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
