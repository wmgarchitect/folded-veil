# Session 05: review together

Updated 1 October 2026. IFC4 export and published Speckle model complete.

[Open Folded Veil in Speckle](https://app.speckle.systems/projects/0f83cf24a9/models/5a3b3c7dd5).
Version `7e698df178`; Public access confirmed in project settings.

## Files

- `../exports/FV-05-free-radial.ifc`: actual IFC4 exchange file.
- `../exports/FV-05-validation.json`: saved validation summary.
- `../exports/FV-05-readback.json`: vertices, triangles and fabrication data
  read from the IFC, used by the inspection snapshot.
- `../exports/FV-05-review.html`: offline snapshot; open directly in a browser.
- `../media/FV-05-ifc-review.jpg`: checked preview, FV-088 selected.

## First comparison

Choose these units in the review dropdown, then repeat in Speckle after upload.

| Property | FV-004, beside entrance | FV-088, top corner |
|---|---:|---:|
| Depth | 120 mm | 900 mm |
| Aperture half-diagonal | 652.5 mm | 315 mm |
| Internal bend angle | 136.56 degrees | 139.68 degrees |
| Blank width | 1500 mm | 1500 mm |
| Blank height | 763.7 mm | 1199.2 mm |
| Pieces per unit | 4 | 4 |

The first question: can another viewer preserve the shape **and** these
fabrication values, with correct units? Confirm the 6 x 3 m entrance remains
open, the facade spans 18 x 12 m, and individual units remain selectable.

`ARC_Fabrication` contains all 13 CSV columns. `ARC_Design` states the variant,
exact field value, developed/open area and modelling limits. Geometry is
stored in metres; `_mm` properties explicitly reference millimetres; angles
explicitly reference degrees. `bay_col` is the original CSV name for the
zero-based **unit** column, 0 through 11, not the six-bay index.

The 26 free families have non-contiguous identifiers inherited from nest.py's
shared cache. Do not infer family count from the highest T number.
`family_five` is a proposed grouping; this export is not the rationalised
five-family geometry.

## Remaining evidence for session 05

- [x] Reproducible IFC4 export with properties and explicit units.
- [x] Schema/EXPRESS validation and geometry readback.
- [x] Original geometry tests and corruption-detection tests pass.
- [x] Local inspection snapshot and visual check.
- [x] Speckle upload and independent viewer spot check of geometry and properties.
- [x] Save the public model link, version, source hash and screenshots.
- [ ] Walid's own visual feedback (model is open beside the chat).
- [x] Prepare a 40-second project film with actual Speckle viewer capture and
  a labelled property-panel excerpt (publishing follow-up, 1 October).

The week-1 BIM deliverable is complete. Walid's feedback is a follow-up review,
not a missing IFC/Speckle export. The publishing package remains unpublished.

Speckle shows 94 elements: 88 plates plus six spatial containers. Both sample
units above matched their source values. Both ARC property sets are visible,
including the modelling limits. Evidence is saved in
`../exports/FV-05-speckle-review.json` and `../media/FV-05-speckle-*.jpg`.
The Speckle check was visual and sample-based; no claim is made that every
imported coordinate or explicit property-unit object was independently tested.

These are conceptual midsurfaces, with no thickness, bend allowance,
connections, glass or frame. Alloy and thickness remain unspecified.

## Implementation references

- [IfcOpenShell geometry creation](https://docs.ifcopenshell.org/ifcopenshell-python/geometry_creation.html)
- [IfcOpenShell validation](https://docs.ifcopenshell.org/autoapi/ifcopenshell/validate/index.html)

The exporter pins IfcOpenShell 0.8.5 and validates against its IFC4 schema;
online documentation may describe newer versions.
