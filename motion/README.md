# Prescribed Motion Tools

`fort.*` files store prescribed relative surface motion for each body. They are
kept separate from `unstruc_surface_in.dat` tools because they can be hundreds of
MB and should not be rewritten during every surface edit.

## Format

The current examples use Fortran sequential unformatted records:

```text
frame header record:
  real*8 dt
  real*8 time
  int32  nPtsBodyMarker

node record repeated nPtsBodyMarker times:
  real*8 dx
  real*8 dy
  real*8 dz
```

Each Fortran record also has leading and trailing 32-bit byte-count markers. The
header marker is `20`; each node-vector marker is `24`.

## Inspect

```bash
python motion/run_motion_tools.py --case-dir example/run_case inspect
python motion/run_motion_tools.py --case-dir example/run_case_2D inspect --body 1
```

`inspect` reports frame counts, `dt`, time range, and checks each fort file's
node count against `unstruc_surface_in.dat`.

## Rotate

Translation of `unstruc_surface_in.dat` does not require changing `fort.*`,
because the motion vectors are relative. Rotation does require rotating each
stored `(dx, dy, dz)` vector:

```bash
python motion/run_motion_tools.py --case-dir example/run_case rotate --rotate 0 0 10 --body 1 --output-dir motion_outputs
```

Rotation uses the same XYZ Euler degrees convention as the surface transform
tools. Outputs are written as new files by default, for example
`motion_outputs/fort.41_rotated`.

## Visualize

Motion visualization combines `unstruc_surface_in.dat` with the matching
`fort.*` file. Gray shapes are sampled frames over the period; red is the
highlighted frame.

```bash
python motion/run_motion_tools.py --case-dir example/run_case_2D view 2d --body 1 --frame 240 --samples 18 --save body1_motion.png --no-show
python motion/run_motion_tools.py --case-dir example/run_case view 3d --body 4 --frame 240 --samples 8 --save body4_motion.png --no-show
```

In `2d` mode, `--plane xy|xz|yz` selects the projection. Thin side-wall XY
surfaces are drawn as one representative closed layer, which keeps 2D plots
close to a clean outline/envelope view. In `3d` mode, PyVista draws sampled
surface meshes as a semi-transparent envelope with the highlighted frame in red.

Other likely edit operations:

- body reorder or body duplication: rename/copy matching `fort.*` files
- scale of geometry: scale motion-vector amplitudes by the same factor
- mirror/reflection: apply the same sign changes to motion vectors
- changing node order: reorder fort node records to match the new surface order
- resampling a period: interpolate frames and update frame headers
- trimming/extending a run: keep or repeat frame blocks consistently
