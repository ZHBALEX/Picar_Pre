# Console and mesh development

## Architecture and interaction

The entry point is `picar_console.py`; HTTP routes and payload helpers live in
`case_editor/run_picar_console.py`. The integrated viewport in
`case_editor/console/app.js` uses a Canvas 2D context with custom projections.
Do not assume it is a Three.js scene because old requests mentioned Three.js;
standalone geometry/mesh editors are separate implementations.

Keep surface, mesh bounds/dense region, AMR, probes, and motion in the shared
viewport when switching Setup/Geometry/Mesh/AMR/Probe/Fort panels. Geometry-only
loading is supported; no default mesh preview should obscure small geometry when
actual grid files are absent. Probe file detection enables availability, not an
automatically checked probe layer.

Established view behavior:

- 3D normal drag rotates; Ctrl-drag pans. XY/XZ/YZ planar views drag to pan.
- Reset restores the ISO orientation and clears pan/zoom.
- ISO starts with XY as ground and Z up, with a right-handed coordinate system.
  Top is still a 3D camera preset, not a replacement for explicit 2D plane mode.
- Keep point rendering and sampled grid overlays responsive. Current sampling
  caps are implementation details, not solver resolution.
- Do not put a large shared file/drop section ahead of every tab's own controls.

After Python API changes a running server needs a restart; new static files can
be served by an old Python process. Inspect `/api/health` and the actual listening
URL when new buttons reach old handlers. Do not stop unrelated Python processes
or change the default example to make a test work. Historical request to remove
redundant timeout/version-guard scaffolding was about that implementation, not
permission to omit file safety checks.

## Imports and exports

Geometry Import replaces the current surface; Append Body appends uploaded
STL/OBJ/DAT bodies. DAT append uses `_save_surface_payload`, not raw concatenation.
The backend normalizes `mode=replace|append` (`add` is an alias). Changes write
the active case, and should be followed by count/mapping checks.

STL/OBJ paths go through `SurfaceProject.convert_stl/convert_obj`. OBJ support is
currently present despite an earlier reverted attempt. Conversion deduplicates
rounded vertices and remaps faces, so it does not preserve a pre-existing fort or
probe node-order mapping. The fallback handles polygon fan triangulation and OBJ
face index forms including negative indices; it is not a general remesher.

Export JSON and Export PNG belong in Setup, below Scene Layers. PNG captures the
current canvas. JSON `version: 1` from `buildPlotExport()` carries view, layers,
canvas dimensions and actual surface/mesh/AMR/probe/fort/motion data, including
unselected layers' data when loaded. Large arrays and pretty-printing explain
large line counts. It is not merely a camera preset and not a solver-file backup:
surface serialization does not retain all original node-id/format metadata.
A standalone Python renderer was proposed, but is not currently a repo feature.

## Mesh origin, generation and preview

The UI's Mesh input is `mesh_input_twolayers.dat`, not solver `input.dat`.
Supported candidate names are listed in `MESH_INPUT_CANDIDATES`; the legacy
`input.dat` candidate does not make solver input and mesh input interchangeable.

Preserve the intended separation:

1. Edit/load mesh parameters; optionally optimize counts; preview.
2. Save mesh input without requiring successful grid generation.
3. Generate XYZ, performing generation validation and writing grids.

`/api/mesh/preview` allows `repair_degenerate=True`; `/api/mesh/generate` uses
strict generation. Saving input should not reset current controls by reloading
old grid-derived parameters. Explicitly loading mesh input should replace controls.
On initial case load, actual X/Y grids take precedence over candidate input files.

`make_axis_nodes()` produces local `[0,length]` coordinates; console controls
carry absolute starts separately in `origin`. `_shift_mesh()` must be applied
equally to preview and generation. Dense centers inferred by
`_axis_params_from_grid()` are relative to the loaded axis start. Never silently
recenter an asymmetric dense region or move a nonzero-start grid to the origin.
The legacy mesh-input text does not serialize the console's separate origin;
do not promise an origin-preserving input-only round trip without checking it.

Use `mesh/generation.py:smooth_stretch_sizes`, which matches the reference PICAR
two-layer generator, rather than replacing stretch regions with a fixed geometric
ratio. Keep console and standalone mesh-editor preview algorithms aligned with
backend generation. `mesh/optimization.py` has dense/balanced priorities and
preferred counts; preserve dense-spacing and axis-independence assumptions.

Dense inference uses `DENSE_SPACING_TOLERANCE=0.02` for rounded spacing and
`DENSE_UNIFORM_RATIO=1.05` for nearly uniform axes in the current implementation.
The tolerance avoids fragmenting a real dense band after 8-decimal coordinate
output. Keep frontend and backend tolerances consistent and run both the precise
reference-grid and rounded-grid regressions when changing them.

Known discrepancy reproduced during the 2026-08-30 documentation audit:
`test_console_infers_reference_two_layer_dense_region` fails with the current
2% inference threshold. Expected center/length/count are `10.9/2.2656/192`, but
inference returns approximately `10.923817336/2.337038483/198`, absorbing nearby
stretch intervals. The reference **generation** and rounded-grid tests pass.
Do not claim all dense-inference regressions pass or tighten the threshold
without preserving rounded-grid behavior. This audit did not change the algorithm.

Missing/flat Z must still render a 2D dense rectangle. Positive `Lz` generates
Z even when interval counts are all zero (at least the two endpoints). A single
indexed Z-grid row is one coordinate, not two values; preserve this parsing fix.

## Regression scenarios

Use temporary cases for import/save tests. Check geometry-only, X/Y-only grids,
nonzero origins, asymmetric dense regions, nearly uniform and rounded grids,
and positive-Z/zero-Z-count cases. Check actual output coordinates, not only an
attractive preview. UI changes should preserve normal rotate/Ctrl-pan/Reset,
panel visibility, and the shared viewport.

Historical anchors: console integration `019edbe0-eca4-7bf2-af4e-9cfa9b568cf0`;
reference mesh `019f6337-6781-7aa2-b458-cd30bd91a5d7`; view controls
`019fb353-bad9-7b42-99a5-8458cd768597`; export
`019fd8dd-0d9f-7eb3-b32c-2b018570fded`; rounded 2D grids
`019fee46-db06-7192-8b7d-7062b88d29dd`; OBJ
`019ffc88-10ec-76c1-b80c-584d036dda2f`.
