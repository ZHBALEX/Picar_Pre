from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from geometry.unstructure_surface.project import SurfaceProject  # noqa: E402
from geometry.unstructure_surface.surface import read_surface, write_surface  # noqa: E402
from geometry.unstructure_surface.visualize import (  # noqa: E402
    plot_body_2d,
    plot_pointcloud_all,
    plot_pointcloud_multi,
    show_sample_points,
    visualize_multi_mesh,
)


def parse_vec3(values: list[float] | None):
    """Parse an optional vector argument."""
    return None if values is None else tuple(values)


def parse_key_values(items: list[str] | None) -> dict[str, object]:
    """Parse key=value CLI items into int/float/string values."""
    result: dict[str, object] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"Expected key=value, got: {item}")
        key, value = item.split("=", 1)
        result[key.replace("-", "_")] = parse_scalar(value)
    return result


def parse_scalar(value: str) -> object:
    """Parse a scalar CLI value."""
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if any(ch in value for ch in [".", "e", "E"]):
            return float(value)
        return int(value)
    except ValueError:
        return value


def add_project_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--case-dir", type=Path, default=None, help="Target directory. Defaults to example/run_case.")
    parser.add_argument("--surface-name", default="unstruc_surface_in.dat", help="Surface filename inside the target directory.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified unstructured-surface preprocessing pipeline.")
    add_project_args(parser)

    subparsers = parser.add_subparsers(dest="command")

    inspect_cmd = subparsers.add_parser("inspect", help="Load, summarize, and validate the target surface.")
    inspect_cmd.add_argument("--roundtrip", action="store_true", help="Write to a temporary file and read it back.")

    convert = subparsers.add_parser("convert-stl", help="Convert STL files in the target directory to surface format.")
    convert.add_argument("stl", nargs="*", help="STL files. If omitted, all *.stl files in case-dir are used.")
    convert.add_argument("--output", default=None, help="Output filename/path. Defaults to surface-name in case-dir.")
    convert.add_argument("--append", action="store_true", help="Append converted STL bodies to the existing surface.")
    convert.add_argument("--precision", type=int, default=8, help="Decimal precision before STL vertex deduplication.")

    generate = subparsers.add_parser("generate", help="Generate a simple parametric body.")
    generate.add_argument("kind", choices=["circle", "ellipse", "rectangle", "naca"], help="Parametric model kind.")
    generate.add_argument("--output", default=None, help="Output filename/path. Defaults to surface-name in case-dir.")
    generate.add_argument("--append", action="store_true", help="Append the generated body to the existing surface.")
    generate.add_argument("--center", type=float, nargs=3, default=(0.0, 0.0, 0.0), metavar=("X", "Y", "Z"))
    generate.add_argument("--plane", choices=["xy", "xz", "yz"], default="xy")
    generate.add_argument("--thickness", type=float, default=0.0, help="Extrude the 2D model into a thin 3D body.")
    generate.add_argument("--rotate", type=float, nargs=3, default=None, metavar=("RX", "RY", "RZ"))
    generate.add_argument("--translate", type=float, nargs=3, default=None, metavar=("TX", "TY", "TZ"))
    generate.add_argument("--scale", type=float, default=1.0)
    generate.add_argument("--param", action="append", help="Extra model parameter as key=value, e.g. rx=0.5.")

    transform = subparsers.add_parser("transform", help="Transform bodies in an existing surface file.")
    transform.add_argument("--body", type=int, action="append", help="1-based body id. Repeat to select multiple bodies. Default: all.")
    transform.add_argument("--output", default=None, help="Output filename/path. Defaults to overwriting surface-name.")
    transform.add_argument("--rotate", type=float, nargs=3, default=None, metavar=("RX", "RY", "RZ"))
    transform.add_argument("--translate", type=float, nargs=3, default=None, metavar=("TX", "TY", "TZ"))
    transform.add_argument("--scale", type=float, default=1.0)

    view = subparsers.add_parser("view", help="Visualize the target surface.")
    view.add_argument("mode", choices=["mesh", "points", "body", "body2d", "sample"])
    view.add_argument("--body", type=int, default=1, help="1-based body id for body/body2d/sample modes.")
    view.add_argument("--target", type=float, default=4.0, help="Target y/z layer for sample mode.")
    view.add_argument("--plane-axis", choices=["y", "z"], default="y", help="Layer axis for sample mode.")
    view.add_argument("--show-nodes", action="store_true", help="Show node markers for body2d mode.")
    view.add_argument("--save", type=Path, default=None, help="Save body2d output to an image file.")

    args = parser.parse_args()
    if args.command is None:
        args.command = "inspect"
        args.roundtrip = False
    return args


