from __future__ import annotations

import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geometry.unstructure_surface.surface import transform_points


HEADER_RECORD_BYTES = 20
VECTOR_RECORD_BYTES = 24
FRAME_HEADER_BYTES = 4 + HEADER_RECORD_BYTES + 4
NODE_RECORD_BYTES = 4 + VECTOR_RECORD_BYTES + 4
HEADER_STRUCT = struct.Struct("<iddii")
NODE_DTYPE = np.dtype([("start", "<i4"), ("xyz", "<f8", (3,)), ("end", "<i4")])


@dataclass(frozen=True)
class MotionFrameHeader:
    """One fort.* frame header."""

    dt: float
    time: float
    node_count: int


@dataclass(frozen=True)
class FortMotionInfo:
    """Summary of one prescribed-motion fort.* file."""

    path: Path
    node_count: int
    frame_count: int
    frame_size: int
    dt: float
    first_time: float
    last_time: float


def fort_motion_info(path: str | Path) -> FortMotionInfo:
    """Inspect a fort.* motion file without loading all frames."""
    path = Path(path)
    file_size = path.stat().st_size
    first = read_frame_header(path, 0)
    if first.node_count <= 0:
        raise ValueError(f"{path} has invalid node count {first.node_count}")
    frame_size = frame_size_for_nodes(first.node_count)
    if file_size % frame_size != 0:
        raise ValueError(f"{path} size {file_size} is not divisible by frame size {frame_size}")

    frame_count = file_size // frame_size
    last = read_frame_header(path, frame_count - 1)
    if last.node_count != first.node_count:
        raise ValueError(f"{path} node count changed from {first.node_count} to {last.node_count}")
    return FortMotionInfo(
        path=path,
        node_count=first.node_count,
        frame_count=frame_count,
        frame_size=frame_size,
        dt=first.dt,
        first_time=first.time,
        last_time=last.time,
    )


def frame_size_for_nodes(node_count: int) -> int:
    """Return one binary frame size for node_count motion vectors."""
    return FRAME_HEADER_BYTES + int(node_count) * NODE_RECORD_BYTES


def read_frame_header(path: str | Path, frame_index: int, node_count: int | None = None) -> MotionFrameHeader:
    """Read one frame header."""
    path = Path(path)
    offset = _frame_offset(frame_index, node_count) if node_count is not None else 0
    if node_count is None and frame_index != 0:
        node_count = read_frame_header(path, 0).node_count
        offset = _frame_offset(frame_index, node_count)

    with path.open("rb") as f:
        f.seek(offset)
        raw = f.read(FRAME_HEADER_BYTES)

    if len(raw) != FRAME_HEADER_BYTES:
        raise ValueError(f"Could not read complete frame header {frame_index} from {path}")

    start_marker, dt, time, npts, end_marker = HEADER_STRUCT.unpack(raw)
    if start_marker != HEADER_RECORD_BYTES or end_marker != HEADER_RECORD_BYTES:
        raise ValueError(f"Invalid frame header markers in {path} frame {frame_index}: {start_marker}, {end_marker}")
    return MotionFrameHeader(dt=dt, time=time, node_count=npts)


def read_frame(
    path: str | Path,
    frame_index: int,
    node_count: int | None = None,
    component_order: str | None = None,
) -> tuple[MotionFrameHeader, np.ndarray]:
    """Read one frame as (header, motion_vectors).

    component_order describes the raw fort columns. For example, "yxz" means
    raw column 0 is physical y, raw column 1 is physical x, and raw column 2 is
    physical z. Use None to return raw file order.
    """
    path = Path(path)
    header = read_frame_header(path, frame_index, node_count=node_count)
    offset = _frame_offset(frame_index, header.node_count) + FRAME_HEADER_BYTES

    with path.open("rb") as f:
        f.seek(offset)
        records = np.fromfile(f, dtype=NODE_DTYPE, count=header.node_count)

    if len(records) != header.node_count:
        raise ValueError(f"Could not read complete frame {frame_index} from {path}")
    _validate_node_markers(records, path, frame_index)
    vectors = records["xyz"].copy()
    if component_order is not None:
        vectors = components_to_physical(vectors, component_order)
    return header, vectors


