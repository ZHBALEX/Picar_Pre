from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


SENTINEL = "-100.000  -100.000  -100.000"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASE_SURFACE = REPO_ROOT / "example" / "run_case" / "unstruc_surface_in.dat"


@dataclass
class SurfaceBody:
    """One solver body in unstruc_surface_in.dat."""

    nodes: np.ndarray
    elems: np.ndarray
    bbox: str | None = None

    @property
    def points(self) -> np.ndarray:
        """Return coordinates only, shaped as (n_nodes, 3)."""
        return self.nodes[:, 1:4]

    @property
    def node_count(self) -> int:
        return int(self.nodes.shape[0])

    @property
    def elem_count(self) -> int:
        return int(self.elems.shape[0])


def _read_nonempty_lines(path: str | Path) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return [line.strip() for line in f if line.strip()]


def _is_sentinel(line: str, tol: float = 5.0) -> bool:
    parts = line.split()
    if len(parts) < 3:
        return False
    try:
        values = [float(parts[i]) for i in range(3)]
    except ValueError:
        return False
    return all(value < -tol for value in values)


def read_surface(path: str | Path, sentinel_tol: float = 5.0) -> list[SurfaceBody]:
    """Read a single-body or multi-body unstructured surface file.

    The common solver format is numeric-only, so the default path tokenizes the
    whole file with NumPy's C parser and then slices node/element blocks. If a
    file contains unusual non-numeric records, the original line-aware parser is
    still used as a compatibility fallback.
    """
    try:
        return _read_surface_token_stream(path, sentinel_tol=sentinel_tol)
    except (IndexError, TypeError, ValueError):
        return _read_surface_linewise(path, sentinel_tol=sentinel_tol)


def _read_surface_linewise(path: str | Path, sentinel_tol: float = 5.0) -> list[SurfaceBody]:
    """Read a surface file with strict line-aware parsing."""
    lines = _read_nonempty_lines(path)
    bodies: list[SurfaceBody] = []
    idx = 0

    while idx < len(lines):
        while idx < len(lines) and _is_sentinel(lines[idx], sentinel_tol):
            idx += 1
        if idx >= len(lines):
            break

        header = lines[idx].split()
        if len(header) < 2:
            raise ValueError(f"Cannot parse body header at nonempty line {idx + 1}: {lines[idx]}")

        node_count = int(float(header[0]))
        elem_count = int(float(header[1]))
        idx += 1

        nodes = np.zeros((node_count, 4), dtype=float)
        for row in range(node_count):
            if idx >= len(lines):
                raise ValueError(f"Body node block ended early near node {row + 1}")

            line1 = lines[idx].split()
            if len(line1) >= 4:
                nodes[row] = [int(line1[0]), float(line1[1]), float(line1[2]), float(line1[3])]
                idx += 1
                continue

            if idx + 1 >= len(lines):
                raise ValueError(f"Body node z coordinate is missing near node {row + 1}")

            line2 = lines[idx + 1].split()
            if len(line1) < 3 or len(line2) < 1:
                raise ValueError(f"Invalid node record near nonempty line {idx + 1}")

            nodes[row] = [int(line1[0]), float(line1[1]), float(line1[2]), float(line2[0])]
            idx += 2

        elems = np.zeros((elem_count, 4), dtype=int)
        for row in range(elem_count):
            if idx >= len(lines):
                raise ValueError(f"Body element block ended early near element {row + 1}")

            elem = lines[idx].split()
            if len(elem) < 4:
                raise ValueError(f"Invalid element record at nonempty line {idx + 1}: {lines[idx]}")

            elems[row] = [int(elem[0]), int(elem[1]), int(elem[2]), int(elem[3])]
            idx += 1

        bbox = None
        if idx < len(lines) and not _is_sentinel(lines[idx], sentinel_tol):
            bbox = lines[idx]
            idx += 1

        bodies.append(SurfaceBody(nodes=nodes, elems=elems, bbox=bbox))

    return bodies


