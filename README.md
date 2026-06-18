# Picar_Pre

Picar_Pre is a Python preprocessing toolkit for preparing PICAR solver cases.
It is organized around one target case directory: generate or convert geometry,
write matching body metadata, generate structured grids, edit common solver
inputs, inspect prescribed-motion files, and validate the case before running
the solver.

The toolkit currently focuses on the solid/body workflow:

- create `unstruc_surface_in.dat` from parametric shapes, STL files, transforms,
  or combined surface files
- keep `canonical_body_in.dat` synchronized with the surface body counts
- generate and inspect `xgrid.dat`, `ygrid.dat`, and `zgrid.dat`
- edit common `input.dat` values without rewriting the whole file format
- inspect, rotate, visualize, and analyze large prescribed-motion `fort.*` files
- validate a complete case directory

## Repository Layout

```text
case_editor/
  Case-level workflow for input.dat, canonical bodies, grids, surfaces, and validation.

geometry/unstructure_surface/
  Boundary-surface pipeline for unstruc_surface_in.dat, including STL conversion,
  parametric body generation, transforms, visualization, and a static browser editor.

mesh/
  Structured Cartesian grid generation, mesh-input optimization, inspection, and
  1D/2D/3D grid visualization.

motion/
  Prescribed-motion fort.* tools for inspection, rotation, visualization, and
  harmonic motion analysis.

example/
  Example cases and the one-file 2D cylinder case builder.
```

Detailed module documentation:

- [case_editor/README.md](case_editor/README.md)
- [geometry/unstructure_surface/README.md](geometry/unstructure_surface/README.md)
- [mesh/README.md](mesh/README.md)
- [motion/README.md](motion/README.md)

## Main Files

### `unstruc_surface_in.dat`

Stores body boundary data only. For solver-style 2D bodies, this toolkit writes
a very thin side-wall surface: several spanwise layers of boundary points plus
triangle elements. Flat boundary curves with `elem_count = 0` are also supported
for sketches and previews. For 3D bodies, the file stores boundary surface
points and triangle elements, not a volume mesh.

### `canonical_body_in.dat`

Stores body control/count information. In this toolkit it can be generated from
the current `unstruc_surface_in.dat`, so a separate canonical geometry source is
not required for the supported workflow.

### `input.dat`

Stores solver and mesh parameters. The case editor updates common values such as
grid counts, domain lengths, initial velocity, Reynolds number, time step, and
internal-boundary settings while preserving the line-based format as much as
possible.

### `xgrid.dat`, `ygrid.dat`, `zgrid.dat`

Structured Cartesian grid coordinate files. The `mesh/` tools can generate them
from compact mesh parameters, inspect multigrid-friendly count properties, and
visualize grid spacing before or after generation.

### `fort.*`

Large prescribed-motion files. These live in a separate `motion/` workflow
because they can be hundreds of MB and should not be rewritten during ordinary
surface edits. Translation of a static surface does not require motion edits,
but rotation should rotate the stored motion vectors too.

## Quick Start

Run commands from the repository root.

Launch the unified local console:

```powershell
python -B case_editor/run_picar_console.py --case-dir example/run_case --port 8765
```

Open the printed local URL. The console loads `unstruc_surface_in.dat` and
`xgrid.dat`/`ygrid.dat`/`zgrid.dat` into one shared 3D scene, so geometry and
mesh can be checked together. By default it draws surface points plus the mesh
boundary and dense-region box; sampled full-grid and triangle overlays can be
enabled only when needed.

The easiest complete workflow is the 2D cylinder case builder:

```powershell
python example/build_2d_cylinder_case.py
```

Edit the configuration near the top of
[example/build_2d_cylinder_case.py](example/build_2d_cylinder_case.py) to change
the output directory, geometry, mesh, and flow parameters. The script:

- copies a template case
- generates `unstruc_surface_in.dat`
- syncs `canonical_body_in.dat`
- generates `xgrid.dat`, `ygrid.dat`, and `zgrid.dat`
- updates common `input.dat` values
- validates the final case

The default generated case is:

```text
example/generated_circle2d_case
```

## One-Function Python Workflow

```python
from case_editor import build_2d_cylinder_case

case = build_2d_cylinder_case(
    case_dir="example/generated_circle2d_case",
    center=(19.2, 10.0, 0.005),
    radius=0.25,
    points=600,
    thickness=0.01,
    layers=3,
)

print(case.report())
```

