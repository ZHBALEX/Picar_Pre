---
name: picar-pre
description: Develop, inspect, or prepare PICAR cases with Picar_Pre. Use for its local console, surface/STL/OBJ geometry, grids, input/canonical Setup Sync, AMR, probes, prescribed-motion fort files, and associated phase-case workflows. Not a general PICAR solver or CFD postprocessing skill.
---

# Picar_Pre

Picar_Pre is a local, case-directory-oriented preprocessing toolkit. Existing
solver files remain the source of truth; it is not a solver runner or a replacement
file format. Run commands from the repository root unless stated otherwise.

```bash
python -B picar_console.py
python -B picar_console.py path/to/case
```

The default case is `example/run_case`, not the 2D example. The server binds to
`127.0.0.1`; if port 8765 is occupied, use the exact URL it prints.

## Project memory and continuity

Treat this skill and its references as the maintained record of prior Picar_Pre
collaboration. They capture verified repository facts, user workflow preferences,
accepted design decisions, rejected alternatives, known regressions, and relevant
external-case lessons. Use them to continue development without asking the user to
reconstruct earlier conversations.

Apply this evidence order when records disagree:

1. Current implementation, tests, and files in the active checkout.
2. The user's latest explicit request and corrections.
3. This skill's maintained guidance and references.
4. Repository documentation and historical conversation anchors.

Conversation history is evidence, not current state. Re-check code before acting,
especially after a revert or later commit. Keep case-specific observations labeled
as such; do not promote them to universal PICAR rules. Keep proposed, rejected,
removed, and implemented behavior distinct. A historical task/thread id is only a
provenance clue and is never proof that code is still present.

When future work reveals a durable, non-obvious fact that would change later
development decisions, update the narrowest relevant reference in the same change
when practical. Record the reason and boundary, not a chronological chat summary.
Do not store secrets, credentials, personal data, transient paths, speculative
hypotheses, or generic coding advice. Avoid duplicating facts across references;
route to one maintained source from the task table instead.

## Working conventions

- Keep changes modular and small, with English code comments. Preserve unrelated
  panels and controls when adding a feature to one panel.
- Prefer existing parsers, project APIs, and CLIs. Do not casually reformat
  solver files or replace the workflow with an extra manifest/configuration layer.
- For simple operations use the relevant CLI; for coordinated case building use
  `CaseProject` or `case_editor.workflow.build_case(config)`.
- The real directory is `geometry/unstructure_surface`, not `unstructured_surface`.
- Check current code and `git status`: some recent console/motion features may
  exist as uncommitted changes. A historical response saying “implemented” is not
  proof that a feature survived a revert or exists in the current checkout.
- Preserve examples and source cases during testing. Use temporary cases for
  writes; loading, previewing, and inspecting must not imply permission to save.

## Task routing

Read only the reference relevant to the work; paths mentioned inside references
are repository-relative unless explicitly identified as external.

| Task | Entry point and reference |
| --- | --- |
| Console UI, viewport, imports/exports, mesh display or generation | `case_editor/run_picar_console.py`, `case_editor/console/`; [console and mesh](references/console-mesh.md) |
| Surface generation/conversion/transform | `geometry/unstructure_surface/run_surface_tools.py`, `SurfaceProject`; [formats and synchronization](references/formats-sync.md) |
| Setup Sync, input/canonical, body mapping, AMR compatibility | `case_editor/control/`, `case_editor/data_facts.py`; [formats and synchronization](references/formats-sync.md) |
| Probe generation, positioning, spacing, file parsing | `case_editor/probe.py`; [probes](references/probes.md) |
| fort parsing, preview, resample, Y/Z swap, neutral surface | `motion/fort.py`, `motion/project.py`, `motion/visualize.py`; [motion](references/motion.md) |
| Previous batch pitching/heaving phase cases | External `foil_pitching_PhaseChange` project; [phase workflow](references/phase-workflow.md) |
| Whole-case generation | `case_editor.workflow.build_case(config)`, `example/build_2d_cylinder_case.py` |
| Box trimming of geometry and matching fort nodes | `trim_surface_fort_box.py`; [formats and synchronization](references/formats-sync.md) |

For uncommon flags inspect CLI help. Repository READMEs contain some older
descriptions (notably motion outlines, mesh-input naming, and sync blockers);
resolve disagreement against implementation and regression tests.

## Cross-file invariants

- `canonical_body_in.dat` body/node/element counts must match the surface.
- Body ids in CLIs/APIs are 1-based; Python body lists are 0-based. The usual
  mapping is body `b` to `fort.(fort_start+b-1)`, with `fort_start=41`.
- Surface body order, canonical records, fort numbering, and probe body/node
  references must stay consistent. Current Geometry Remove and Fort Remove are
  separate actions, not an automatic coordinated transaction.
- Mesh-generation counts are **interval counts**; grid arrays and input sync use
  **coordinate-node counts**, normally intervals + 1.
- Missing `zgrid.dat` can be valid for 2D. Positive Z extent should generate Z
  coordinates even with zero dense-Z intervals. Do not invent missing mesh data
  merely to show a geometry-only case.
- Default fort semantics are physical `xyz` **velocities**, integrated using each
  frame's `dt` from the reference surface. Never treat raw velocity extrema as
  displacement or integrate known displacement data again.
- Translation of a surface does not change velocity vectors. Rotation, scaling,
  reflection, topology/node-order changes, and body reordering require checking
  the matching motion and probes. Importing STL/OBJ can renumber nodes.

## Verification

Choose checks for the affected behavior, rather than running every expensive
operation. Documentation-only work does not require launching a solver or GUI.

```bash
python -B case_editor/run_case_editor.py --case-dir path/to/case report
python -B case_editor/run_case_editor.py --case-dir path/to/case validate
python -B case_editor/run_case_editor.py --case-dir path/to/case sync --dry-run
python -B geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case inspect --roundtrip
python -B -m mesh.run_mesh_tools --case-dir path/to/case inspect
python -B motion/run_motion_tools.py --case-dir path/to/case inspect
```

Relevant regressions:

- `case_editor/test__control_sync.py`: narrow writes, incomplete canonical records.
- `case_editor/test__probe.py`: node references, slice sampling, editing, diagnostics.
- `case_editor/test__console_imports.py`: append/replace, swap, resample, extreme frames.
- `mesh/test__mesh_generate.py`: reference stretching, rounded dense inference, Z.
- `mesh/test__draw_meshcombine.py`: mesh plotting.

Use `python -B -m pytest -p no:cacheprovider <relevant files>` when pytest is
available. If unavailable, report that and run suitable test functions with
temporary-directory fixtures; do not claim pytest passed. UI verification also
needs served HTML/JS/API consistency and visual/interaction checks when relevant.

## Scope and safety

Large fort files should not be copied/rewritten for unrelated surface inspection.
Template initialization skips them unless requested (`--include-large`). Confirm
which operations write the active case; importing and removing are not previews.
Keep derived outputs separate, and verify exact targets before overwrite.

Do not revive historical cloud-hosting, manifest, case-setup, or solver-submission
proposals as implemented features. The references preserve useful decisions and
known limitations, not authorization to modify external cases or submit jobs.