def _read_surface_token_stream(path: str | Path, sentinel_tol: float = 5.0) -> list[SurfaceBody]:
    """Read the standard numeric surface format using NumPy tokenization."""
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    values = np.fromstring(text, sep=" ")
    if values.size == 0:
        return []

    bodies: list[SurfaceBody] = []
    idx = 0
    size = int(values.size)

    while idx < size:
        while idx + 2 < size and _token_is_sentinel(values[idx : idx + 3], sentinel_tol):
            idx += 3
        if idx >= size:
            break
        if idx + 1 >= size:
            raise ValueError("Incomplete body header")

        node_count = int(values[idx])
        elem_count = int(values[idx + 1])
        if node_count < 0 or elem_count < 0:
            raise ValueError("Negative body counts")
        idx += 2

        node_values = node_count * 4
        elem_values = elem_count * 4
        if idx + node_values + elem_values > size:
            raise ValueError("Surface body ended early")

        nodes = values[idx : idx + node_values].reshape(node_count, 4).copy()
        idx += node_values

        elems = values[idx : idx + elem_values].reshape(elem_count, 4).astype(int, copy=True)
        idx += elem_values

        bbox = None
        if idx + 2 < size and not _token_is_sentinel(values[idx : idx + 3], sentinel_tol):
            bbox_values = values[idx : idx + 3]
            bbox = " ".join(f"{value:.16g}" for value in bbox_values)
            idx += 3

        bodies.append(SurfaceBody(nodes=nodes, elems=elems, bbox=bbox))

    return bodies


def _token_is_sentinel(values: np.ndarray, tol: float) -> bool:
    return values.size >= 3 and bool(np.all(values[:3] < -tol))


def write_surface(path: str | Path, bodies: Iterable[SurfaceBody], write_final_sentinel: bool = True) -> None:
    """Write bodies in the solver's unstruc_surface_in.dat format."""
    bodies = list(bodies)
    with open(path, "w", encoding="utf-8") as f:
        for body_id, body in enumerate(bodies):
            f.write(" \n")
            f.write(f"{body.node_count:12d}{body.elem_count:12d}\n")
            f.write(" \n")

            for node_id, x, y, z in body.nodes:
                f.write(f"{int(node_id):12d}   {x:.14f}        {y:.14f}     \n")
                f.write(f"   {z:.14f}     \n")

            f.write(" \n")
            for elem_id, n1, n2, n3 in body.elems:
                f.write(f"{int(elem_id):12d}{int(n1):12d}{int(n2):12d}{int(n3):12d}\n")

            if body.bbox is not None:
                f.write(" \n")
                f.write(f"{body.bbox}\n")

            if body_id < len(bodies) - 1 or write_final_sentinel:
                f.write(" \n")
                f.write(f" {SENTINEL}\n")


def summarize_surface(bodies: Iterable[SurfaceBody]) -> list[dict[str, object]]:
    """Return body counts and coordinate ranges for quick case inspection."""
    summary = []
    for idx, body in enumerate(bodies, start=1):
        points = body.points
        summary.append(
            {
                "body": idx,
                "nodes": body.node_count,
                "elems": body.elem_count,
                "min": points.min(axis=0),
                "max": points.max(axis=0),
                "center": points.mean(axis=0),
            }
        )
    return summary


