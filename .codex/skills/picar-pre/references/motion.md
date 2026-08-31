# Motion and fort workflows

## Binary contract and interpretation

`motion/fort.py` is authoritative for this repo's little-endian Fortran sequential
unformatted format:

- Header: int32 marker 20, float64 dt, float64 time, int32 node_count, marker 20;
  total 28 bytes (`<iddii`).
- Each node: int32 marker 24, three float64 components, marker 24; total 32 bytes.
- Frame size: `28 + 32 * node_count`. File size must contain whole frames; also
  validate record markers and header/node consistency. A valid first marker does
  not establish that the rest of a downloaded fort is intact.

Physical component order defaults to `xyz`. Map raw columns through
`components_to_physical`/`physical_to_components` when an explicit other order is
used; do not swap axes just to make a plot look plausible.

Default mode is velocity: after each frame `q += v * header.dt`. Selected frame
positions must integrate all preceding frames even if only a few are displayed.
`displacement` means `q_ref + data`; `relative` means reference centroid + data.
Neither is integrated. Frame zero in velocity mode already includes its velocity
increment; the stored reference surface is the pre-step reference.

`ntmax`/steps-per-cycle and total simulated steps are different concepts. Before
blaming EOF on “only one period”, inspect cyclic-motion settings, the reader,
and binary completeness. A past phase-case EOF was a truncated transfer, not
evidence that a 960-step period was wrong.

## Visualization and analysis

Console `/api/fort/preview` displays point-cloud snapshots of the sampled frames,
not lines joining file-order nodes. Gray is sampled motion; red is highlighted.
Earlier polyline/contour fallbacks made spikes and were superseded. Current CLI
2D plotting is also scatter-based; older README outline language is stale.

`sample_frame_indices()` merges uniform samples, highlighted frame and required
frames. `motion_envelope_frame_indices()` scans the integrated sequence for
coordinate min/max frames and maximum displacement-norm frame. Preserve those
frames even with a small requested snapshot count: output count may exceed it.
This captures discrete recorded extrema, not an exact continuous-time envelope.
Do not replace the scan with raw velocity extrema or clip required frames after
sampling. Console currently assumes the usual fort start 41 for preview even
though other APIs expose `fort_start`.

`motion/project.py` provides centroid/centerline harmonic analysis and CSV export.
Midline stations are fixed bins in reference coordinates; default centerline
method `bounds` averages lower/upper station bounds, rather than node-density-
weighted means. Motion plotting uses equal spatial scales where appropriate and
compact JFM-style Matplotlib plots: serif/math labels, no grid, no unnecessary
title. Use `motion/README.md` and CLI help for analysis parameters.

## Import, rotation and Y/Z swap

Fort Replace targets the selected body's file. Add uses the first available
numeric body slot (or the requested starting slot); manual mode requires an
unoccupied target. Upload format is checked before writing, but a surface-node
mismatch is **reported**, not rejected by the import API. Successful upload or
`node_match=True` with no surface is not a complete physical mapping validation.

Ordinary surface transform does not automatically transform fort vectors. Use
`MotionProject.rotate` or the motion CLI for rotation. The dedicated
`/api/geometry/swap-yz-fort` operation swaps selected surface Y/Z coordinates and
physical fort Y/Z components, and reverses triangle winding for the reflection.
It requires matching forts by default and checks nodes before writing. It stages
files but sequential replacement is not a guaranteed rollback transaction; keep
appropriate recoverability for multi-file edits. Check probe coordinates too.

## Periodic resampling

Core: `resample_fort_motion(input_path, output_path,
target_steps_per_cycle=..., source_steps_per_cycle=..., component_order=...)`.
Input and output must differ. The console `/api/fort/resample` wraps this with a
temporary file and then **replaces the selected active fort**; it is not a preview
or an automatic persistent backup. The core function is exported in `motion`,
but do not invent a resample CLI subcommand without checking current help.

Current convention is periodic **end-of-step** samples: phases `1/N ... 1`.
Resampling linearly interpolates within each cycle with wraparound; preserves
cycle duration; writes new dt, time and frame count. It requires a whole number
of source cycles. Default source cycle length is the full file, so multi-cycle
files need an explicit value. Check time uniformity and genuine periodicity for
external files rather than applying this convention blindly. Recheck integrated
motion, closure and phase after interpolation; equal node count is insufficient.
Solver input dt is not automatically changed.

## Undeformed export

```bash
python -B motion/run_motion_tools.py --case-dir path/to/case export-undeformed --output unstruc_surface_undeformed.dat
```

`MotionProject.export_undeformed_surface` integrates through the full fort file
and averages recovered positions per node. It preserves ids, topology, body order
and unselected bodies, reports cycle drift/offset statistics, and rejects writing
over its source surface. The console exposes Export Undeformed in Fort.

This is a cycle-averaged reference estimate, not recovery of a unique stress-free
shape for arbitrary asymmetric/nonperiodic/free-drifting motion. Inspect period
coverage and closure before calling it neutral geometry. Using it as a new solver
reference may require reconciling the initial phase with the motion data.

Historical anchors: binary/point snapshots
`019f005e-e4ad-7692-8f3f-0ba6e6ef7a98`; append, swap and resample
`01a03204-8d70-7163-b6f5-d7bad89fde79`; extreme-frame sampling
`01a04878-dba7-74d2-a6a2-26c0cbebbf33`; undeformed export
`01a01ff4-0ab3-7c11-9ffa-4044ccf777a2`.