For full control:

```python
from case_editor import CaseBuildConfig, MeshBuildConfig, SurfaceBuildConfig, build_case

config = CaseBuildConfig(
    case_dir="example/my_case",
    surface=SurfaceBuildConfig(
        kind="naca",
        params={"code": "0012", "chord": 1.0, "n": 100},
        center=(6.8, 3.0, 0.0),
    ),
    mesh=MeshBuildConfig(nx=121, ny=81, nz=1, xout=24.0, yout=20.0, zout=0.0),
)

case = build_case(config)
print(case.report())
```

## Manual Case Workflow

### 1. Initialize a case directory

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/demo_case init
```

This copies the small files from `example/run_case`. Large `fort.*` files are
skipped by default.

### 2. Generate or convert a surface

Generate a solver-style thin 2D cylinder:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case generate circle --param radius=0.25 --param n=600 --param layers=3 --center 19.2 10 0.005 --thickness 0.01
```

Convert STL files already inside the case directory:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case convert-stl
```

Export a triangulated `unstruc_surface_in.dat` back to STL:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case export-stl --output surface.stl
```

Combine separate surface files into one multi-body surface:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case combine path/to/body1/unstruc_surface_in.dat path/to/body2/unstruc_surface_in.dat
```

### 3. Sync canonical body metadata

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/demo_case canonical --nbody-solid 1 --nbody-membrane 0 --motion-type 3 --zone-max 1
```

For multi-body surfaces, omit `--nbody-solid` to use the number of bodies in
`unstruc_surface_in.dat`.

### 4. Generate grid files

Case-level uniform grid generation:

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/demo_case mesh --nx 121 --ny 81 --nz 1 --xout 24 --yout 20 --zout 0
```

Mesh-package generation from a compact mesh input:

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples generate
```

Generate with multigrid-friendly dense-length optimization:

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples generate --optimize
```

Write an optimized mesh input file without overwriting the original:

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples optimize-input
```

The Excel-style preferred-count table method is available with:

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples optimize-input --method table --ideal-delta 0.0033
```

### 5. Edit common solver input values

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/demo_case input --u 1.0 --v 0 --w 0 --re 1000 --dt 0.001 --ib-present 1 --body-type 2 --formulation 1
```

### 6. Validate or report the case

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/demo_case validate
python case_editor/run_case_editor.py --case-dir case_editor/demo_case report
```

## Surface Tools

Inspect a surface and verify read/write consistency:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case inspect --roundtrip
```

Visualize a solver-style 2D body by projecting the thin side-wall surface to XY:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case view body2d --body 1 --show-nodes
```

Save the preview:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case view body2d --body 1 --show-nodes --save body2d_preview.png
```

Transform existing bodies:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case transform --body 1 --rotate 0 0 10 --translate 0.1 0 0
```

The surface browser editor can generate simple parametric bodies and export
surface/STL files:

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

Open:

```text
http://127.0.0.1:8765/geometry/unstructure_surface/editor/
```

Keep the PowerShell server running while using the editor. For a 3D cylinder,
choose `Circle / 2D cylinder`, enable `3D`, set `Thickness`, then export
`unstruc_surface_in.dat`. See
[`geometry/unstructure_surface/README.md`](geometry/unstructure_surface/README.md)
for the full 3D cylinder quick start.

## Mesh Tools

Inspect existing grid files:

```powershell
python -m mesh.run_mesh_tools --case-dir example/run_case inspect
```

Visualize generated grid files:

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples view --mode 2d --plane xy --save mesh/examples/grid_preview.png --no-show
```

Visualize 1D spacing curves:

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples view --mode 1d --axis all --save mesh/examples/spacing.png --no-show
```

Preview a mesh input before grid files exist:

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples view --source input --input input.dat --save input_preview.png --no-show
```

The mesh browser editor creates mesh-generator `input.dat` files:

```powershell
python -m http.server 8765
```

Open:

```text
http://localhost:8765/mesh/editor/
```

Use `python -m mesh.run_mesh_tools --case-dir path/to/case generate` afterward
to create `xgrid.dat`, `ygrid.dat`, and `zgrid.dat`.

