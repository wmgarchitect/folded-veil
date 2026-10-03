# LB-01: direct sun hours — guided Grasshopper exercise

Started 1 October 2026. Walid chose to work inside Grasshopper step by step.
This is the week-1 Ladybug exercise in the Q4 plan, not an invented seventh
Folded Veil core session. The PDF remains deferred to the end of the project.

## Question

How many potential direct-sun hours reach the glass plane with and without
the folded veil, under the same orientation, location and sampling?

The existing radial field stays fixed. This is an evaluation of the chosen
design, not evidence that the radial field was derived from solar performance.

## Prepared inputs

Open `exports/sun-hours/FV-LB01-west-facing-inputs.3dm` in Rhino 8.
Units are metres. +Y is north, +Z is up; the facade faces west (-X).
The source IFC read-back was rotated about Z; its geometry was not redesigned.

- `01_Veil_Context`: 88 meshes / 704 triangles, for the context input.
- `02_Glass_TestGrid_250mm`: 88 meshes / 3,168 quad faces at 0.25 m spacing,
  with west-facing normals. Excludes the 6 x 3 m entrance; test area 198 m².

These are inputs only. No Ladybug result has been calculated.

## First step with Walid

1. Open the model in Rhino; use Zoom Extents to see it.
2. Enter `Grasshopper` in the Rhino command line.
3. Search for `LB Direct Sun Hours` on the Grasshopper canvas.
4. Confirm that the component is available before adding or wiring more components.

Rhino 8 and the Ladybug Python packages were found locally, but the availability
of the Grasshopper components has not yet been verified in the UI.

## Subsequent steps — do one at a time

- Set the study location to Istanbul (40.9932922 N, 29.0646267 E), UTC+3.
  This is an assumed study location, not a surveyed project site.
- Begin with 21 June, a full day, at four timesteps per hour.
- Generate vectors with LB SunPath and connect the same vectors and timestep
  to two Direct Sun Hours components.
- Both components use the same glass test meshes. The baseline has no context;
  the second uses the veil meshes as context.
- ~~Set `geo_block_` False and `offset_dist_` 0~~ **Corrected 2026-10-01:** set
  `geo_block_` True and `_offset_dist_` 0.01 m. With `geo_block_` False Ladybug
  drops its facing check, so the west glass counted morning sun from behind
  (15.0 h baseline). The 10 mm offset keeps test points off their own face.
- Input meshes are already divided into faces; LB evaluates mesh faces directly.
  Changing `_grid_size` will not remesh them. Regenerate inputs for a finer grid.
- Check that the baseline is spatially uniform, then compare the shaded case.
  Use a shared legend range and report the area-weighted average and spread.
- Repeat with 21 March and 21 December, and refine the mesh/time sampling before
  treating differences as stable results.

Potential direct sun is geometric visibility; it does not account for clouds,
glazing transmittance or diffuse daylight. This exercise is not a daylight,
thermal-comfort, energy or annual radiation calculation.

## Done when

The Grasshopper definition runs both cases with recorded assumptions, units and
timestep; a checked comparison and figure are saved. Preparing inputs alone
does not complete the exercise.

Official component reference:
https://docs.ladybug.tools/ladybug-primer/components/3_analyzegeometry/direct_sun_hours
