# Picar_Pre

Picar_Pre is a preprocessing toolkit for preparing Picar solver input cases.
The current focus is the solid/body pipeline:

- generate or convert `unstruc_surface_in.dat`
- keep `canonical_body_in.dat` consistent with the surface file
- generate structured grid files
- edit common `input.dat` parameters
- validate the whole case directory before running the solver

The workflow is case-directory based. This follows the same practical idea as
pyvicar-style tools: choose one target case directory, then run generation,
editing, visualization, and validation commands against that directory.

## Repository Layout

```text
example/
  run_case/                         Existing solver input example

geometry/
  unstructure_surface/              Surface generation, STL conversion, transforms, visualization
    run_surface_tools.py            CLI for unstruc_surface_in.dat operations
    surface.py                      Surface read/write/validation
    modeling.py                     Parametric 2D/3D body generation
    stl.py                          STL conversion helpers
    visualize.py                    Optional visualization helpers
    editor/                         Browser-based parametric editor

case_editor/                        Full case input editing workflow
  run_case_editor.py                CLI for case-level operations
  case_project.py                   CaseProject high-level object
  input_editor.py                   input.dat editor
  canonical_body_editor.py          canonical_body_in.dat editor
  mesh_editor.py                    x/y/z grid editor
```

## Main Concepts

### `unstruc_surface_in.dat`

This file stores only body boundary data.

For 2D bodies:

- nodes are boundary marker points
- element count is `0`
- no interior points are written

For 3D bodies:

- nodes are boundary surface points
- elements are boundary surface triangles
- no volume mesh is written

### `canonical_body_in.dat`

This file stores body control/count information. In this toolkit, it can be
generated directly from `unstruc_surface_in.dat`, so a separate canonical body
geometry file is not required.

### `input.dat`

The case editor updates common values while preserving the original line-based
format as much as possible:

- grid counts
- domain lengths
- initial velocity
- Reynolds number and time step
- internal boundary settings

## Quick Start: Build a 2D Cylinder Case

Run all commands from the repository root.

### Easiest: Use the One-File Example

Open and edit:

[example/build_2d_cylinder_case.py](example/build_2d_cylinder_case.py)

The main parameters are kept together:

```python
config = CaseBuildConfig(
    case_dir="example/generated_circle2d_case",
    surface=SurfaceBuildConfig(
        kind="circle",
        params={
            "radius": 0.25,
            "n": 96,
        },
        center=(19.2, 10.0, 0.0),
    ),
    mesh=MeshBuildConfig(
        nx=121,
        ny=81,
        nz=1,
        xout=24.0,
        yout=20.0,
        zout=0.0,
    ),
    input=InputBuildConfig(
        u=1.0,
        v=0.0,
        w=0.0,
        re=1000.0,
        dt=0.001,
    ),
)
```

Run:

```powershell
python example/build_2d_cylinder_case.py
```

This one script does the full workflow:

- copy the template case
- generate `unstruc_surface_in.dat`
- sync `canonical_body_in.dat`
- generate `xgrid.dat`, `ygrid.dat`, and `zgrid.dat`
- update common `input.dat` values
- validate the final case

The generated case is:

```text
example/generated_circle2d_case
```

### Python One-Function API

For the default 2D cylinder:

```python
from case_editor import build_2d_cylinder_case

case = build_2d_cylinder_case(
    case_dir="example/generated_circle2d_case",
    center=(19.2, 10.0, 0.0),
    radius=0.25,
    points=96,
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

### Manual Command-Line Workflow

### 1. Initialize a Case Directory

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/demo_case init
```

This copies the small files from `example/run_case`. Large `fort.*` files are
skipped by default.

### 2. Generate a Boundary-Only 2D Cylinder

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case generate circle --param radius=0.25 --param n=96 --center 19.2 10 0
```

Expected surface:

```text
nodes = 96
elems = 0
center = (19.2, 10.0, 0.0)
radius = 0.25
```

### 3. Sync `canonical_body_in.dat`

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/demo_case canonical --nbody-solid 1 --nbody-membrane 0 --motion-type 3 --zone-max 1
```

This reads the current `unstruc_surface_in.dat` and writes matching body counts.