## Motion Tools

Inspect prescribed-motion files and compare node counts with the surface file:

```powershell
python motion/run_motion_tools.py --case-dir example/run_case inspect
python motion/run_motion_tools.py --case-dir example/run_case_2D inspect --body 1
```

Rotate stored motion vectors after rotating a surface:

```powershell
python motion/run_motion_tools.py --case-dir example/run_case rotate --rotate 0 0 10 --body 1 --output-dir motion_outputs
```

Visualize motion envelopes:

```powershell
python motion/run_motion_tools.py --case-dir example/run_case_2D view 2d --body 1 --frame 240 --samples 18 --save body1_motion.png --no-show
python motion/run_motion_tools.py --case-dir example/run_case view 3d --body 4 --frame 240 --samples 8 --save body4_motion.png --no-show
```

Fit harmonic motion equations:

```powershell
python motion/run_motion_tools.py --case-dir example/run_case_2D analyze centroid --body 1
python motion/run_motion_tools.py --case-dir example/run_case_2D analyze centerline --body 1 --axis x --bins 60 --output centerline_body1.csv
```

By default, motion values are interpreted as physical `xyz` marker velocities
and integrated from `unstruc_surface_in.dat`. Use `--component-order` and
`--motion-mode` for files with different conventions.

## Python APIs

Case-level workflow:

```python
from case_editor import CaseProject

case = CaseProject("case_editor/demo_case")
case.copy_template()
case.generate_mesh(nx=121, ny=81, nz=1, xout=24, yout=20, zout=0)
case.sync_canonical_from_surface(nbody_solid=1, motion_type=3)

editor = case.input_editor()
editor.set_initial_velocity(1.0, 0.0, 0.0)
editor.set_re_dt(1000.0, 0.001)
editor.set_internal_boundary(present=1, body_type=2, formulation=1)
editor.write()

print(case.report())
```

Surface workflow:

```python
from geometry.unstructure_surface import SurfaceProject

project = SurfaceProject("case_editor/demo_case")
out, bodies = project.generate(
    "circle",
    radius=0.25,
    n=600,
    layers=3,
    center=(19.2, 10.0, 0.005),
    thickness=0.01,
)

print(out)
print(project.report(bodies=bodies))
```

Mesh workflow:

```python
from mesh import MeshProject

project = MeshProject("mesh/examples")
mesh, optimization_report = project.generate(optimize=True)
print(project.report())
```

## Testing and Checks

Compile the current Python tools:

```powershell
python -m py_compile case_editor/__init__.py case_editor/input_editor.py case_editor/canonical_body_editor.py case_editor/mesh_editor.py case_editor/case_project.py case_editor/workflow.py case_editor/run_case_editor.py example/build_2d_cylinder_case.py geometry/unstructure_surface/__init__.py geometry/unstructure_surface/surface.py geometry/unstructure_surface/project.py geometry/unstructure_surface/modeling.py geometry/unstructure_surface/stl.py geometry/unstructure_surface/visualize.py geometry/unstructure_surface/run_surface_tools.py geometry/transfer_stlToUnstr.py mesh/__init__.py mesh/io.py mesh/generation.py mesh/optimization.py mesh/project.py mesh/visualize.py mesh/run_mesh_tools.py motion/__init__.py motion/fort.py motion/project.py motion/visualize.py motion/analysis.py motion/run_motion_tools.py
```

Validate a generated case:

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/demo_case validate
```

Check surface read/write consistency:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case inspect --roundtrip
```

Inspect mesh counts and spacing:

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples inspect
```

## Notes

- `unstruc_surface_in.dat` reading uses a NumPy token-stream fast path for the
  standard numeric solver format, with the line-aware parser kept as fallback
  for unusual files.
- Command-line body ids are 1-based; Python body lists are 0-based.
- `body_type = 2` means canonical body in the current example format.
- Solver-style 2D examples use thin side-wall boundary surfaces with triangle
  elements.
- Flat boundary curves with zero elements are supported for sketches and quick
  previews.
- STL conversion creates 3D boundary surface triangles.
- Mesh count fields are treated as interval counts; written grid files contain
  `total intervals + 1` coordinate nodes.
- If body node order, node count, or topology changes, any external files that
  refer to body node ids, including matching `fort.*` files, should be checked
  or regenerated.
