# Solver formats, synchronization and body mapping

## Preserve the actual file contract

`InputDatEditor` preserves the line-based solver input while editing known
fields. Do not infer schema changes from comment labels alone: different solver
templates may name existing numeric slots differently or omit labels entirely.
Compare numeric record grouping and, for migration, the target solver's reader.
Only `picar-current` is registered in `case_editor/control/__init__.py`; do not
claim automatic support for every PICAR/ViCar version.

Surfaces contain boundary nodes and triangles, not volume mesh nodes. Solver 2D
examples are thin side walls with triangles; zero-element curves are sketches or
explicitly supported special cases. Surface-only inspection must not require a
canonical file.

Use `read_surface`/`write_surface` for semantic edits. If the request is explicitly
an exact-format reorder or append of an external solver template, preserve raw
body blocks, leading blanks, coordinate-line wrapping, column spacing and
negative sentinels. Do not flatten tokens, split a two-count header across lines,
or use `.strip()` on entire files. The permissive Python parser is not proof that
the solver accepts arbitrary formatting. Verify both semantic content and the
target template's physical record layout.

`trim_surface_fort_box.py` is an independent NumPy-based utility: keep the same
node-selection indices for surface and all fort frames; preserve surviving order;
update node/element ids, triangle references and fort header node counts. Its
sentinel parser accepts equal negative triples, not only `-100`. Inspect arguments
instead of running its historical external default case. `--overwrite` replaces
an output directory; validate the exact target first. `trim_dfly_box.py` appeared
in old conversations but is absent from current source (cached bytecode does not
make it a supported entry point).

## Setup Sync

The pipeline is `scan_case_data -> CaseFacts -> PicarCurrentProfile -> SyncPlan`.
Use `CaseProject.scan_data()`, `plan_control_sync()` and `sync_control_files()`, or:

```bash
python -B case_editor/run_case_editor.py --case-dir path/to/case sync --dry-run
python -B case_editor/run_case_editor.py --case-dir path/to/case sync
```

UI name: **Setup Sync**. Primary routes: `/api/setup-sync/plan` and
`/api/setup-sync/apply`; input-sync/control-sync names are compatibility aliases.

Current behavior:

- Present grids supply node counts, uniform/nonuniform flags and `axis.maximum`
  for `xout/yout/zout`. Nonzero starts produce a warning, not a silently subtracted
  domain length. Missing Z preserves the existing Z control values.
- Surface supplies internal-boundary presence and per-body node/element counts.
- Existing canonical records retain motion/zone choices; header reconciliation
  keeps `nbody_membrane` and derives the solid remainder. This is an existing
  convention, not an ability to infer physical body classification from geometry.
- Incomplete canonical records can be repaired by copying the **last real record's
  motion_type and zoneMax** for missing records and using surface counts. Preview
  exposes this assumption. Extra records are not automatically deleted. A wholly
  missing canonical file or no record to copy from blocks this automatic repair.
- Parse only initial contiguous real body records; trailing “example for FBI
  wings” material is documentation, not additional bodies. Motion checks must
  index actual parsed records, never trust a larger header count as list length.
- Orphan forts and fort/surface node-count mismatch block apply. Different fort
  and solver `dt`, non-prescribed canonical motion with fort present, and missing
  fort for prescribed motion are warnings. No automatic Re/BC/solver-dt rewrite.

Do not repeat the outdated rule “any surface/canonical count mismatch blocks”:
missing-record repair was added after that description. Conversely, Setup Sync
does not infer a body permutation from counts and cannot fix a wrong motion
assignment simply because two bodies happen to have the same node count.

## Body order and remove semantics

When a case uses solid-first/membrane-after grouping, verify the target reader
and maintain that ordering across surface blocks, canonical records and fort
names. An external staggered-fish case required old body order `[1,3,2,4]` to
produce solid ids 1/2 and membrane ids 3/4. That is a case-specific permutation,
not a rule for every fish case. Probe body references must follow any permutation.

For order-only changes, retain coordinate/topology content and verify fort hashes
under the new mapping. Use collision-free temporary names for swaps; do not
regenerate or interpolate motion just to reorder it.

Current console operations are independent and mutate the active case:

- Geometry Remove rewrites kept surface bodies; it does not also shift fort files
  or synchronize canonical/probes.
- Fort Remove deletes selected numeric fort files and shifts later body-numbered
  forts down by the number of removed lower ids. For example, remove fort.42:
  old fort.43 becomes fort.42. It does not remove surface bodies.
- Therefore report and verify the resulting body/fort mapping before running the
  solver; a single remove button is not a complete coordinated case edit.

The historical `case_setup.py` / “Save Case Setup” UI was removed from the current
checkout. Do not recommend it based on an old success message or `__pycache__`.
The user also rejected an extra `picar_setup.yaml` manifest as unnecessary for
their existing direct-file workflow; do not silently reintroduce it.

## AMR

Current read/write helpers `_parse_amr_text` and `_format_amr_payload` are inside
`case_editor/run_picar_console.py`, not a separate `amr.py`. The console detects
`amr_in.dat`, renders colored layers, and edits resize, block id/parent,
start/end coordinates and moving flag.

The maintained writer emits **9 fields per block**:
`id parent x1 y1 z1 x2 y2 z2 moving`. The parser accepts >=9 values but retains
only these fields. Some external cases have **11-field** variants. Opening such
a case is not evidence that saving is lossless: the current writer drops extra
columns. Preserve the original and establish the target schema before editing
an extended file through this API. Do not assign meanings to unlabeled fields
from memory.

An AMR plot is a sanity check, not a solver-level nesting/stencil validator.
Compare full **integrated** motion extent to blocks; use runtime-refined grids
for log-index-to-physical-coordinate conversion rather than guessing from base
spacing. Earlier staggered-case hypotheses about AMR extent, normals and fresh
cells were not a confirmed universal diagnosis; do not encode them as fixes.

Historical anchors: sync and rejected alternatives
`019fb904-c631-7b90-ac0b-8f798a049a2d`; AMR implementation
`019f27f6-f300-7f40-bf57-f00af7c84b2b`; external format comparison
`019ff1df-2c8b-7a31-87c5-362661afbc88`; input-label correction
`01a0211f-9af1-7693-aa8c-83f2fb7d261b`; body reorder/format correction
`01a04872-3331-74f1-8afb-34539c810537`.
