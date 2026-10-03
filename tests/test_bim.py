"""Integration checks, including deliberately corrupted IFC files.

Run: python tests/test_bim.py
"""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import bim


class BimRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.source = Path(cls.temp.name) / 'source.ifc'
        bim.export(cls.source)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_round_trip_geometry_and_schedule(self):
        report, records = bim.verify(self.source)
        self.assertEqual(report['triangles'], 704)
        self.assertEqual(report['properties_matched_to_csv'], 1144)
        self.assertEqual(report['validation_issues'], 0)
        self.assertEqual(len(records), 88)

    def test_changed_property_is_detected(self):
        model = bim.ifcopenshell.open(str(self.source))
        prop = next(p for p in model.by_type('IfcPropertySingleValue') if p.Name == 'depth_mm')
        prop.NominalValue.wrappedValue += 10
        path = Path(self.temp.name) / 'wrong-property.ifc'
        model.write(str(path))
        with self.assertRaises(AssertionError):
            bim.verify(path)

    def test_displaced_unit_is_detected(self):
        model = bim.ifcopenshell.open(str(self.source))
        location = model.by_type('IfcPlate')[0].ObjectPlacement.RelativePlacement.Location
        location.Coordinates = tuple(value + 1 for value in location.Coordinates)
        path = Path(self.temp.name) / 'wrong-position.ifc'
        model.write(str(path))
        with self.assertRaises(AssertionError):
            bim.verify(path)

    def test_stable_identity_on_reexport(self):
        second = Path(self.temp.name) / 'second.ifc'
        bim.export(second)
        a = bim.ifcopenshell.open(str(self.source))
        b = bim.ifcopenshell.open(str(second))
        self.assertEqual({p.Tag: p.GlobalId for p in a.by_type('IfcPlate')},
                         {p.Tag: p.GlobalId for p in b.by_type('IfcPlate')})


if __name__ == '__main__':
    unittest.main()
