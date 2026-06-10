from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mesh.project import MeshProject  # noqa: E402
from mesh.visualize import plot_grid_from_files, plot_grid_from_input  # noqa: E402


def add_ideal_delta_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ideal-delta", type=float, default=None, help="Ideal dense spacing for all axes in --method table.")
    parser.add_argument("--ideal-delta-x", type=float, default=None, help="Ideal dense spacing for x in --method table.")
    parser.add_argument("--ideal-delta-y", type=float, default=None, help="Ideal dense spacing for y in --method table.")
    parser.add_argument("--ideal-delta-z", type=float, default=None, help="Ideal dense spacing for z in --method table.")


def parse_ideal_deltas(args: argparse.Namespace) -> dict[str, float] | None:
    values = {
        "x": args.ideal_delta_x if args.ideal_delta_x is not None else args.ideal_delta,
        "y": args.ideal_delta_y if args.ideal_delta_y is not None else args.ideal_delta,
        "z": args.ideal_delta_z if args.ideal_delta_z is not None else args.ideal_delta,
    }
    result = {axis: value for axis, value in values.items() if value is not None}
    return result or None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Structured-mesh preprocessing tools.")
    parser.add_argument("--case-dir", type=Path, default=None, help="Target case directory. Defaults to example/run_case.")
    parser.add_argument("--input-name", default="input.dat", help="Mesh-parameter filename inside case-dir.")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("inspect", help="Summarize and validate existing x/y/z grid files.")

    generate = subparsers.add_parser("generate", help="Generate xgrid/ygrid/zgrid from mesh input parameters.")
    generate.add_argument("--output-dir", type=Path, default=None, help="Output directory. Defaults to case-dir.")
    generate.add_argument("--one-column", action="store_true", help="Write grid files as value-only columns.")
    generate.add_argument("--optimize", action="store_true", help="Optimize dense lengths for multigrid-friendly counts before generating.")
    generate.add_argument("--search-window", type=int, default=None, help="Dense interval count search radius for --optimize.")
    generate.add_argument(
        "--max-dense-change",
        type=float,
        default=0.25,
        help="Maximum relative dense-length change for --optimize. Default: 0.25.",
    )
    generate.add_argument(
        "--priority",
        choices=["dense", "balanced"],
        default="dense",
        help="Optimization priority. 'dense' preserves dense count quality first; 'balanced' trades dense and total quality.",
    )
    generate.add_argument(
        "--method",
        choices=["search", "table"],
        default="search",
        help="Optimization method. 'table' follows the Excel calculator style: nearest preferred count to ideal dense delta.",
    )
    add_ideal_delta_args(generate)

    optimize = subparsers.add_parser("optimize-input", help="Write an optimized mesh input file.")
    optimize.add_argument("--output", type=Path, default=None, help="Output input file. Defaults to input_optimized.dat.")
    optimize.add_argument("--search-window", type=int, default=None, help="Dense interval count search radius.")
    optimize.add_argument(
        "--max-dense-change",
        type=float,
        default=0.25,
        help="Maximum relative dense-length change. Default: 0.25.",
    )
    optimize.add_argument(
        "--priority",
        choices=["dense", "balanced"],
        default="dense",
        help="Optimization priority. 'dense' preserves dense count quality first; 'balanced' trades dense and total quality.",
    )
    optimize.add_argument(
        "--method",
        choices=["search", "table"],
        default="search",
        help="Optimization method. 'table' follows the Excel calculator style: nearest preferred count to ideal dense delta.",
    )
    add_ideal_delta_args(optimize)

    view = subparsers.add_parser("view", help="Visualize grid files or mesh input in 1D, 2D, or 3D.")
    view.add_argument("--source", choices=["auto", "grids", "input"], default="auto", help="Visualization source. Default: auto.")
    view.add_argument("--from-input", action="store_true", help="Compatibility alias for --source input.")
    view.add_argument("--input", "--input-file", dest="input_file", type=Path, default=None, help="Mesh input file to preview directly.")
    view.add_argument(
        "--input-format",
        choices=["auto", "canonical", "twolayer2d"],
        default="auto",
        help="Mesh input format for --source input.",
    )
    view.add_argument("--mode", choices=["1d", "2d", "3d"], default="2d", help="Visualization mode. Default: 2d.")
    view.add_argument("--plane", choices=["xy", "xz", "yz"], default="xy", help="2D plane for mode=2d. Default: xy.")
    view.add_argument("--axis", choices=["x", "y", "z", "all"], default="all", help="Axis for mode=1d. Default: all.")
    view.add_argument("--max-lines", type=int, default=24, help="Maximum sampled lines per axis for mode=3d.")
    view.add_argument("--save", type=Path, default=None, help="Save image path.")
    view.add_argument("--no-show", action="store_true", help="Do not open an interactive plot window.")

    args = parser.parse_args()
    if args.command is None:
        args.command = "inspect"
    return args


def main() -> None:
    args = parse_args()
    project = MeshProject(args.case_dir, input_name=args.input_name)

    if args.command == "inspect":
        print(project.report())

    elif args.command == "generate":
        mesh, optimization_report = project.generate(
            output_dir=args.output_dir,
            include_index=not args.one_column,
            optimize=args.optimize,
            search_window=args.search_window,
            max_relative_dense_change=args.max_dense_change,
            priority=args.priority,
            method=args.method,
            ideal_deltas=parse_ideal_deltas(args),
        )
        if optimization_report is not None:
            print(optimization_report)
            print()
        print("Mesh Generation")
        print("===============")
        print(f"Case dir : {project.case_dir}")
        print(f"Counts   : {mesh.counts}")
        print("Status   : DONE")

    elif args.command == "optimize-input":
        out, report = project.optimize_input(
            output=args.output,
            search_window=args.search_window,
            max_relative_dense_change=args.max_dense_change,
            priority=args.priority,
            method=args.method,
            ideal_deltas=parse_ideal_deltas(args),
        )
        print(report)
        print()
        print("Optimized Input")
        print("===============")
        print(f"Output : {out}")
        print("Status : DONE")

    elif args.command == "view":
        source = "input" if args.from_input or args.input_file is not None else args.source
        if source == "auto":
            source = "grids"
        if source == "input":
            input_path = args.input_file
            if input_path is None:
                input_path = project.input_path
            elif not input_path.is_absolute():
                input_path = project.case_dir / input_path
            plot_grid_from_input(
                input_path,
                input_format=args.input_format,
                mode=args.mode,
                plane=args.plane,
                axis=args.axis,
                save_path=args.save,
                show=not args.no_show,
                max_lines_per_axis=args.max_lines,
            )
        else:
            z_path = project.case_dir / "zgrid.dat"
            plot_grid_from_files(
                project.case_dir / "xgrid.dat",
                project.case_dir / "ygrid.dat",
                z_path if z_path.exists() else None,
                mode=args.mode,
                plane=args.plane,
                axis=args.axis,
                save_path=args.save,
                show=not args.no_show,
                max_lines_per_axis=args.max_lines,
            )


if __name__ == "__main__":
    main()
