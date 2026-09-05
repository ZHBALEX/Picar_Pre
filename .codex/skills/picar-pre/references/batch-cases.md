# Batch case setup

## Scope and entry points

`batch_console.py` launches an isolated batch workspace (preferred port 8775).
It is intentionally separate from the main Picar Console panels and active-case
workflow. The implementation is split between:

- `case_editor/batch_case_setup.py`: parsing, planning, preview payloads, copying,
  surface transforms, motion-center pivots, and fort rotation;
- `case_editor/run_batch_console.py`: local HTTP API and static serving;
- `case_editor/batch_console/`: browser UI;
- `case_editor/console/viewport_core.js`: camera projection shared with the main
  console; and
- `motion/project.py:MotionProject.cycle_average_group_center`: cycle-average
  center recovery used by batch rotation.

Backend/API changes require a server restart. The frontend checks the version
reported by `/api/health`; keep both version strings aligned when changing the
payload contract or pivot semantics.

## Rigid groups and series

One group accepts 1-based body ids as lists or inclusive ranges (`2,3,4` or
`2-4`). Bodies in a group share one rigid transform in each case. A body may not
appear in two groups. X/Y/Z translations and RX/RY/RZ degree rotations are six
ordered series. A singleton broadcasts; every non-singleton series must have the
same case count.

Names are derived from the requested prefix and transform, not ordinal indexes:
positive/negative use `P`/`M` and a decimal point becomes `p`. Examples are
`tunabot_YP0p4`, `tunabot_RZM10`, and, for multiple groups,
`pair_B1_XP0p1_B2-4_YP0p4`. An all-zero case is `prefix_BASE`. Duplicate
transform-derived names block the batch before copying.

Preview is read-only and point-only. Unchanged bodies are sent/drawn once;
changed bodies are repeated per variant. Case opacity runs from deep to light.
Interactive drawing uses a lower temporary point budget. Preserve ISO/Top/XY/
XZ/YZ and main-console rotate/pan/zoom conventions through the shared viewport
core.

## Motion-aware rotation

Never use the global origin or the instantaneous surface centroid as the batch
rotation pivot for prescribed pitching/heaving motion. The surface is the
pre-step geometry at one phase and may not lie at the motion center.

For every rotating group, `cycle_average_group_center` integrates the physical
fort velocity at each frame using that frame's `dt`, averages reconstructed node
positions over all recorded frames, and takes a node-weighted center across group
bodies. Batch transformation is:

```text
p_new = c_motion + R (p_source - c_motion) + translation
v_new = R v_source
```

Use the same XYZ Euler-degree rotation convention as `transform_points` and
`rotate_fort_motion`. Translation does not change velocity vectors. The default
mapping is body `b` to `fort.(41+b-1)`, but the UI/API expose `fort_start` and
physical component order.

Motion-center calculations are cached by resolved source path, surface size and
mtime, group ids, fort start, component order, and each fort's size/mtime. Preview
reports the center and maximum cycle drift. A large drift does not silently
change the algorithm; it signals that the recording may not be a clean complete
cycle and should be inspected.

Every rotated body requires a complete matching fort with the same node count.
Validate this before copying. Rotate each fort to a temporary sibling and replace
only the copied case file after successful output validation. Translation-only
groups do not require fort rewriting.

Case-specific verification for `example/run_case`: bodies 2-4 each have 960
frames and reported closure drift around 2e-14 to 3e-14. Their instantaneous
surface centroid and recovered motion center differ, demonstrating why the fort
trajectory pivot is required. These numbers validate that fixture only.

## Copy and safety boundaries

Creation copies the complete source directory, then changes the copied surface
and rotated forts. It never writes the source, refuses existing variant
directories, validates before copying, and removes directories created by the
failed operation. Preserve body order, node ids, topology, canonical counts, and
the body-to-fort mapping.

Grid, AMR, solver-input, and direct fluid-probe coordinates are copied unchanged.
Do not claim that a large geometry transform automatically reconciles those
spatial files. Large forts make case copying and rotation expensive; preview must
not copy or rewrite them.

Regression coverage is `case_editor/test__batch_case_setup.py`. It includes body
ranges, series broadcasting, naming, non-overwrite behavior, multi-body preview,
motion-center rotation, fort-vector rotation, and missing-fort rejection.
