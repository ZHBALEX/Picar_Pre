# Unstructured Surface Pipeline

This folder contains the unified preprocessing pipeline for Picar
`unstruc_surface_in.dat` files. The design is target-directory based: load a
case directory once, then inspect, convert STL files, generate simple parametric
bodies, transform bodies, write the surface file, and visualize results.

The style follows the same high-level idea used by `pyvicar`: create a case-like
context around a directory, then call operations on that context instead of
passing file paths into every low-level function.

## Modules

- `surface.py`
  Core surface format: `SurfaceBody`, read/write, validate, summary, transforms,
  sampling. No plotting dependencies.

- `project.py`
  Target-directory workflow: `SurfaceProject(case_dir)`.

- `stl.py`
  STL conversion and box cutting helpers.

- `modeling.py`
  Simple parametric body generation: circle, ellipse, rectangle, NACA 4-digit.

- `visualize.py`
  Optional PyVista/Matplotlib visualization.

- `run_surface_tools.py`
  Unified command-line interface.

- `editor/`
  Static browser editor for parametric boundary/surface generation and export.

## Surface Format

Each body is stored as:

```text
node_count elem_count

node_id x y
z

elem_id n1 n2 n3

-100.000  -100.000  -100.000
```

Multi-body files repeat this block. The final sentinel is allowed.

## Command-Line Workflow

Run commands from the repository root. If `--case-dir` is omitted, the default
target is:

```text
example/run_case
```

### 1. Inspect the Target Directory Surface

```powershell
python geometry/unstructure_surface/run_surface_tools.py inspect
```

The terminal report is printed as narrow body cards. Each axis line shows:

```text
x range : min .. max  span=value  [-----*-----]
```

The `*` marks the body center relative to that axis range.

With round-trip write/read verification:

```powershell
python geometry/unstructure_surface/run_surface_tools.py inspect --roundtrip
```

Use another target directory:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case inspect
```

### 2. Convert STL Files in the Target Directory

If STL files are in the target directory, no STL path is needed:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case convert-stl
```

Convert selected STL files:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case convert-stl body.stl fin.stl
```

Write to a different output name:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case convert-stl body.stl --output unstruc_surface_body.dat
```

Append converted STL bodies to an existing surface:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case convert-stl wing.stl --append
```

### 3. Combine Existing Surface Files

Combine separate surface files into one multi-body `unstruc_surface_in.dat`:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case combine path/to/cylinder/unstruc_surface_in.dat path/to/foil/unstruc_surface_in.dat
```

Append bodies from another surface file to the current case surface:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case combine path/to/another_body/unstruc_surface_in.dat --append
```

Relative input paths are resolved from the current working directory first, then
from `--case-dir`.

### 4. Generate a Simple Parametric Body

Generate an ellipse:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case generate ellipse --param rx=0.5 --param ry=0.2 --param n=128 --center 0 0 0
```

Generate a circle:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case generate circle --param radius=0.3 --param n=96
```

With no thickness, this creates a flat boundary curve with `elem_count=0`. For
solver-style 2D cases matching `example/run_case_2D`, use a thin layered
side-wall surface:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case generate circle --param radius=0.25 --param n=600 --param layers=3 --center 19.2 10 0.005 --thickness 0.01
```

This produces:

```text
nodes = 1800
elems = 2400
```

Generate a rectangle:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case generate rectangle --param width=1.0 --param height=0.2
```

Generate a NACA 4-digit airfoil:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case generate naca --param code=0012 --param chord=1.0 --param n=100
```

Extrude a 2D boundary into a thin 3D side-wall surface:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case generate naca --param code=0012 --param chord=1.0 --thickness 0.02
```

Apply transform during generation:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case generate ellipse --param rx=0.5 --param ry=0.2 --rotate 0 0 10 --translate 6.8 3.0 3.0
```

Append generated body to an existing surface:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case generate circle --param radius=0.1 --append
```

### 5. Transform Existing Surface Bodies

Transform all bodies:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case transform --rotate 0 0 5 --translate 0.1 0 0 --scale 1.0
```

Transform selected body ids only:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case transform --body 1 --body 3 --rotate 0 0 5
```

Write transformed output to a new file:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case transform --body 1 --translate 0.1 0 0 --output unstruc_surface_shifted.dat
```

### 6. Visualize

Show all triangle meshes:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case view mesh
```

Show all point clouds:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case view points
```

Show one body as points:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case view body --body 1
```

Show one body as a 2D XY projection:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case view body2d --body 1 --show-nodes
```

For 2D boundary-only bodies, `body2d` draws the closed boundary curve from node
order even when `elem_count=0`.