def run_roundtrip(project: SurfaceProject) -> None:
    bodies = project.load(required=True)
    out = Path(tempfile.gettempdir()) / "picar_surface_roundtrip.dat"
    write_surface(out, bodies)
    reread = read_surface(out)
    arrays_equal = len(bodies) == len(reread) and all(
        np.array_equal(a.nodes, b.nodes) and np.array_equal(a.elems, b.elems) for a, b in zip(bodies, reread)
    )
    out.unlink(missing_ok=True)
    print()
    print("Roundtrip")
    print("=" * 9)
    print(f"Temporary file : {out}")
    print(f"Bodies         : {len(reread)}")
    print(f"Arrays equal   : {arrays_equal}")
    print(f"Status         : {'PASS' if arrays_equal else 'FAIL'}")


def print_write_report(title: str, project: SurfaceProject, output: Path, bodies_count: int) -> None:
    print()
    print(title)
    print("=" * len(title))
    print(f"Case dir     : {project.case_dir}")
    print(f"Output file  : {output}")
    print(f"Bodies       : {bodies_count}")
    print("Status       : DONE")


def main() -> None:
    args = parse_args()
    project = SurfaceProject(args.case_dir, surface_name=args.surface_name)

    if args.command == "inspect":
        print(project.report())
        if args.roundtrip:
            run_roundtrip(project)

    elif args.command == "convert-stl":
        out, bodies = project.convert_stl(
            stl_files=args.stl,
            output=args.output,
            append=args.append,
            precision=args.precision,
        )
        print_write_report("STL Conversion", project, out, len(bodies))
        print(project.report(surface_path=out, bodies=bodies))

    elif args.command == "generate":
        params = parse_key_values(args.param)
        out, bodies = project.generate(
            args.kind,
            output=args.output,
            append=args.append,
            center=tuple(args.center),
            plane=args.plane,
            thickness=args.thickness,
            rotation=parse_vec3(args.rotate),
            translate=parse_vec3(args.translate),
            scale=args.scale,
            **params,
        )
        print_write_report("Parametric Generation", project, out, len(bodies))
        print(project.report(surface_path=out, bodies=bodies))

    elif args.command == "transform":
        out, bodies = project.transform(
            body_ids=args.body,
            output=args.output,
            rotation=parse_vec3(args.rotate),
            translate=parse_vec3(args.translate),
            scale=args.scale,
        )
        print_write_report("Surface Transform", project, out, len(bodies))
        print(project.report(surface_path=out, bodies=bodies))

    elif args.command == "view":
        bodies = project.load(required=True)
        if args.mode == "mesh":
            if all(body.elem_count == 0 for body in bodies):
                print()
                print("2D Boundary Notice")
                print("==================")
                print("All bodies have zero elements. Showing body2d boundary view instead of triangle mesh.")
                plot_body_2d(bodies[args.body - 1], show_nodes=args.show_nodes, save_path=args.save)
            else:
                visualize_multi_mesh(bodies)
        elif args.mode == "points":
            plot_pointcloud_multi(bodies)
        elif args.mode == "body":
            plot_pointcloud_all(bodies[args.body - 1].points)
        elif args.mode == "body2d":
            plot_body_2d(bodies[args.body - 1], show_nodes=args.show_nodes, save_path=args.save)
        elif args.mode == "sample":
            show_sample_points(bodies, args.body, args.target, args.plane_axis)


if __name__ == "__main__":
    main()
