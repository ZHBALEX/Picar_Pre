# Probe parsing, generation and editing

Use the independent `case_editor/probe.py` module. Console endpoints wrap this
module; do not duplicate marker resolution inside drawing code.

## File and reference contract

`probe_in.dat` has a marker section containing count, all body ids, then all
references (not interleaved body/reference pairs), plus a fluid section with
count and XYZ triples. Use `parse_probe_text`, `format_probe_text` and
`write_probe_file` rather than inventing a new format.

For a marker reference resolve in this order:

1. Surface **node id**.
2. Element id, using its triangle centroid.
3. 1-based element index, using its centroid.

Node priority is essential when node and element ids overlap. Element-first
resolution caused visibly wrong 2D probes in an earlier implementation. Preserve
sparse/reordered actual node ids; a row index is not necessarily its node id.
Unresolved bodies/references become warnings/counts and are not assigned guessed
coordinates. The historical 2D fixture had only 2 surface bodies but references
to more bodies: missing references were not permission to fabricate bodies.

## Generation

`generate_surface_marker_probes()` samples uniform X targets in a selected slice:

- `plane_axis=z`: slice near a Z value and select lower/upper Y branches.
- `plane_axis=y`: slice near a Y value and select lower/upper Z branches.
- Determine slice candidates globally before per-X selection. If necessary use
  the globally nearest discrete layer; do not broaden to unrelated layers
  independently at each X target.
- Wider local context identifies both branches, but prefer populated narrow X
  bands for the actual selection. Balance plane and X errors, and pair branches
  to avoid visibly offset upper/lower stations. Do not optimize plane error alone.
- Return actual surface-node coordinates and ids, not synthetic interpolated
  marker positions. Deduplication may reduce the final count.
- `include_endpoints=True` preserves endpoint sampling. False uses
  `linspace(xmin,xmax,n_samples+2)[1:-1]`, leaving the ends inset.

Preview metadata includes requested X, side, X error and plane error. It is not
part of the solver file. Loaded and generated layouts expose slice/spacing
diagnostics through `summarize_probe_layout` and the console summary: slice
errors, X spacing, Euclidean spacing, spacing differences and pair X differences.
For loaded probes some layout values are inferred; do not claim original target
positions or original generator settings can be recovered exactly.

## Editing and saving

Marker XYZ edits snap to the nearest surface node. Connected-edge arrow controls
use screen-relative directions and topology; fluid probes keep exact entered
XYZ. Preview/editing stays in UI state until Save probe_in.dat. Generation can
preserve existing fluid probes. File detection makes the layer available but
does not force it visible on initial load.

After a surface reorder, node remesh, reflection or coordinate transform, check
which references and fluid coordinates require updating. Imported similar-looking
geometry is not proof of identical node numbering; external node-mapping scripts
must establish and validate that correspondence.

## Validation

Run `case_editor/test__probe.py`, which covers sparse ids, node-first resolution,
slice locality, endpoint insets, pair alignment, snapping/stepping, spacing and
payload behavior. For algorithm changes also plot against actual surface nodes
in the selected plane and a second plane: a correct XY projection can hide
incorrect Z-layer selection. Preserve source example data while producing tests.

Historical anchors: module and node-priority correction
`019f9ee6-7299-7232-864c-3463bca0d4dc`; endpoint and loaded diagnostics
`01a01ff4-0ab3-7c11-9ffa-4044ccf777a2`; external geometry/probe node mapping
`019ffd11-a706-7403-a59d-6f227631d5ac`.
