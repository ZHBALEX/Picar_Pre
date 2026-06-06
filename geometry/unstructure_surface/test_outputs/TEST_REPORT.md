# Unstructured Surface Test Report

Generated on 2026-06-06.

## Baseline Example

Command:

```powershell
python geometry/unstructure_surface/run_surface_tools.py inspect --roundtrip
```

Result:

```text
bodies = 5
counts = [(7789, 15571), (9170, 18336), (914, 1696), (193, 352), (650, 1216)]
validation errors = 0
roundtrip = PASS
```

## 2D Circle Boundary

Directory:

```text
geometry/unstructure_surface/test_outputs/circle2d
```

Command:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir geometry/unstructure_surface/test_outputs/circle2d generate circle --param radius=0.25 --param n=96 --center 19.2 10 0
```

Result:

```text
bodies = 1
counts = [(96, 0)]
x range = [18.95, 19.45]
y range = [9.75, 10.25]
z range = [0.0, 0.0]
validation errors = 0
roundtrip = PASS
```

This is boundary-only: 96 boundary marker points and no elements.

## Thin 3D Cylinder Side-Wall

Directory:

```text
geometry/unstructure_surface/test_outputs/cylinder3d
```

Command:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir geometry/unstructure_surface/test_outputs/cylinder3d generate circle --param radius=0.25 --param n=96 --center 19.2 10 0 --thickness 0.1
```

Result:

```text
bodies = 1
counts = [(192, 192)]
x range = [18.95, 19.45]
y range = [9.75, 10.25]
z range = [-0.05, 0.05]
validation errors = 0
roundtrip = PASS
```

This is a boundary side-wall surface: two boundary rings and side-wall triangles.

## STL Box Conversion

Directory:

```text
geometry/unstructure_surface/test_outputs/stl_box
```

A box STL was generated with `trimesh.creation.box(extents=(1.0, 2.0, 3.0))`.

Command:

```powershell
python geometry/unstructure_surface/run_surface_tools.py --case-dir geometry/unstructure_surface/test_outputs/stl_box convert-stl
```

Result:

```text
bodies = 1
counts = [(8, 12)]
x range = [-0.5, 0.5]
y range = [-1.0, 1.0]
z range = [-1.5, 1.5]
validation errors = 0
roundtrip = PASS
```

This matches a surface triangle mesh for a box: 8 boundary vertices and 12 boundary triangles.
