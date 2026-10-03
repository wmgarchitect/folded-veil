"""Session 05: export the free radial veil to IFC4 and verify the saved file.

python src/bim.py
Geometry: metres, X across the facade, Y outward negative, Z up. No site
georeferencing, sheet thickness, fixings, glazing or frame is invented.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / '.deps').is_dir():
    sys.path.insert(0, str(ROOT / '.deps'))

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.validate
import ifcopenshell.util.element
import ifcopenshell.util.placement
import veil as v
import field as fl
import nest as nz

NAMESPACE = uuid.UUID('f9dc647a-9cb0-4fc7-9340-8fe9b70fc3d7')
INTEGER_FIELDS = {'bay_col', 'row', 'pieces'}
TEXT_FIELDS = {'unit', 'family_free', 'family_five'}


def guid(name):
    return ifcopenshell.guid.compress(uuid.uuid5(NAMESPACE, name).hex)


def schedule_rows():
    with (ROOT / 'fabrication_schedule.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for key, value in row.items():
            row[key] = (value if key in TEXT_FIELDS else
                        int(value) if key in INTEGER_FIELDS else float(value))
    if [r['unit'] for r in rows] != [f'FV-{i:03d}' for i in range(1, 89)]:
        raise ValueError('Schedule must contain FV-001 through FV-088 in order.')
    return rows


def source_units():
    rows = schedule_rows()
    field = fl.radial_field()
    five_depths = fl.rationalise(fl.depths_from(field), 5)
    # Preserve nest.py's existing labels: its shared cache includes both
    # variants, so the 26 free families have non-contiguous T numbers.
    five_field = [(d - v.D_MIN) / (v.DMAX_DEFAULT - v.D_MIN) for d in five_depths]
    families = sorted({round(f, 9) for f in field + five_field})
    five_levels = sorted(set(five_depths))
    for row, (col, level), f, five in zip(rows, v.unit_positions(), field, five_depths):
        u = v.unit(f)
        x0, y0, x1, y1 = nz.bbox(nz.piece_outline(f))
        # Fail on stale data rather than attaching another variant's properties.
        expected = {'bay_col': col, 'row': level, 'pieces': 4,
                    'f': round(f, 4), 'depth_mm': round(u.d * 1000, 1),
                    'aperture_r_mm': round(u.r * 1000, 1),
                    'bend_deg': round(v.piece_fold_angle(u), 2),
                    'family_free': f'T{families.index(round(f, 9)) + 1:02d}',
                    'family_five': f'F{five_levels.index(five) + 1}',
                    'blank_w_mm': round((x1 - x0) * 1000, 1),
                    'blank_h_mm': round((y1 - y0) * 1000, 1),
                    'blank_area_m2': round(v.metal_area(u) / 4, 4)}
        if any(row[k] != value for k, value in expected.items()):
            raise ValueError(f"Schedule is stale for {row['unit']}")
        yield row, u, ((col + .5) * 1.5, 0., (level + .5) * 1.5)


def export(path):
    model = ifcopenshell.file(schema='IFC4')
    def entity(kind, **kwargs):
        return model.create_entity(kind, **kwargs)
    def root(kind, key, **kwargs):
        return entity(kind, GlobalId=guid(key), **kwargs)
    def placement(offset=(0., 0., 0.), parent=None):
        axis = entity('IfcAxis2Placement3D', Location=entity('IfcCartesianPoint', Coordinates=offset))
        return entity('IfcLocalPlacement', PlacementRelTo=parent, RelativePlacement=axis)
    def aggregate(parent, children):
        root('IfcRelAggregates', 'aggregate:' + parent.GlobalId,
             RelatingObject=parent, RelatedObjects=children)

    metre = entity('IfcSIUnit', UnitType='LENGTHUNIT', Name='METRE')
    mm = entity('IfcSIUnit', UnitType='LENGTHUNIT', Prefix='MILLI', Name='METRE')
    area = entity('IfcSIUnit', UnitType='AREAUNIT', Name='SQUARE_METRE')
    radian = entity('IfcSIUnit', UnitType='PLANEANGLEUNIT', Name='RADIAN')
    degree = entity('IfcConversionBasedUnit',
        Dimensions=entity('IfcDimensionalExponents', LengthExponent=0, MassExponent=0,
            TimeExponent=0, ElectricCurrentExponent=0, ThermodynamicTemperatureExponent=0,
            AmountOfSubstanceExponent=0, LuminousIntensityExponent=0),
        UnitType='PLANEANGLEUNIT', Name='degree', ConversionFactor=entity('IfcMeasureWithUnit',
            ValueComponent=entity('IfcPlaneAngleMeasure', wrappedValue=math.pi / 180), UnitComponent=radian))
    context = entity('IfcGeometricRepresentationContext', ContextType='Model',
        CoordinateSpaceDimension=3, Precision=1e-7, WorldCoordinateSystem=placement().RelativePlacement)
    body = entity('IfcGeometricRepresentationSubContext', ContextIdentifier='Body', ContextType='Model',
        ParentContext=context, TargetView='MODEL_VIEW')
    project = root('IfcProject', 'project', Name='Folded Veil | free radial gradient',
        RepresentationContexts=[context], UnitsInContext=entity('IfcUnitAssignment', Units=[metre, area, radian]))
    site = root('IfcSite', 'site', Name='Concept site (not georeferenced)', ObjectPlacement=placement(), CompositionType='ELEMENT')
    building = root('IfcBuilding', 'building', Name='18 x 12 m facade study',
        ObjectPlacement=placement(parent=site.ObjectPlacement), CompositionType='ELEMENT')
    aggregate(project, [site])
    aggregate(site, [building])
    storeys = []
    for i in range(4):
        storeys.append(root('IfcBuildingStorey', f'storey:{i}', Name=f'Level {i}', Elevation=i * 3.,
            CompositionType='ELEMENT', ObjectPlacement=placement((0., 0., i * 3.), building.ObjectPlacement)))
    aggregate(building, storeys)
    plates = []
    by_storey = [[] for _ in storeys]

    def pset(plate, name, properties):
        values = []
        for key, value in properties.items():
            unit = None
            if key.endswith('_mm'):
                kind, unit = 'IfcLengthMeasure', mm
            elif key.endswith('_m2'):
                kind, unit = 'IfcAreaMeasure', area
            elif key.endswith('_deg'):
                kind, unit = 'IfcPlaneAngleMeasure', degree
            else:
                kind = 'IfcBoolean' if isinstance(value, bool) else 'IfcInteger' if isinstance(value, int) else 'IfcReal' if isinstance(value, float) else 'IfcLabel'
            values.append(entity('IfcPropertySingleValue', Name=key,
                NominalValue=entity(kind, wrappedValue=value), Unit=unit))
        props = root('IfcPropertySet', plate.Tag + ':' + name, Name=name, HasProperties=values)
        root('IfcRelDefinesByProperties', plate.Tag + ':rel:' + name, RelatedObjects=[plate], RelatingPropertyDefinition=props)

    for row, u, offset in source_units():
        level = row['row'] // 2
        coords = entity('IfcCartesianPointList3D', CoordList=u.points)
        mesh = entity('IfcTriangulatedFaceSet', Coordinates=coords, Closed=False,
            CoordIndex=[tuple(j + 1 for j in tri) for tri in u.faces])
        rep = entity('IfcShapeRepresentation', ContextOfItems=body,
            RepresentationIdentifier='Body', RepresentationType='Tessellation', Items=[mesh])
        plate = root('IfcPlate', row['unit'], Name=row['unit'], Tag=row['unit'],
            PredefinedType='USERDEFINED', ObjectType='Folded veil unit (four sheet pieces)',
            Description='Eight triangular midsurface faces; no sheet thickness or connections modelled.',
            ObjectPlacement=placement((offset[0], offset[1], offset[2] - level * 3.), storeys[level].ObjectPlacement),
            Representation=entity('IfcProductDefinitionShape', Representations=[rep]))
        pset(plate, 'ARC_Fabrication', row)
        pset(plate, 'ARC_Design', {
            'Variant': 'Free radial gradient; 26 families', 'FieldValueExact': u.f,
            'DevelopedArea_m2': v.metal_area(u), 'ApertureArea_m2': v.open_area(u),
            'Porosity': v.porosity(u), 'TriangleCount': len(u.faces),
            'ThicknessModelled': False, 'FiveFamilyGeometryApplied': False,
            'FiveFamilyNote': 'family_five is proposed grouping only; geometry uses family_free.',
            'BlankNote': 'blank dimensions and area describe ONE of four pieces; bend allowance excluded.'})
        plates.append(plate)
        by_storey[level].append(plate)
    for storey, children in zip(storeys, by_storey):
        root('IfcRelContainedInSpatialStructure', 'contains:' + storey.GlobalId,
             RelatingStructure=storey, RelatedElements=children)
    material = entity('IfcMaterial', Name='Aluminium (concept; alloy and thickness unspecified)', Category='metal')
    root('IfcRelAssociatesMaterial', 'material', RelatedObjects=plates, RelatingMaterial=material)
    path.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(path))


def verify(path):
    """Read disk, validate EXPRESS, compare properties and tessellated geometry."""
    model = ifcopenshell.open(str(path))
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(model, logger, express_rules=True)
    if logger.statements:
        raise ValueError('IFC validation failed: ' + str(logger.statements[:3]))
    assert model.schema == 'IFC4'
    plates = {plate.Tag: plate for plate in model.by_type('IfcPlate')}
    assert len(plates) == 88
    assert len(model.by_type('IfcBuildingStorey')) == 4
    all_guids = [item.GlobalId for item in model.by_type('IfcRoot')]
    assert len(all_guids) == len(set(all_guids))
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    total_area, triangles, max_error = 0., 0, 0.
    records = []
    for row, u, offset in source_units():
        plate = plates[row['unit']]
        assert plate.GlobalId == guid(row['unit'])
        props = ifcopenshell.util.element.get_psets(plate)
        for key, value in row.items():
            assert props['ARC_Fabrication'][key] == value, (plate.Tag, key)
        mesh = plate.Representation.Representations[0].Items[0]
        assert mesh.Closed is False
        assert list(mesh.CoordIndex) == [tuple(j + 1 for j in tri) for tri in u.faces]
        for actual, expected in zip(mesh.Coordinates.CoordList, u.points):
            assert math.dist(actual, expected) < 1e-10
        container = ifcopenshell.util.element.get_container(plate)
        assert container.Name == f"Level {row['row'] // 2}"
        transform = ifcopenshell.util.placement.get_local_placement(plate.ObjectPlacement)
        assert math.dist(transform[:3, 3], offset) < 1e-10
        for rel in plate.IsDefinedBy:
            if rel.RelatingPropertyDefinition.Name != 'ARC_Fabrication':
                continue
            for prop in rel.RelatingPropertyDefinition.HasProperties:
                if prop.Name.endswith('_mm'):
                    assert prop.Unit.Name == 'METRE' and prop.Unit.Prefix == 'MILLI'
                elif prop.Name.endswith('_m2'):
                    assert prop.Unit.Name == 'SQUARE_METRE'
                elif prop.Name.endswith('_deg'):
                    assert prop.Unit.Name == 'degree'
        shape = ifcopenshell.geom.create_shape(settings, plate)
        vertices = list(zip(*[iter(shape.geometry.verts)] * 3))
        faces = list(zip(*[iter(shape.geometry.faces)] * 3))
        expected_points = [tuple(p[i] + offset[i] for i in range(3)) for p in u.points]
        assert len(vertices) == 8 and len(faces) == 8
        error = max(min(math.dist(p, q) for q in vertices) for p in expected_points)
        assert error < 1e-7, (plate.Tag, error)
        max_error = max(max_error, error)
        measured = sum(v.tri_area(vertices[a], vertices[b], vertices[c]) for a, b, c in faces)
        assert math.isclose(measured, v.metal_area(u), abs_tol=1e-9)
        total_area += measured
        triangles += len(faces)
        records.append({'id': plate.Tag, 'guid': plate.GlobalId, 'properties': props['ARC_Fabrication'],
                        'vertices': vertices, 'faces': faces})
    report = {'file': path.name, 'schema': model.schema, 'ifcopenshell': ifcopenshell.version,
              'validation_issues': len(logger.statements), 'units': len(plates),
              'triangles': triangles, 'pieces_described': sum(r['pieces'] for r in schedule_rows()),
              'free_families': len({r['family_free'] for r in schedule_rows()}),
              'properties_matched_to_csv': 88 * len(schedule_rows()[0]),
              'developed_area_m2': total_area, 'max_vertex_error_m': max_error,
              'geometry_engine_readback': 'passed',
              'scope': 'Local IFC validation; external viewer evidence is in FV-05-speckle-review.json.',
              'limits': 'Open midsurfaces; no thickness, bend allowance, fixings, glass or frame. Not fabrication-ready.'}
    return report, records


def main():
    path = ROOT / 'exports' / 'FV-05-free-radial.ifc'
    export(path)
    report, records = verify(path)
    (path.parent / 'FV-05-validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (path.parent / 'FV-05-readback.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
