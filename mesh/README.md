# Mesh preprocessing

This package contains structured Cartesian mesh helpers for PICAR cases.

## Common commands

Run the included basic example:

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples generate
python -m mesh.run_mesh_tools --case-dir mesh/examples inspect
python -m mesh.run_mesh_tools --case-dir mesh/examples view --mode 2d --plane xy --save mesh/examples/grid_preview.png --no-show
python -m mesh.run_mesh_tools --case-dir mesh/examples view --mode 1d --axis all --save mesh/examples/spacing.png --no-show
```

Open the visual input designer:

```powershell
python -m http.server 8765
```

Then visit `http://localhost:8765/mesh/editor/`. The designer only creates the
mesh-generator `input.dat`; use `generate` afterward to create the grid files.

Generate with multigrid-friendly dense-length optimization:

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples generate --optimize
```

The default optimizer prioritizes dense-region count quality first. To trade
dense and total interval quality more aggressively, use:

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples generate --optimize --priority balanced
```

To follow the Excel `mesh_Input_calculator.xlsx` style, use the preferred-count
table method. It computes `target dense count = dense length / ideal delta`,
then selects the closest count of the form `odd_remainder * 2^k` with odd
remainders from `1, 3, 5, ..., 21`.

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples optimize-input --method table --ideal-delta 0.0033
```

You can also set per-axis target spacings:

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples optimize-input --method table --ideal-delta-x 0.0033 --ideal-delta-y 0.0033
```

Write a separate optimized input file without overwriting the original:

```powershell
python -m mesh.run_mesh_tools --case-dir mesh/examples optimize-input
```

Inspect an existing case mesh:

```powershell
python -m mesh.run_mesh_tools --case-dir example/run_case inspect
```

Generate `xgrid.dat`, `ygrid.dat`, and `zgrid.dat` from a compact mesh-parameter
`input.dat`:

```powershell
python -m mesh.run_mesh_tools --case-dir path/to/case generate
```

Save an x-y grid preview without opening a GUI window:

```powershell
python -m mesh.run_mesh_tools --case-dir path/to/case view --save grid.png --no-show
```

## Python API

```python
from mesh import MeshProject

project = MeshProject("path/to/case")
mesh, report = project.generate(optimize=True)
print(project.report())
```

The supported entry points are the package API and `python -m mesh.run_mesh_tools`.

## Visualization

Grid axes are decoupled, so `view` supports separate modes:

```powershell
# From generated x/y/z grid files. zgrid.dat is not required for xy.
python -m mesh.run_mesh_tools --case-dir path/to/case view --save grid_xy.png --no-show

# From a mesh-generation input file, before xgrid/ygrid/zgrid exist.
python -m mesh.run_mesh_tools --case-dir path/to/case view --input input_mesh_twolayers.dat --save input_preview.png --no-show

# Other planes require the corresponding axis files.
python -m mesh.run_mesh_tools --case-dir path/to/case view --plane yz --save grid_yz.png --no-show

# 1D spacing curves for grid-size changes.
python -m mesh.run_mesh_tools --case-dir path/to/case view --mode 1d --axis all --save spacing.png --no-show

# 3D wireframe. Requires xgrid.dat, ygrid.dat, and zgrid.dat.
python -m mesh.run_mesh_tools --case-dir path/to/case view --mode 3d --max-lines 24
```

## Count semantics

The mesh generator treats `Nx_dense`, `n_left_stretch`, and related count fields
as interval counts. The written grid file therefore has `total intervals + 1`
coordinate nodes.

For multigrid performance, `inspect` reports how many times each dense and total
interval count can be divided by 2, plus the final odd remainder. Smaller odd
remainders are better; `1` is ideal.
