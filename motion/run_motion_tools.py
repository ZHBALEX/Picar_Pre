from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from motion.project import MotionProject  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prescribed-motion fort.* tools.")
    parser.add_argument("--case-dir", type=Path, default=None, help="Target case directory. Defaults to example/run_case.")
    parser.add_argument("--surface-name", default="unstruc_surface_in.dat", help="Surface filename inside case-dir.")
    parser.add_argument("--fort-start", type=int, default=41, help="fort number for body 1. Default: 41.")
    parser.add_argument(
        "--component-order",
        default="xyz",
        help="Raw fort column order mapped to physical axes. Default: xyz.",
    )
    parser.add_argument(
        "--motion-mode",
        choices=["velocity", "relative", "displacement"],
        default="velocity",
        help="Interpret fort values as velocities, center-relative positions, or nodal displacements. Default: velocity.",
    )

    subparsers = parser.add_subparsers(dest="command")

    inspect = subparsers.add_parser("inspect", help="Summarize fort.* files and compare node counts with the surface file.")
    inspect.add_argument("--body", type=int, action="append", help="1-based body id. Repeat to select multiple bodies.")
    inspect.add_argument("--no-surface-check", action="store_true", help="Skip unstruc_surface_in.dat node-count validation.")

    rotate = subparsers.add_parser("rotate", help="Rotate fort.* relative motion vectors.")
    rotate.add_argument("--body", type=int, action="append", help="1-based body id. Repeat to select multiple bodies. Default: all fort.* files.")
    rotate.add_argument("--rotate", type=float, nargs=3, required=True, metavar=("RX", "RY", "RZ"))
    rotate.add_argument("--output-dir", type=Path, default=None, help="Output directory. Defaults to case-dir.")
    rotate.add_argument("--suffix", default="_rotated", help="Output suffix appended after fort.NN. Default: _rotated.")

    view = subparsers.add_parser("view", help="Visualize fort.* motion together with unstruc_surface_in.dat.")
    view.add_argument("mode", choices=["2d", "3d"], nargs="?", default="2d", help="Visualization mode. Default: 2d.")
    view.add_argument("--body", type=int, default=1, help="1-based body id. Default: 1.")
    view.add_argument("--frame", type=int, default=-1, help="Highlighted frame index. Negative values count from the end. Default: -1.")
    view.add_argument("--samples", type=int, default=24, help="Number of sampled frames for the gray envelope. Default: 24.")
    view.add_argument("--plane", choices=["xy", "xz", "yz"], default="xy", help="Projection plane for 2d mode. Default: xy.")
    view.add_argument("--save", type=Path, default=None, help="Save figure/screenshot path.")
    view.add_argument("--no-show", action="store_true", help="Do not open an interactive window.")

    analyze = subparsers.add_parser("analyze", help="Analyze fort.* motion equations.")
    analyze.add_argument("kind", choices=["centroid", "centerline"], help="Analysis type.")
    analyze.add_argument("--body", type=int, default=1, help="1-based body id. Default: 1.")
    analyze.add_argument("--stride", type=int, default=1, help="Use every Nth frame. Default: 1.")
    analyze.add_argument("--period", type=float, default=1.0, help="Motion period used by harmonic fits. Default: 1.0.")
    analyze.add_argument("--axis", choices=["x", "y", "z"], default="x", help="Reference axis for centerline. Default: x.")
    analyze.add_argument("--value-axis", choices=["x", "y", "z"], action="append", help="Centerline value axis to fit. Repeatable. Default: y and z.")
    analyze.add_argument("--bins", type=int, default=80, help="Number of centerline stations. Default: 80.")
    analyze.add_argument("--output", type=Path, default=None, help="CSV output for centerline harmonic coefficients.")

    args = parser.parse_args()
    if args.command is None:
        args.command = "inspect"
        args.body = None
        args.no_surface_check = False
    return args


def main() -> None:
    args = parse_args()
    project = MotionProject(args.case_dir, surface_name=args.surface_name, fort_start=args.fort_start)

    if args.command == "inspect":
        print(project.inspect(body_ids=args.body, validate_surface_counts=not args.no_surface_check))

    elif args.command == "rotate":
        results = project.rotate(
            rotation=tuple(args.rotate),
            body_ids=args.body,
            output_dir=args.output_dir,
            suffix=args.suffix,
            component_order=args.component_order,
        )
        print("Motion Rotate")
        print("=============")
        print(f"Case dir : {project.case_dir}")
        print(f"Rotation : rx={args.rotate[0]}, ry={args.rotate[1]}, rz={args.rotate[2]}")
        for body_id, output_path, info in results:
            print(f"Body {body_id}: {output_path} ({info.frame_count} frames, {info.node_count} nodes)")
        print("Status   : DONE")

    elif args.command == "view":
        project.view(
            body_id=args.body,
            mode=args.mode,
            frame=args.frame,
            samples=args.samples,
            plane=args.plane,
            component_order=args.component_order,
            motion_mode=args.motion_mode,
            save_path=args.save,
            show=not args.no_show,
        )

    elif args.command == "analyze":
        if args.kind == "centroid":
            print(
                project.analyze_centroid(
                    body_id=args.body,
                    stride=args.stride,
                    period=args.period,
                    component_order=args.component_order,
                    motion_mode=args.motion_mode,
                )
            )
        elif args.kind == "centerline":
            value_axes = tuple(args.value_axis) if args.value_axis else ("y", "z")
            print(
                project.analyze_centerline(
                    body_id=args.body,
                    axis=args.axis,
                    value_axes=value_axes,
                    bins=args.bins,
                    stride=args.stride,
                    period=args.period,
                    component_order=args.component_order,
                    motion_mode=args.motion_mode,
                    output=args.output,
                )
            )


if __name__ == "__main__":
    main()
