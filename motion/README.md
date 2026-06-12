# Prescribed Motion Tools

`fort.*` files store prescribed marker velocities for each body. They are kept
separate from `unstruc_surface_in.dat` tools because they can be hundreds of MB
and should not be rewritten during every surface edit.

## Format

The current examples use Fortran sequential unformatted records:

```text
frame header record:
  real*8 dt
  real*8 time
  int32  nPtsBodyMarker

node record repeated nPtsBodyMarker times:
  real*8 component_1
  real*8 component_2
  real*8 component_3
```

Each Fortran record also has leading and trailing 32-bit byte-count markers. The
header marker is `20`; each node-vector marker is `24`.

The current examples store motion components in physical `xyz` order, so the CLI
defaults to `--component-order xyz`. By default, tools interpret the mapped fort
values as marker velocities (`--motion-mode velocity`) and integrate them from
the reference `unstruc_surface_in.dat` coordinates with the `dt` stored in each
frame. Use `--motion-mode relative` or `--motion-mode displacement` only for
files known to store those quantities directly.

## Inspect

```bash
python motion/run_motion_tools.py --case-dir example/run_case inspect
python motion/run_motion_tools.py --case-dir example/run_case_2D inspect --body 1
```

`inspect` reports frame counts, `dt`, time range, and checks each fort file's
node count against `unstruc_surface_in.dat`.

## Rotate

Translation of `unstruc_surface_in.dat` does not require changing `fort.*`,
because velocity vectors are independent of absolute position. Rotation does
require rotating each stored velocity vector:

```bash
python motion/run_motion_tools.py --case-dir example/run_case rotate --rotate 0 0 10 --body 1 --output-dir motion_outputs
```

Rotation uses the same XYZ Euler degrees convention as the surface transform
tools after mapping raw fort columns through `--component-order`. Outputs are
written as new files by default, for example `motion_outputs/fort.41_rotated`.

## Visualize

Motion visualization integrates velocities from `unstruc_surface_in.dat` with
the matching `fort.*` file. Gray shapes are sampled frames over the period; red
is the highlighted frame.

```bash
python motion/run_motion_tools.py --case-dir example/run_case_2D view 2d --body 1 --frame 240 --samples 18 --save body1_motion.png --no-show
python motion/run_motion_tools.py --case-dir example/run_case view 3d --body 4 --frame 240 --samples 8 --save body4_motion.png --no-show
python motion/run_motion_tools.py --case-dir example/run_case_2D view midline --body 1 --axis x --value-axis y --bins 80 --stride 80 --save body1_midline.png --no-show
```

In `2d` mode, `--plane xy|xz|yz` selects the projection. Thin side-wall XY
surfaces are drawn as one representative closed layer, which keeps 2D plots
close to a clean outline/envelope view. In `3d` mode, PyVista draws sampled
surface meshes as a semi-transparent envelope with the highlighted frame in red.
In `midline` mode, station-wise centerline motion is extracted from the
integrated body positions, normalized to `0..1` along `--axis`, mean-centered by
default, and plotted as phase curves with true upper/lower dashed envelope
lines. The default `--centerline-method bounds` uses the midpoint between each
station's lower and upper value-coordinate bounds; `--centerline-method mean`
uses the node average. Use `--absolute-midline` to plot absolute centerline
coordinates, or `--raw-station` to keep the original station coordinate.

## Analyze

Motion analysis uses the surface file as the initial geometry and `fort.*` as
the marker velocity field.

Fit the overall body centroid motion:

```bash
python motion/run_motion_tools.py --case-dir example/run_case_2D analyze centroid --body 1
```

This reports first-harmonic equations for centroid `x(t)`, `y(t)`, and `z(t)`:

```text
q(t) = offset + amplitude*cos(2*pi*t/period + phase)
```

Fit station-wise midline/centerline motion along a reference axis:

```bash
python motion/run_motion_tools.py --case-dir example/run_case_2D analyze midline --body 1 --axis x --bins 60 --output midline_equations_body1.csv --kinematics-output midline_kinematics_body1.csv
```

Stations are fixed bins in the reference surface coordinate. For each frame, the
deformed nodes inside each station are reduced to a centerline value, then each
requested value axis is fitted independently. The default
`--centerline-method bounds` uses the midpoint between lower and upper station
bounds; use `--centerline-method mean` for node averaging. Use
`--value-axis y --value-axis z` to choose outputs; the default is `y,z`.
`--output` writes fitted harmonic-equation coefficients; `--kinematics-output`
writes the station-wise time series.

Other likely edit operations:

- body reorder or body duplication: rename/copy matching `fort.*` files
- scale of geometry: scale motion-vector amplitudes by the same factor
- mirror/reflection: apply the same sign changes to motion vectors
- changing node order: reorder fort node records to match the new surface order
- resampling a period: interpolate frames and update frame headers
- trimming/extending a run: keep or repeat frame blocks consistently