def format_surface_summary(bodies: Iterable[SurfaceBody]) -> str:
    """Format body counts and coordinate ranges as a compact table."""
    rows = list(summarize_surface(bodies))
    if not rows:
        return "No bodies found."

    header = (
        f"{'Body':>4}  {'Nodes':>8}  {'Elems':>8}  "
        f"{'X min':>11}  {'X max':>11}  "
        f"{'Y min':>11}  {'Y max':>11}  "
        f"{'Z min':>11}  {'Z max':>11}  "
        f"{'Center X':>11}  {'Center Y':>11}  {'Center Z':>11}"
    )
    line = "-" * len(header)
    body_lines = [header, line]

    for item in rows:
        xyz_min = item["min"]
        xyz_max = item["max"]
        center = item["center"]
        body_lines.append(
            f"{item['body']:>4}  {item['nodes']:>8}  {item['elems']:>8}  "
            f"{xyz_min[0]:>11.6f}  {xyz_max[0]:>11.6f}  "
            f"{xyz_min[1]:>11.6f}  {xyz_max[1]:>11.6f}  "
            f"{xyz_min[2]:>11.6f}  {xyz_max[2]:>11.6f}  "
            f"{center[0]:>11.6f}  {center[1]:>11.6f}  {center[2]:>11.6f}"
        )

    return "\n".join(body_lines)


