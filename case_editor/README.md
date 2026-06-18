# Picar Case Editor

This package provides a lightweight case-directory workflow for Picar
preprocessing files. It follows the same high-level pattern as pyvicar: create a
case object around one directory, then edit or generate the files that belong to
that case.

The implementation keeps Picar's current input files unchanged. It does not
replace the solver format; it only gives a cleaner Python and command-line layer
for generating and checking:

- `input.dat`
- `canonical_body_in.dat`
- `xgrid.dat`, `ygrid.dat`, `zgrid.dat`
- `unstruc_surface_in.dat`

## Modules

- `input_editor.py`
  Formatting-preserving edits for common `input.dat` values.

- `canonical_body_editor.py`
  Read/write helpers for the body counts and motion records in
  `canonical_body_in.dat`.

- `mesh_editor.py`
  Structured Cartesian grid read/write/generation helpers.

- `case_project.py`
  Directory-level workflow that connects input, mesh, canonical body, and
  unstructured surface files.

- `run_case_editor.py`
  Command-line interface for the case workflow.

## Command-Line Workflow

Run commands from the repository root.

## Local Console

Start the browser-based preprocessing console from the terminal:

```powershell
python -B case_editor/run_picar_console.py --case-dir case_editor/test_case --port 8765
```

The console serves only local files from this repository session. It loads the
current `unstruc_surface_in.dat`, `xgrid.dat`, `ygrid.dat`, and `zgrid.dat` into
one shared 3D scene. The default view is performance-oriented: surface points,
mesh boundary, dense-region box, and coordinate axes/ticks. Sampled full-grid
and surface-triangle overlays are optional layers.

## One-File Example

The easiest entry point is:

```powershell
python example/build_2d_cylinder_case.py
```

Edit the config at the top of that file to change geometry, mesh, flow
parameters, and output directory. It calls `build_case(config)` from
`case_editor.workflow`.

## Python One-Function Workflow

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
        kind="circle",
        params={"radius": 0.25, "n": 600, "layers": 3},
        center=(19.2, 10.0, 0.005),
        thickness=0.01,
    ),
    mesh=MeshBuildConfig(nx=121, ny=81, nz=1, xout=24.0, yout=20.0, zout=0.0),
)

case = build_case(config)
print(case.report())
```

## Manual Command-Line Workflow

### 1. Create an Editable Case

Copy the small template files from `example/run_case`:

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/test_case init
```

Large `fort.*` files are skipped by default. To copy them too:

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/test_case init --include-large
```

Use another template directory:

```powershell
python case_editor/run_case_editor.py --case-dir my_case init --template example/run_case
```

### 2. Generate or Convert the Surface

The case editor expects `unstruc_surface_in.dat` to exist before canonical body
sync. Use the unified surface tools for this step.

Solver-style thin 2D cylinder:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/test_case generate circle --param radius=0.25 --param n=600 --param layers=3 --center 19.2 10 0.005 --thickness 0.01
```

Thin 3D side-wall cylinder:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/test_case generate circle --param radius=0.25 --param n=96 --center 19.2 10 0 --thickness 0.1
```

Convert STL files already inside the case directory:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/test_case convert-stl
```

### 3. Sync `canonical_body_in.dat`

Create canonical body counts from the current surface file:

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/test_case canonical --nbody-solid 1 --nbody-membrane 0 --motion-type 3 --zone-max 1
```

For multi-body surfaces, omit `--nbody-solid` to use the number of bodies in
`unstruc_surface_in.dat`.

### 4. Generate Mesh Files

Generate uniform grid files and update `input.dat` counts/domain lengths:

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/test_case mesh --nx 121 --ny 81 --nz 1 --xout 24 --yout 20 --zout 0
```

### 5. Edit Common `input.dat` Values

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/test_case input --u 1.0 --v 0 --w 0 --re 1000 --dt 0.001 --ib-present 1 --body-type 2 --formulation 1
```

### 6. Validate the Whole Case

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/test_case validate
```

A valid case prints:

```text
Case Validation
===============
Status: PASS
```

For a full summary:

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/test_case report
```

## Python Workflow

```python
from case_editor import CaseProject

case = CaseProject("case_editor/test_case")
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

## Design Notes

- `CaseProject` is the high-level entry point.
- The surface pipeline remains in `geometry/unstructure_surface`.
- `canonical_body_in.dat` can be generated from only `unstruc_surface_in.dat`;
  no separate canonical body geometry is required.
- Solver-style 2D unstructured surfaces are thin side-wall boundary surfaces
  with triangle elements, matching `example/run_case_2D`.
- Flat 2D boundary curves with zero elements are supported for quick sketches.
- 3D unstructured surfaces are boundary-only surface points and triangle
  elements.
- The current mesh generator is uniform. Nonuniform segmented grids can be added
  on top of `GridAxis` without changing the case workflow.