def rotate_fort_motion(
    input_path: str | Path,
    output_path: str | Path,
    rotation: tuple[float, float, float],
    *,
    chunk_nodes: int = 65536,
    component_order: str = "xyz",
) -> FortMotionInfo:
    """Rotate all motion vectors in a fort.* file and write a new file.

    The fort.* values are relative vectors, so translation is intentionally not
    supported. component_order maps raw file columns to physical x/y/z before
    applying the same XYZ Euler degrees convention as surface transforms.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)
    info = fort_motion_info(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("rb") as src, output_path.open("wb") as dst:
        for frame_index in range(info.frame_count):
            header_raw = src.read(FRAME_HEADER_BYTES)
            if len(header_raw) != FRAME_HEADER_BYTES:
                raise ValueError(f"Could not read header for frame {frame_index} from {input_path}")
            dst.write(header_raw)

            remaining = info.node_count
            while remaining:
                count = min(int(chunk_nodes), remaining)
                records = np.fromfile(src, dtype=NODE_DTYPE, count=count)
                if len(records) != count:
                    raise ValueError(f"Could not read node records for frame {frame_index} from {input_path}")
                _validate_node_markers(records, input_path, frame_index)

                records = records.copy()
                physical = components_to_physical(records["xyz"], component_order)
                rotated = transform_points(physical, rotation=rotation, translate=None, scale=1.0)
                records["xyz"] = physical_to_components(rotated, component_order)
                records.tofile(dst)
                remaining -= count

    return fort_motion_info(output_path)


def copy_fort_motion(input_path: str | Path, output_path: str | Path) -> FortMotionInfo:
    """Copy one fort.* file and return its parsed metadata."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(input_path, output_path)
    return fort_motion_info(output_path)


def format_motion_info(info: FortMotionInfo) -> str:
    """Format one motion-file summary."""
    return "\n".join(
        [
            f"File        : {info.path}",
            f"Nodes       : {info.node_count}",
            f"Frames      : {info.frame_count}",
            f"Frame bytes : {info.frame_size}",
            f"dt          : {info.dt:.16g}",
            f"Time range  : {info.first_time:.16g} .. {info.last_time:.16g}",
        ]
    )


def components_to_physical(vectors: np.ndarray, component_order: str = "xyz") -> np.ndarray:
    """Convert raw fort columns to physical x/y/z columns."""
    order = _validate_component_order(component_order)
    vectors = np.asarray(vectors, dtype=float)
    result = np.empty_like(vectors)
    for raw_col, label in enumerate(order):
        result[:, _axis_index(label)] = vectors[:, raw_col]
    return result


def physical_to_components(vectors: np.ndarray, component_order: str = "xyz") -> np.ndarray:
    """Convert physical x/y/z columns back to raw fort column order."""
    order = _validate_component_order(component_order)
    vectors = np.asarray(vectors, dtype=float)
    result = np.empty_like(vectors)
    for raw_col, label in enumerate(order):
        result[:, raw_col] = vectors[:, _axis_index(label)]
    return result


def _frame_offset(frame_index: int, node_count: int) -> int:
    if frame_index < 0:
        raise ValueError("frame_index must be non-negative")
    return int(frame_index) * frame_size_for_nodes(node_count)


def _validate_node_markers(records: np.ndarray, path: Path, frame_index: int) -> None:
    if not np.all(records["start"] == VECTOR_RECORD_BYTES) or not np.all(records["end"] == VECTOR_RECORD_BYTES):
        raise ValueError(f"Invalid node record markers in {path} frame {frame_index}")


def _validate_component_order(component_order: str) -> str:
    order = component_order.lower()
    if sorted(order) != ["x", "y", "z"]:
        raise ValueError("component_order must contain x, y, and z exactly once")
    return order


def _axis_index(axis: str) -> int:
    return {"x": 0, "y": 1, "z": 2}[axis]
