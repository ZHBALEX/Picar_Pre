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

    view = subparsers.add_parser("view", help="Plot the x-y grid.")
    view.add_argument("--from-input", action="store_true", help="Generate plot directly from mesh input parameters.")
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
        if args.from_input:
            plot_grid_from_input(project.input_path, save_path=args.save, show=not args.no_show)
        else:
            plot_grid_from_files(
                project.case_dir / "xgrid.dat",
                project.case_dir / "ygrid.dat",
                project.case_dir / "zgrid.dat",
                save_path=args.save,
                show=not args.no_show,
            )


if __name__ == "__main__":
    main()
