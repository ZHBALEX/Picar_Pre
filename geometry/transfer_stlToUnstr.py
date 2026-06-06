from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from geometry.unstructure_surface.stl import cut_stl_with_box, mesh_report, stl_to_surface_body  # noqa: E402
from geometry.unstructure_surface.surface import write_surface  # noqa: E402


def print_section(title: str) -> None:
    """Print a small terminal section header."""
    print()
    print(title)
    print("=" * len(title))


def cut_mesh_with_box(
    stl_file: str | Path,
    box_bounds: list[float],
    output_stl: str | Path | None = None,
    visualize: bool = False,
    show_original: bool = True,
):
    """Compatibility wrapper for cutting STL meshes."""
    original, cut_mesh = cut_stl_with_box(stl_file, box_bounds=box_bounds, output_stl=output_stl)

    print_section("STL Box Cut")
    print(f"Input STL  : {stl_file}")
    print(f"Box bounds : {box_bounds}")
    print(mesh_report(original, "Original mesh"))
    print(mesh_report(cut_mesh, "Cut mesh"))
    if output_stl is not None:
        print(f"Saved STL  : {output_stl}")

    if visualize:
        visualize_cut_result(original, cut_mesh, box_bounds, show_original=show_original)

    return cut_mesh


def visualize_cut_result(original_mesh, cut_mesh, box_bounds: list[float], show_original: bool = True) -> None:
    """Display the original mesh, cut mesh, and cut box with pyrender."""
    import pyrender
    import trimesh

    xmin, xmax, ymin, ymax, zmin, zmax = box_bounds
    scene = pyrender.Scene()
    if show_original:
        scene.add(pyrender.Mesh.from_trimesh(original_mesh, smooth=False))
    scene.add(pyrender.Mesh.from_trimesh(cut_mesh, smooth=False))

    box = trimesh.creation.box(extents=[xmax - xmin, ymax - ymin, zmax - zmin])
    box.apply_translation([(xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2])
    scene.add(pyrender.Mesh.from_trimesh(box, wireframe=True))
    pyrender.Viewer(scene, use_raymond_lighting=True)


def transfer_stl_to_unstructured_surface(stl_file, out_file, precision: int = 8):
    """Compatibility wrapper for converting one STL into surface format."""
    body = stl_to_surface_body(stl_file, precision=precision)
    write_surface(out_file, [body])

    print_section("STL To Surface")
    print(f"Input STL      : {stl_file}")
    print(f"Output surface : {out_file}")
    print(f"Precision      : {precision}")
    print(f"Nodes          : {body.node_count}")
    print(f"Triangles      : {body.elem_count}")
    print("Status         : DONE")
    return body


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cut STL meshes and convert STL files to unstructured surface files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    cut = subparsers.add_parser("cut", help="Cut an STL by face-center box filtering.")
    cut.add_argument("--stl", type=Path, required=True, help="Input STL file.")
    cut.add_argument("--box", type=float, nargs=6, required=True, metavar=("XMIN", "XMAX", "YMIN", "YMAX", "ZMIN", "ZMAX"))
    cut.add_argument("--out-stl", type=Path, default=None, help="Optional output STL path.")
    cut.add_argument("--visualize", action="store_true", help="Open a pyrender viewer.")
    cut.add_argument("--hide-original", action="store_true", help="Do not show the original mesh in the viewer.")

    convert = subparsers.add_parser("convert", help="Convert an STL to unstructured surface format.")
    convert.add_argument("--stl", type=Path, required=True, help="Input STL file.")
    convert.add_argument("--out", type=Path, required=True, help="Output unstructured surface file.")
    convert.add_argument("--precision", type=int, default=8, help="Decimal precision used before vertex deduplication.")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "cut":
        cut_mesh_with_box(
            args.stl,
            box_bounds=args.box,
            output_stl=args.out_stl,
            visualize=args.visualize,
            show_original=not args.hide_original,
        )
    elif args.command == "convert":
        transfer_stl_to_unstructured_surface(args.stl, args.out, precision=args.precision)


if __name__ == "__main__":
    main()
