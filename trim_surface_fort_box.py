from __future__ import annotations

import argparse
import json
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np


DEFAULT_CASE_DIR = Path(
    r".\test"
)
DEFAULT_BOUNDS = {
    "x": (-1.0, 4.0),
    "y": (-1.0, 5.0),
    "z": (-1.0, 6.0),
}
DEFAULT_SURFACE_NAME = "unstruc_surface_in.dat"
DEFAULT_FORT_START = 41

HEADER_RECORD_BYTES = 20
VECTOR_RECORD_BYTES = 24
FRAME_HEADER_BYTES = 4 + HEADER_RECORD_BYTES + 4
NODE_RECORD_BYTES = 4 + VECTOR_RECORD_BYTES + 4
HEADER_STRUCT = struct.Struct("<iddii")
NODE_DTYPE = np.dtype([("start", "<i4"), ("xyz", "<f8", (3,)), ("end", "<i4")])


@dataclass
class SurfaceBody:
    nodes: np.ndarray
    elems: np.ndarray


@dataclass
class SurfaceFile:
    bodies: list[SurfaceBody]
    sentinel: str


@dataclass
class TrimmedBody:
    body: SurfaceBody
    keep_indices: np.ndarray
    old_node_count: int
    old_elem_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trim unstruc_surface_in.dat and matching fort.* files to an axis-aligned box."
    )
    parser.add_argument("--case-dir", type=Path, default=DEFAULT_CASE_DIR)
    parser.add_argument("--surface-name", default=DEFAULT_SURFACE_NAME)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--fort-start", type=int, default=DEFAULT_FORT_START)
    parser.add_argument("--x", type=float, nargs=2, default=DEFAULT_BOUNDS["x"], metavar=("MIN", "MAX"))
    parser.add_argument("--y", type=float, nargs=2, default=DEFAULT_BOUNDS["y"], metavar=("MIN", "MAX"))
    parser.add_argument("--z", type=float, nargs=2, default=DEFAULT_BOUNDS["z"], metavar=("MIN", "MAX"))
    parser.add_argument("--overwrite", action="store_true", help="Replace output-dir if it already exists.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    case_dir = args.case_dir.resolve()
    output_dir = args.output_dir.resolve() if args.output_dir else case_dir.with_name(f"{case_dir.name}_trimmed_box")
    bounds = {
        "x": tuple(float(v) for v in args.x),
        "y": tuple(float(v) for v in args.y),
        "z": tuple(float(v) for v in args.z),
    }

    if not case_dir.exists():
        raise FileNotFoundError(f"Case directory does not exist: {case_dir}")
    if output_dir.exists():
        if not args.overwrite:
            raise FileExistsError(f"Output directory already exists: {output_dir} (use --overwrite to replace it)")
        shutil.rmtree(output_dir)

    shutil.copytree(case_dir, output_dir)
    surface_path = output_dir / args.surface_name
    surface_file = read_surface(surface_path)
    trimmed = [trim_body_to_box(body, bounds) for body in surface_file.bodies]
    write_surface(surface_path, [item.body for item in trimmed], sentinel=surface_file.sentinel)

    report = {
        "input_dir": str(case_dir),
        "output_dir": str(output_dir),
        "surface": str(surface_path),
        "bounds": bounds,
        "bodies": [],
        "fort_files": [],
    }

    for body_id, item in enumerate(trimmed, start=1):
        report["bodies"].append(
            {
                "body": body_id,
                "nodes_before": item.old_node_count,
                "nodes_after": int(item.body.nodes.shape[0]),
                "elems_before": item.old_elem_count,
                "elems_after": int(item.body.elems.shape[0]),
            }
        )
        fort_path = output_dir / f"fort.{args.fort_start + body_id - 1}"
        if fort_path.exists():
            fort_report = trim_fort_file(fort_path, item.keep_indices, item.old_node_count)
            fort_report["body"] = body_id
            report["fort_files"].append(fort_report)

    report_path = output_dir / "trim_box_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print_summary(report)


def read_surface(path: Path) -> SurfaceFile:
    raw_lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    lines = [line for line in raw_lines if line.strip()]
    bodies: list[SurfaceBody] = []
    sentinel = " -100.000  -100.000  -100.000"
    idx = 0

    while idx < len(lines):
        parts = lines[idx].split()
        if is_final_sentinel(parts):
            sentinel = lines[idx].rstrip()
            break
        if len(parts) < 2:
            idx += 1
            continue

        node_count = int(float(parts[0]))
        elem_count = int(float(parts[1]))
        if node_count < 0 or elem_count < 0:
            if is_final_sentinel(parts):
                break
            raise ValueError(
                f"Invalid body header at nonempty line {idx + 1}: node_count={node_count}, elem_count={elem_count}"
            )
        idx += 1

        nodes = np.zeros((node_count, 4), dtype=float)
        for row in range(node_count):
            parts = lines[idx].split()
            idx += 1
            if len(parts) >= 4:
                nodes[row] = [int(float(parts[0])), float(parts[1]), float(parts[2]), float(parts[3])]
            elif len(parts) >= 3 and idx < len(lines):
                z_parts = lines[idx].split()
                idx += 1
                nodes[row] = [int(float(parts[0])), float(parts[1]), float(parts[2]), float(z_parts[0])]
            else:
                raise ValueError(f"Invalid node record near body {len(bodies) + 1}, node {row + 1}")

        elems = np.zeros((elem_count, 4), dtype=int)
        for row in range(elem_count):
            parts = lines[idx].split()
            idx += 1
            if len(parts) < 4:
                raise ValueError(f"Invalid element record near body {len(bodies) + 1}, elem {row + 1}")
            elems[row] = [int(float(parts[0])), int(float(parts[1])), int(float(parts[2])), int(float(parts[3]))]

        bodies.append(SurfaceBody(nodes=nodes, elems=elems))

    return SurfaceFile(bodies=bodies, sentinel=sentinel)


def is_final_sentinel(parts: list[str]) -> bool:
    if len(parts) < 3:
        return False
    try:
        values = [float(parts[0]), float(parts[1]), float(parts[2])]
    except ValueError:
        return False
    return values[0] < 0.0 and max(values) - min(values) < 1.0e-9


def trim_body_to_box(body: SurfaceBody, bounds: dict[str, tuple[float, float]]) -> TrimmedBody:
    points = body.nodes[:, 1:4]
    keep_mask = (
        (points[:, 0] >= bounds["x"][0])
        & (points[:, 0] <= bounds["x"][1])
        & (points[:, 1] >= bounds["y"][0])
        & (points[:, 1] <= bounds["y"][1])
        & (points[:, 2] >= bounds["z"][0])
        & (points[:, 2] <= bounds["z"][1])
    )
    keep_indices = np.flatnonzero(keep_mask)
    kept_nodes = body.nodes[keep_indices].copy()

    old_ids = body.nodes[:, 0].astype(int)
    new_id_by_old_id: dict[int, int] = {}
    for new_row, old_row in enumerate(keep_indices, start=1):
        old_id = int(old_ids[int(old_row)])
        new_id_by_old_id[old_id] = new_row
        kept_nodes[new_row - 1, 0] = new_row

    kept_elems: list[list[int]] = []
    for elem in body.elems:
        old_refs = [int(elem[1]), int(elem[2]), int(elem[3])]
        if all(ref in new_id_by_old_id for ref in old_refs):
            new_refs = [new_id_by_old_id[ref] for ref in old_refs]
            kept_elems.append([len(kept_elems) + 1, *new_refs])

    new_elems = np.asarray(kept_elems, dtype=int) if kept_elems else np.zeros((0, 4), dtype=int)
    return TrimmedBody(
        body=SurfaceBody(nodes=kept_nodes, elems=new_elems),
        keep_indices=keep_indices.astype(int),
        old_node_count=int(body.nodes.shape[0]),
        old_elem_count=int(body.elems.shape[0]),
    )


def write_surface(path: Path, bodies: list[SurfaceBody], sentinel: str) -> None:
    with path.open("w", encoding="utf-8") as f:
        for body_id, body in enumerate(bodies):
            f.write(" \n")
            f.write(f"{body.nodes.shape[0]:12d}{body.elems.shape[0]:12d}\n")
            f.write(" \n")
            for node_id, x, y, z in body.nodes:
                f.write(f"{int(node_id):12d}   {x:.14f}        {y:.14f}     \n")
                f.write(f"   {z:.14f}     \n")
            f.write(" \n")
            for elem_id, n1, n2, n3 in body.elems:
                f.write(f"{int(elem_id):12d}{int(n1):12d}{int(n2):12d}{int(n3):12d}\n")
            if body_id < len(bodies) - 1:
                f.write(" \n")
                f.write(f"{sentinel}\n")
        f.write(" \n")
        f.write(f"{sentinel}\n")


def trim_fort_file(path: Path, keep_indices: np.ndarray, old_node_count: int) -> dict[str, object]:
    info = inspect_fort(path)
    if info["node_count"] != old_node_count:
        raise ValueError(
            f"{path.name} node count {info['node_count']} does not match surface body nodes {old_node_count}"
        )

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    new_node_count = int(len(keep_indices))
    if new_node_count <= 0:
        raise ValueError(f"{path.name} would have zero nodes after trimming; choose a larger box or drop/renumber bodies manually")
    keep_indices = keep_indices.astype(int)

    with path.open("rb") as src, tmp_path.open("wb") as dst:
        for frame_index in range(int(info["frame_count"])):
            raw_header = src.read(FRAME_HEADER_BYTES)
            if len(raw_header) != FRAME_HEADER_BYTES:
                raise ValueError(f"Could not read complete header from {path} frame {frame_index}")
            start_marker, dt, time, npts, end_marker = HEADER_STRUCT.unpack(raw_header)
            if start_marker != HEADER_RECORD_BYTES or end_marker != HEADER_RECORD_BYTES:
                raise ValueError(f"Invalid header markers in {path} frame {frame_index}")
            if npts != old_node_count:
                raise ValueError(f"{path} frame {frame_index} has node count {npts}, expected {old_node_count}")

            records = np.fromfile(src, dtype=NODE_DTYPE, count=old_node_count)
            if len(records) != old_node_count:
                raise ValueError(f"Could not read node records from {path} frame {frame_index}")
            if not np.all(records["start"] == VECTOR_RECORD_BYTES) or not np.all(records["end"] == VECTOR_RECORD_BYTES):
                raise ValueError(f"Invalid node record markers in {path} frame {frame_index}")

            dst.write(HEADER_STRUCT.pack(HEADER_RECORD_BYTES, dt, time, new_node_count, HEADER_RECORD_BYTES))
            records[keep_indices].tofile(dst)

    tmp_path.replace(path)
    new_info = inspect_fort(path)
    return {
        "path": str(path),
        "frames": int(new_info["frame_count"]),
        "nodes_before": int(old_node_count),
        "nodes_after": int(new_info["node_count"]),
        "bytes_before": int(info["file_size"]),
        "bytes_after": int(new_info["file_size"]),
    }


def inspect_fort(path: Path) -> dict[str, object]:
    file_size = path.stat().st_size
    with path.open("rb") as f:
        raw_header = f.read(FRAME_HEADER_BYTES)
    if len(raw_header) != FRAME_HEADER_BYTES:
        raise ValueError(f"Could not read fort header: {path}")
    start_marker, dt, first_time, node_count, end_marker = HEADER_STRUCT.unpack(raw_header)
    if start_marker != HEADER_RECORD_BYTES or end_marker != HEADER_RECORD_BYTES:
        raise ValueError(f"Invalid fort header markers in {path}: {start_marker}, {end_marker}")
    frame_size = FRAME_HEADER_BYTES + int(node_count) * NODE_RECORD_BYTES
    if frame_size <= FRAME_HEADER_BYTES or file_size % frame_size != 0:
        raise ValueError(f"{path} size {file_size} is not divisible by frame size {frame_size}")
    frame_count = file_size // frame_size
    return {
        "file_size": file_size,
        "node_count": int(node_count),
        "frame_count": int(frame_count),
        "dt": float(dt),
        "first_time": float(first_time),
    }


def print_summary(report: dict[str, object]) -> None:
    print("Trim Surface + Fort")
    print("===================")
    print(f"Input : {report['input_dir']}")
    print(f"Output: {report['output_dir']}")
    print(f"Bounds: {report['bounds']}")
    print()
    for item in report["bodies"]:
        print(
            f"Body {item['body']}: "
            f"nodes {item['nodes_before']} -> {item['nodes_after']}, "
            f"elems {item['elems_before']} -> {item['elems_after']}"
        )
    print()
    for item in report["fort_files"]:
        print(
            f"Fort body {item['body']}: "
            f"nodes {item['nodes_before']} -> {item['nodes_after']}, "
            f"frames {item['frames']}"
        )
    print()
    print(f"Report: {Path(report['output_dir']) / 'trim_box_report.json'}")


if __name__ == "__main__":
    main()