def format_surface_summary_compact(bodies: Iterable[SurfaceBody]) -> str:
    """Format body counts and ranges as narrow vertical cards."""
    rows = list(summarize_surface(bodies))
    if not rows:
        return "No bodies found."

    lines = []
    for item in rows:
        xyz_min = item["min"]
        xyz_max = item["max"]
        center = item["center"]
        spans = xyz_max - xyz_min
        lines.extend(
            [
                f"Body {item['body']}",
                "-" * 6,
                f"  nodes / elems : {item['nodes']} / {item['elems']}",
                f"  center        : x={center[0]:.6f}, y={center[1]:.6f}, z={center[2]:.6f}",
                _format_axis_line("x", xyz_min[0], xyz_max[0], center[0], spans[0]),
                _format_axis_line("y", xyz_min[1], xyz_max[1], center[1], spans[1]),
                _format_axis_line("z", xyz_min[2], xyz_max[2], center[2], spans[2]),
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def _format_axis_line(axis: str, vmin: float, vmax: float, center: float, span: float) -> str:
    return f"  {axis} range       : {vmin:.6f} .. {vmax:.6f}  span={span:.6f}  {_axis_bar(vmin, vmax, center)}"


def _axis_bar(vmin: float, vmax: float, marker: float, width: int = 24) -> str:
    """Return a small ASCII range bar with the center marker."""
    if width < 3:
        width = 3
    if np.isclose(vmin, vmax):
        chars = ["-"] * width
        chars[width // 2] = "*"
        return "[" + "".join(chars) + "]"

    ratio = (marker - vmin) / (vmax - vmin)
    marker_idx = int(round(np.clip(ratio, 0.0, 1.0) * (width - 1)))
    chars = ["-"] * width
    chars[marker_idx] = "*"
    return "[" + "".join(chars) + "]"


def print_surface_summary(bodies: Iterable[SurfaceBody]) -> None:
    """Print a compact body-by-body geometry summary."""
    print(format_surface_summary_compact(bodies))


def format_validation_report(errors: Iterable[str]) -> str:
    """Format validation results for terminal output."""
    errors = list(errors)
    if not errors:
        return "Status: PASS\nSurface validation passed."

    lines = ["Status: FAIL", "Validation errors:"]
    lines.extend(f"- {error}" for error in errors)
    return "\n".join(lines)


def print_validation_report(errors: Iterable[str]) -> None:
    """Print validation results."""
    print(format_validation_report(errors))


def print_surface_report(bodies: Iterable[SurfaceBody], errors: Iterable[str] | None = None) -> None:
    """Print a structured surface summary and validation report."""
    bodies = list(bodies)
    print("Surface Summary")
    print("=" * 15)
    print(format_surface_summary_compact(bodies))
    print()
    print("Validation")
    print("=" * 10)
    print(format_validation_report(validate_surface(bodies) if errors is None else errors))


def _print_legacy_counts(label: str, count: int) -> None:
    """Print a small compatibility count block."""
    print(f"{label}: {count}")


def _print_surface_counts(bodies: Iterable[SurfaceBody]) -> None:
    """Print compact body and point counts for compatibility wrappers."""
    bodies = list(bodies)
    total_points = sum(body.node_count for body in bodies)
    print("Surface Counts")
    print("=" * 14)
    _print_legacy_counts("Bodies", len(bodies))
    _print_legacy_counts("Total points", total_points)


def _print_noop() -> None:
    """Placeholder used to keep output helpers grouped."""
    return None


def _print_body_count(bodies: Iterable[SurfaceBody]) -> None:
    """Print only the body count for lightweight compatibility wrappers."""
    bodies = list(bodies)
    print("Surface Counts")
    print("=" * 14)
    _print_legacy_counts("Bodies", len(bodies))


def validate_surface(
    bodies: Iterable[SurfaceBody],
    strict_ids: bool = True,
) -> list[str]:
    """Return surface-format validation errors; an empty list means checks passed."""
    bodies = list(bodies)
    errors: list[str] = []

    for body_id, body in enumerate(bodies, start=1):
        expected_node_ids = np.arange(1, body.node_count + 1)
        expected_elem_ids = np.arange(1, body.elem_count + 1)

        if strict_ids and not np.array_equal(body.nodes[:, 0].astype(int), expected_node_ids):
            errors.append(f"Body {body_id}: node ids are not contiguous from 1 to {body.node_count}")

        if strict_ids and not np.array_equal(body.elems[:, 0].astype(int), expected_elem_ids):
            errors.append(f"Body {body_id}: element ids are not contiguous from 1 to {body.elem_count}")

        if body.elem_count > 0:
            refs = body.elems[:, 1:4]
            if refs.min() < 1 or refs.max() > body.node_count:
                errors.append(f"Body {body_id}: element node references are outside 1..{body.node_count}")

    return errors


def transform_points(points: np.ndarray, rotation=None, translate=None, scale=1.0) -> np.ndarray:
    """Apply scale, XYZ Euler rotation in degrees, and translation to points."""
    pts = np.asarray(points, dtype=float).copy()

    if isinstance(scale, (int, float)):
        pts *= float(scale)
    else:
        pts *= np.asarray(scale, dtype=float).reshape(1, 3)

    if rotation is not None:
        rx, ry, rz = np.deg2rad(rotation)
        rot_x = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
        rot_y = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
        rot_z = np.array([[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]])
        pts = pts @ (rot_z @ rot_y @ rot_x).T

    if translate is not None:
        pts += np.asarray(translate, dtype=float).reshape(1, 3)

    return pts


def transform_body(body: SurfaceBody, rotation=None, translate=None, scale=1.0) -> SurfaceBody:
    """Transform body coordinates while preserving node ids and triangle topology."""
    nodes = body.nodes.copy()
    nodes[:, 1:4] = transform_points(nodes[:, 1:4], rotation=rotation, translate=translate, scale=scale)
    return SurfaceBody(nodes=nodes, elems=body.elems.copy(), bbox=body.bbox)


def read_multi_unstructured_surface_mesh(filepath, sentinel_tol=5.0):
    """Compatibility wrapper returning nodes, elements, and bbox lists."""
    bodies = read_surface(filepath, sentinel_tol=sentinel_tol)
    _print_body_count(bodies)
    return [body.nodes for body in bodies], [body.elems for body in bodies], [body.bbox for body in bodies]


def read_multi_body_pointcloud(filepath, sentinel_tol=5.0):
    """Compatibility wrapper returning per-body points and one stacked point cloud."""
    bodies = read_surface(filepath, sentinel_tol=sentinel_tol)
    body_points = [body.points for body in bodies]
    all_points = np.vstack(body_points) if body_points else np.empty((0, 3))
    _print_surface_counts(bodies)
    return body_points, all_points


def read_unstructured_surface_dat(filepath):
    """Read points from the first body in an unstructured surface file."""
    bodies = read_surface(filepath)
    if not bodies:
        raise ValueError("No bodies found in surface file")
    return bodies[0].points


def read_unstructure_3row_file(file_path: str):
    """Read a simple point file whose nodes are stored as id x y z."""
    raw = _read_nonempty_lines(file_path)
    if not raw:
        raise ValueError("DAT file is empty")

    node_count = int(float(raw[0].split()[0]))
    points = np.zeros((node_count, 3), dtype=float)
    for idx in range(node_count):
        parts = raw[idx + 1].split()
        if len(parts) < 4:
            raise ValueError(f"Node line format error: {raw[idx + 1]}")
        points[idx] = [float(parts[1]), float(parts[2]), float(parts[3])]
    return points


def write_unstructured_surface_dat(filepath, points):
    """Write a point cloud as a body with no triangle elements."""
    nodes = np.zeros((len(points), 4), dtype=float)
    nodes[:, 0] = np.arange(1, len(points) + 1)
    nodes[:, 1:4] = np.asarray(points, dtype=float)
    write_surface(filepath, [SurfaceBody(nodes=nodes, elems=np.empty((0, 4), dtype=int))], write_final_sentinel=False)


def compute_range(points):
    """Return xmin, xmax, ymin, ymax, zmin, zmax."""
    pts = np.asarray(points)
    return pts[:, 0].min(), pts[:, 0].max(), pts[:, 1].min(), pts[:, 1].max(), pts[:, 2].min(), pts[:, 2].max()


def sample_two_sides_indices(
    points,
    z_target,
    n_samples=120,
    z_tol=0.02,
    x_band_factor=1.5,
    dedup=True,
    plane_axis="z",
):
    """Sample upper and lower point ids along x on a selected y or z layer."""
    pts = np.asarray(points)
    ids = np.arange(len(pts))

    if plane_axis == "z":
        plane_i = 2
        up_i = 1
    elif plane_axis == "y":
        plane_i = 1
        up_i = 2
    else:
        raise ValueError("plane_axis must be 'y' or 'z'")

    xmin = float(pts[:, 0].min())
    xmax = float(pts[:, 0].max())
    xs = np.linspace(xmin, xmax, n_samples)
    x_step = (xmax - xmin) / max(n_samples - 1, 1)
    x_band = x_step * x_band_factor

    upper_idx = []
    lower_idx = []
    for xt in xs:
        dx = np.abs(pts[:, 0] - xt)
        x_mask = dx <= x_band

        if np.any(x_mask):
            cand_pts = pts[x_mask]
            cand_ids = ids[x_mask]
            cand_dx = dx[x_mask]
        else:
            k = min(60, len(pts))
            nearest = np.argpartition(dx, k - 1)[:k]
            cand_pts = pts[nearest]
            cand_ids = ids[nearest]
            cand_dx = dx[nearest]

        dplane = np.abs(cand_pts[:, plane_i] - z_target)
        ref_pt = cand_pts[np.lexsort((cand_dx, dplane))[0]]
        layer_mask = np.abs(cand_pts[:, plane_i] - ref_pt[plane_i]) < z_tol

        layer_pts = cand_pts[layer_mask] if np.any(layer_mask) else cand_pts
        layer_ids = cand_ids[layer_mask] if np.any(layer_mask) else cand_ids

        upper_idx.append(layer_ids[np.argmax(layer_pts[:, up_i])])
        lower_idx.append(layer_ids[np.argmin(layer_pts[:, up_i])])

    upper_idx = np.asarray(upper_idx, dtype=int)
    lower_idx = np.asarray(lower_idx, dtype=int)
    if dedup:
        upper_idx = np.unique(upper_idx)
        lower_idx = np.unique(lower_idx)

    return upper_idx, lower_idx, upper_idx + 1, lower_idx + 1


def main_multi_body(filepath: str | Path = DEFAULT_CASE_SURFACE) -> list[SurfaceBody]:
    """Load a surface file, validate it, and print a summary."""
    bodies = read_surface(filepath)
    print_surface_report(bodies)

    return bodies
