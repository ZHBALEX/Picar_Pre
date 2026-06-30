---
name: picar-pre
description: Work on the Picar_Pre repository, a Python preprocessing toolkit for PICAR solver case directories. Use when editing or explaining geometry/unstruc_surface_in.dat, canonical_body_in.dat, input.dat, x/y/z grid generation, prescribed-motion fort.* files, the local Picar console, or example case-building workflows in this repo.
---

# Picar_Pre Skill

## When To Use

Use this skill for work inside the `Picar_Pre` repository. This project is a PICAR preprocessing assistant organized around one case directory at a time, not a generic Python package.

A case directory commonly contains `input.dat`, `canonical_body_in.dat`, `unstruc_surface_in.dat`, `xgrid.dat`, `ygrid.dat`, optional `zgrid.dat`, optional `fort.*`, and `run.slurm`.

Start from the repository root. The main visual entry point is:

```bash
python -B picar_console.py
python -B picar_console.py path/to/case
```

If port `8765` is occupied, the console chooses another port and prints the exact URL.

## Core Principles

- Prefer existing project APIs and CLIs over direct solver-file edits.
- For small user-facing operations, prefer the CLI entry point.
- For multi-file synchronization or scripted case generation, prefer `CaseProject` or `case_editor.workflow.build_case(config)`.
- Do not use ad hoc string replacement for solver-format files when a project editor/parser exists.
- Verify file paths before assuming similarly named files exist.
- The repository directory is intentionally named `geometry/unstructure_surface`, not `geometry/unstructured_surface`.

## Task Routing

Use this map to choose the first entry point:

| User task | Preferred entry point |
| --- | --- |
| Visual case inspection or console GUI work | `python -B picar_console.py <case>` and files in `case_editor/console/` |
| Whole-case init/edit/report/validate | `case_editor/run_case_editor.py` or `CaseProject` |
| Complete scripted case generation | `case_editor.workflow.build_case(config)` or `example/build_2d_cylinder_case.py` |
| Surface generation, STL import/export, transform, combine, inspect | `geometry/unstructure_surface/run_surface_tools.py` or `SurfaceProject` |
| Grid generation, mesh input, optimization, mesh plots | `python -m mesh.run_mesh_tools` or `MeshProject` |
| Prescribed motion, `fort.*` inspection, rotation, visualization, analysis | `motion/run_motion_tools.py` or `MotionProject` |
| Box trimming of surface plus matching motion records | `trim_surface_fort_box.py`, with extra caution around output overwrite |

For less common options, inspect the relevant CLI help or existing README before inventing flags.

## Critical Coupling Rules

- `input.dat` should be edited through `InputDatEditor` or case-level commands to preserve the line-based format.
- `canonical_body_in.dat` must match `unstruc_surface_in.dat` body count, node count, and element count.
- After body count, node count, element count, or body ordering changes, resync or check `canonical_body_in.dat`.
- CLI body ids are 1-based. Python body lists are 0-based.
- Mesh counts are interval counts. Written grid files contain `intervals + 1` coordinate nodes.
- `zgrid.dat` is optional for 2D cases but should be generated when the mesh has a positive Z range.
- Solver-style 2D surfaces are usually thin side-wall surfaces with triangle elements; flat boundary curves with `elem_count = 0` are only appropriate for sketches/previews or explicitly supported workflows.
- STL conversion/export handles boundary surface triangles, not volume meshes.

## Motion And fort.* Rules

- PICAR prescribed-motion `fort.*` files in this repository use a unified Fortran sequential unformatted format.
- Each frame contains a header record with `20` payload bytes, followed by node-vector records with `24` payload bytes.
- The default component order is physical `xyz`.
- The default motion mode is velocity. Visualization and analysis integrate velocities from the reference `unstruc_surface_in.dat`.
- Do not integrate again if a task explicitly says the values have already been converted to displacement or position.
- Translation of a static surface does not require changing velocity vectors.
- Rotation, scale, reflection, node reorder, node-count change, topology change, or body reorder requires checking or regenerating the matching `fort.*` files.
- Body 1 normally maps to `fort.41`, body 2 to `fort.42`, controlled by `--fort-start`.
- Large `fort.*` files should not be copied or rewritten unless the task explicitly needs it.

## Common Commands

Keep commands targeted; avoid turning this skill into a full manual.

```bash
python case_editor/run_case_editor.py --case-dir path/to/case report
python case_editor/run_case_editor.py --case-dir path/to/case validate
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case inspect --roundtrip
python -m mesh.run_mesh_tools --case-dir path/to/case generate
python -m mesh.run_mesh_tools --case-dir path/to/case inspect
python motion/run_motion_tools.py --case-dir path/to/case inspect
```

For the default one-file generated case:

```bash
python example/build_2d_cylinder_case.py
```

For frontend/editor verification:

```bash
python -B picar_console.py path/to/case
python -m http.server 8765 --bind 127.0.0.1
```

Static editor paths are `geometry/unstructure_surface/editor/` and `mesh/editor/`.

## Validation

Choose checks based on the blast radius:

```bash
python -m py_compile <files you modified>
python -m compileall case_editor geometry/unstructure_surface mesh motion example
python -m pytest mesh/test__mesh_generate.py mesh/test__draw_meshcombine.py
```

For generated or edited cases:

```bash
python case_editor/run_case_editor.py --case-dir path/to/case validate
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case inspect --roundtrip
python -m mesh.run_mesh_tools --case-dir path/to/case inspect
```

For motion changes, run `motion/run_motion_tools.py inspect` and compare `fort.*` node counts against the surface.

If a test dependency such as `pytest` is unavailable, run the closest direct Python check and report the missing dependency.

## Safety

- Avoid silent overwrites of user case directories. Prefer explicit output directories for derived files.
- Do not copy template `fort.*` files unless the user asks for large files or `--include-large`.
- Preserve node ids and topology when only coordinate transforms are intended.
- After modifying surfaces, always consider whether `canonical_body_in.dat`, `input.dat`, grids, or `fort.*` need matching updates.
- `trim_surface_fort_box.py` copies a case and can replace an existing output directory only with `--overwrite`; validate the trimmed case afterward.
- Do not assume an IDE tab means that file exists in the current repository; check with `rg --files` or an explicit file read first.