Save the 2D view:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case view body2d --body 1 --show-nodes --save body2d_preview.png
```

Sample and highlight upper/lower points:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/case view sample --body 1 --target 4.0 --plane-axis y
```

## Python Workflow

### Load a Project

```python
from geometry.unstructure_surface import SurfaceProject

project = SurfaceProject("example/run_case")
print(project.report())
```

### Convert STL Files in a Directory

```python
from geometry.unstructure_surface import SurfaceProject

project = SurfaceProject("path/to/case")
out, bodies = project.convert_stl()
print(out)
print(len(bodies))
```

### Generate and Append a Parametric Body

```python
from geometry.unstructure_surface import SurfaceProject

project = SurfaceProject("path/to/case")
out, bodies = project.generate(
    "naca",
    append=True,
    code="0012",
    chord=1.0,
    n=100,
    thickness=0.02,
    translate=(6.8, 3.0, 3.0),
)
```

### Transform Existing Bodies

```python
from geometry.unstructure_surface import SurfaceProject

project = SurfaceProject("path/to/case")
out, bodies = project.transform(body_ids=[1], rotation=(0, 0, 5), output="shifted.dat")
```

### Direct Low-Level Read/Write

```python
from geometry.unstructure_surface import read_surface, write_surface, transform_body

bodies = read_surface("example/run_case/unstruc_surface_in.dat")
bodies[0] = transform_body(bodies[0], rotation=(0, 0, 5))
write_surface("example/run_case/unstruc_surface_rotated.dat", bodies)
```

## STL Helper Script

`geometry/transfer_stlToUnstr.py` remains as a compatibility helper, but the
preferred interface is `run_surface_tools.py convert-stl`.

Cut an STL:

```powershell
python geometry/transfer_stlToUnstr.py cut --stl input.stl --box -20 20 -20 20 -10 10 --out-stl cut.stl
```

Convert one STL:

```powershell
python geometry/transfer_stlToUnstr.py convert --stl input.stl --out unstruc_surface_in.dat
```

## Browser Editor

Open the static editor:

```powershell
python -m http.server 8765
```

Then open:

```text
http://localhost:8765/geometry/unstructure_surface/editor/
```

The editor can:

- Generate flat 2D circle/ellipse/rectangle/NACA boundary curves.
- Generate thin 3D side-wall surfaces by enabling thickness.
- Preview with Three.js orbit controls when CDN access is available; otherwise
  it falls back to a built-in canvas preview.
- Rotate with left drag, zoom with the mouse wheel, and pan with right drag.
- Switch view with `ISO`, `Top`, and `Fit`.
- Export `unstruc_surface_in.dat`.
- Export STL for 3D side-wall surfaces.
- Copy the equivalent `run_surface_tools.py generate ...` command.

Default editor settings are solver-style:

```text
Shape     : Circle / 2D cylinder
Radius    : 0.25
Points    : 600
Center    : 19.2, 10.0, 0.005
3D        : on
Thickness : 0.01
Layers    : 3
```

This exports:

```text
nodes = 1800
elems = 2400
```

Example editor settings for a 2D cylinder:

```text
Shape  : Circle
Radius : 0.25
Points : 96
Center : 19.2, 10.0, 0.0
3D     : off
```

The exported flat boundary curve should have:

```text
nodes = 96
elems = 0
```

Example settings for a thin 3D side-wall cylinder:

```text
Shape     : Circle
Radius    : 0.25
Points    : 96
Center    : 19.2, 10.0, 0.0
3D        : on
Thickness : 0.1
```

The exported surface should have:

```text
nodes = 192
elems = 192
```

After downloading a surface file, test it with:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/download_folder inspect --roundtrip
```

After downloading an STL, convert it with:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir path/to/stl_folder convert-stl
```

## Notes

- Command-line `--body` is 1-based.
- Python list indexing is 0-based, so body 1 is `bodies[0]`.
- `surface.py`, `project.py`, `stl.py`, and `modeling.py` do not open windows.
- Visualization functions may open PyVista or Matplotlib windows.
- Coordinate-only transforms preserve node ids and topology.
- Flat parametric bodies have zero elements when `--thickness` is not used.
- Solver-style 2D cases should use `--thickness` with `--param layers=3` to
  create a thin side-wall surface like `example/run_case_2D`.
- STL conversion writes STL boundary surface triangles.
- `--thickness` creates a side-wall surface from an ordered 2D boundary; it does
  not add interior volume points.
- If node order, node count, or topology changes, any external solver inputs
  that refer to those nodes/elements must be checked or regenerated.
