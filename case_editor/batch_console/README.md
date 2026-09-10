# Batch Case Setup

This is an isolated workspace for previewing and creating related PICAR case
variants. It does not replace or add a panel to the main Picar Console.

## Launch

From the repository root:

```powershell
python -B batch_console.py path\to\source_case
```

Open the exact URL printed by the server. Its preferred port is `8775`. Restart
the Python process after backend changes; the browser checks the API version and
will reject an outdated server.

## Configure a series

Define one or more rigid body groups. A group accepts an inclusive range such as
`2-4` or a list such as `2,3,4`. All bodies in the group receive the same rigid
transform for a case. A body cannot belong to two groups.

Each group has six series fields:

- X/Y/Z offsets for translation;
- RX/RY/RZ Euler angles in degrees.

A field may contain one value, which is broadcast to every case, or one comma-
or space-separated value per case. All non-singleton fields across all groups
must have the same length.

A group also has an optional `AMR blocks` selector. Use:

- blank/`none` to leave every AMR box fixed;
- `moving` for all blocks with a nonzero `AMR_moving` value;
- `all`; or
- explicit IDs/ranges such as `1,3-4`.

One AMR block cannot belong to two groups. Selected boxes follow the group's
X/Y/Z translation in each case. Because `amr_in.dat` stores axis-aligned start
and end corners, AMR following cannot be combined with rotation.

Example:

```text
Case prefix : tunabot
Body IDs    : 2-4
X offsets   : 0
Y offsets   : 0, 0.1, 0.2, 0.3, 0.4
Z offsets   : 0
RX degrees  : 0
RY degrees  : 0
RZ degrees  : 0
```

The output names are position-derived:

```text
tunabot_BASE
tunabot_YP0p1
tunabot_YP0p2
tunabot_YP0p3
tunabot_YP0p4
```

`P` means positive, `M` means negative, and `p` replaces the decimal point.
Multiple moving groups include body ids in the name, for example
`pair_B1_XP0p1_B2-4_YP0p4`. Duplicate transform combinations are rejected
because they would produce the same directory name.

## Preview

Preview does not write files. Surface geometry stays point-only:

- unchanged bodies are transmitted and drawn once;
- transformed bodies are overlaid per case;
- opacity runs from deep for the first case to light for the last;
- each case can be hidden independently.

The environment is sent once and may be toggled independently in the right-side
toolbar: mesh boundary, inferred dense region, sampled Cartesian grid, and AMR
boxes. A followed AMR box is overlaid per case using the same deep-to-light
opacity order; unchanged boxes are drawn once.

The viewport uses the shared Picar camera projection. It supports ISO, Top, XY,
XZ, and YZ views; drag rotates, Ctrl-drag pans, and the wheel zooms. During an
interaction it temporarily lowers the point budget, then restores the full
sample after interaction.

## Motion-aware rotation

The initial `unstruc_surface_in.dat` is a pre-step surface at one motion phase.
For pitching/heaving motion, its instantaneous centroid need not equal the
cycle's motion center. A rotating group's pivot is therefore computed by:

1. matching each body to `fort.(fort_start + body_id - 1)`;
2. integrating every physical velocity frame from the initial surface;
3. time-averaging every reconstructed node position; and
4. taking the node-weighted center across the bodies in the group.

The same XYZ rotation matrix is applied to the initial surface about that pivot
and to every physical fort velocity vector:

```text
p' = c_motion + R (p - c_motion) + translation
v' = R v
```

For translation-only groups, `fort.*` files are copied byte-for-byte and are not
rewritten. Only nonzero RX/RY/RZ triggers fort transformation. `Fort start`
defaults to 41 and component order defaults to `xyz`. Preview reports the computed pivot and the
maximum cycle drift. The pivot calculation is cached until the source surface,
fort metadata, group membership, fort start, or component order changes.

Nonzero rotation requires every grouped body's fort file to exist, be complete,
and have the same node count as the corresponding surface. These conditions are
validated before any output directory is created.

## Create and verify

**Create Cases** performs the following operation for every variant:

1. copy the complete source case to a new directory;
2. write the transformed `unstruc_surface_in.dat`;
3. translate explicitly selected AMR block corners while preserving other AMR
   columns and comments;
4. rotate each affected fort through a temporary file; and
5. atomically replace that fort inside the new case.

The source case is never written. Existing output directories are never
overwritten. If the batch fails, directories created by that operation are
removed.

Body order, node ids, element topology, and canonical counts do not change.
Grid, solver input, and direct fluid-probe coordinates are copied without
spatial changes. AMR remains unchanged unless its blocks are explicitly assigned
to a translating group, so verify coverage after substantial transformations.

Relevant regression coverage is in
[`case_editor/test__batch_case_setup.py`](../test__batch_case_setup.py).