### 4. Generate Mesh Files

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/demo_case mesh --nx 121 --ny 81 --nz 1 --xout 24 --yout 20 --zout 0
```

This writes:

- `xgrid.dat`
- `ygrid.dat`
- `zgrid.dat`

It also updates the grid counts and domain lengths in `input.dat`.

### 5. Edit Common Solver Input Values

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/demo_case input --u 1.0 --v 0 --w 0 --re 1000 --dt 0.001 --ib-present 1 --body-type 2 --formulation 1
```

### 6. Validate the Case

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/demo_case validate
```

Expected output:

```text
Case Validation
===============
Status: PASS
```

For a full summary:

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/demo_case report
```

## Surface Tool Examples

### Inspect a Surface

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case inspect --roundtrip
```

`--roundtrip` writes the surface to a temporary file, reads it back, and checks
that the arrays are unchanged.

### Visualize a 2D Boundary Surface

For 2D `unstruc_surface_in.dat`, use `body2d`. A 2D body usually has boundary
nodes and `elems = 0`, so this view draws the closed boundary curve from node
order.

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir example/generated_circle2d_case view body2d --body 1 --show-nodes
```

Save the figure to a file:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir example/generated_circle2d_case view body2d --body 1 --show-nodes --save example/generated_circle2d_case/body2d_preview.png
```

If `view mesh` is used on a 2D boundary-only surface, the tool automatically
falls back to the 2D boundary view.

### Visualize a 3D Surface Mesh

For STL-derived or extruded 3D surfaces with triangle elements:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir example/generated_circle2d_case view mesh
```

### Generate a Thin 3D Cylinder Side Wall

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case generate circle --param radius=0.25 --param n=96 --center 19.2 10 0 --thickness 0.1
```

Expected surface:

```text
nodes = 192
elems = 192
```

### Generate a NACA Airfoil Boundary

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case generate naca --param code=0012 --param chord=1.0 --param n=100 --center 6.8 3.0 0
```

### Convert STL Files in a Case Directory

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case convert-stl
```

If no STL paths are provided, all `*.stl` files in the case directory are used.

### Transform a Surface

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case transform --rotate 0 0 10 --translate 0.1 0 0
```

## Browser Editor

The static editor can generate simple parametric bodies and export surface/STL
files.

Start a local server from the repository root:

```powershell
python -m http.server 8765
```

Open:

```text
http://localhost:8765/geometry/unstructure_surface/editor/
```

The editor supports:

- 2D circle, ellipse, rectangle, and NACA boundaries
- optional thin 3D side-wall extrusion
- preview with Three.js when available
- export of `unstruc_surface_in.dat`
- export of STL for 3D side-wall models
- copying an equivalent CLI command

## Python API Examples

### Case-Level Workflow

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

### Surface-Level Workflow

```python
from geometry.unstructure_surface import SurfaceProject

project = SurfaceProject("case_editor/demo_case")
out, bodies = project.generate(
    "circle",
    radius=0.25,
    n=96,
    center=(19.2, 10.0, 0.0),
)

print(out)
print(project.report(bodies=bodies))
```

## Testing Commands

Compile the current Python tools:

```powershell
python -m py_compile case_editor/__init__.py case_editor/input_editor.py case_editor/canonical_body_editor.py case_editor/mesh_editor.py case_editor/case_project.py case_editor/workflow.py case_editor/run_case_editor.py example/build_2d_cylinder_case.py geometry/unstructure_surface/__init__.py geometry/unstructure_surface/surface.py geometry/unstructure_surface/project.py geometry/unstructure_surface/modeling.py geometry/unstructure_surface/stl.py geometry/unstructure_surface/visualize.py geometry/unstructure_surface/run_surface_tools.py geometry/transfer_stlToUnstr.py
```

Validate the generated demo case:

```powershell
python case_editor/run_case_editor.py --case-dir case_editor/demo_case validate
```

Check surface read/write consistency:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir case_editor/demo_case inspect --roundtrip
```

## Notes

- Command-line body ids are 1-based.
- Python body lists are 0-based.
- `body_type = 2` means canonical body in the current example format.
- A 2D body should normally have boundary points and zero triangle elements.
- STL conversion creates 3D boundary surface triangles.
- If a body node order or node count changes, any external files that refer to
  body node ids should be regenerated or checked.
