from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geometry.unstructure_surface.surface import SurfaceBody


@dataclass
class ProbeSpec:
    """Raw probe_in.dat content split into marker and fluid probes."""

    marker_bodies: list[int]
    marker_refs: list[int]
    fluid_points: list[tuple[float, float, float]]
    errors: list[str]

    @property
    def marker_count(self) -> int:
        return len(self.marker_refs)

    @property
    def fluid_count(self) -> int:
        return len(self.fluid_points)


def format_probe_text(spec: ProbeSpec) -> str:
    """Format a probe specification in the solver's ``probe_in.dat`` layout."""
    if len(spec.marker_bodies) != len(spec.marker_refs):
        raise ValueError("marker body ids and references must have the same length")
    if any(int(body_id) < 1 for body_id in spec.marker_bodies):
        raise ValueError("marker body ids must start from 1")
    if any(int(reference) < 1 for reference in spec.marker_refs):
        raise ValueError("marker references must start from 1")

    lines = [
        "! -------------------- marker probes --------------------",
        f"{spec.marker_count} ! nmarker probe",
        " ".join(str(int(value)) for value in spec.marker_bodies),
        " ".join(str(int(value)) for value in spec.marker_refs),
        "! -------------------- fluid probes --------------------",
        f"{spec.fluid_count} ! nfluid probes",
    ]
    if spec.fluid_points:
        lines.extend(f"{x:.8f} {y:.8f} {z:.8f}" for x, y, z in spec.fluid_points)
    else:
        # PICAR examples keep one ignored coordinate record when nfluid is zero.
        lines.append("10.0 10.0 10.0")
    return "\n".join(lines) + "\n"


def write_probe_file(path: str | Path, spec: ProbeSpec) -> Path:
    """Write ``probe_in.dat`` without changing surface or mesh files."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_probe_text(spec), encoding="utf-8")
    return path


def probe_spec_from_payload(payload: dict[str, object]) -> ProbeSpec:
    """Build a validated probe specification from a JSON-ready editor payload."""
    raw_markers = payload.get("markers", [])
    raw_fluids = payload.get("fluids", [])
    if not isinstance(raw_markers, list) or not isinstance(raw_fluids, list):
        raise ValueError("markers and fluids must be lists")

    marker_bodies: list[int] = []
    marker_refs: list[int] = []
    for index, marker in enumerate(raw_markers, start=1):
        if not isinstance(marker, dict):
            raise ValueError(f"marker {index} must be an object")
        body_id = int(marker.get("body", 0))
        reference = int(marker.get("reference", 0))
        if body_id < 1 or reference < 1:
            raise ValueError(f"marker {index} needs positive body and reference ids")
        marker_bodies.append(body_id)
        marker_refs.append(reference)

    fluid_points: list[tuple[float, float, float]] = []
    for index, fluid in enumerate(raw_fluids, start=1):
        point = fluid.get("point") if isinstance(fluid, dict) else fluid
        if not isinstance(point, (list, tuple)) or len(point) != 3:
            raise ValueError(f"fluid probe {index} needs an XYZ point")
        xyz = tuple(float(value) for value in point)
        if not all(np.isfinite(value) for value in xyz):
            raise ValueError(f"fluid probe {index} has a non-finite coordinate")
        fluid_points.append(xyz)

    return ProbeSpec(marker_bodies, marker_refs, fluid_points, [])


def nearest_surface_node(body: SurfaceBody, point: tuple[float, float, float] | list[float]) -> dict[str, object]:
    """Return the surface node nearest an arbitrary target position."""
    target = np.asarray(point, dtype=float).reshape(3)
    if body.node_count == 0:
        raise ValueError("Cannot snap a marker probe to an empty surface body")
    distances2 = np.sum((body.points - target) ** 2, axis=1)
    row = int(np.argmin(distances2))
    node = body.nodes[row]
    return {
        "reference": int(node[0]),
        "point": [float(node[1]), float(node[2]), float(node[3])],
        "distance": float(np.sqrt(distances2[row])),
    }


def resolve_marker_reference(body: SurfaceBody, reference: int) -> dict[str, object]:
    """Resolve one node/element reference to the point displayed by the editor."""
    reference = int(reference)
    if reference < 1:
        raise ValueError("marker reference must start from 1")
    point, source = _marker_point(body, _body_lookup(body), reference)
    if point is None:
        raise ValueError(f"Surface body has no node or element reference {reference}")
    return {
        "reference": reference,
        "source": source,
        "point": [float(point[0]), float(point[1]), float(point[2])],
    }


def generate_surface_marker_probes(
    body: SurfaceBody,
    body_id: int,
    *,
    plane_axis: str = "z",
    plane_value: float = 0.0,
    n_samples: int = 30,
    plane_tolerance: float = 0.02,
    x_band_factor: float = 0.25,
    sides: str = "both",
    deduplicate: bool = True,
) -> list[dict[str, object]]:
    """Sample upper/lower surface nodes at uniform X targets on one slice.

    ``plane_axis='z'`` selects extrema in Y; ``plane_axis='y'`` selects extrema
    in Z. Slice membership is decided globally before X sampling, which prevents
    the old nearest-neighbour fallback from mixing points from different slice
    planes. Within each X neighbourhood, the closest point on each side is used
    instead of an arbitrary extrema point elsewhere in the band.

    Returned references are actual surface node ids, so sparse or reordered
    numbering is preserved. Extra metadata records requested X and slice error
    for preview diagnostics; it is not written to ``probe_in.dat``.
    """
    if body_id < 1:
        raise ValueError("body_id must start from 1")
    if body.node_count == 0:
        raise ValueError("Cannot generate probes for an empty body")
    if plane_axis not in {"y", "z"}:
        raise ValueError("plane_axis must be 'y' or 'z'")
    if sides not in {"both", "upper", "lower"}:
        raise ValueError("sides must be both, upper, or lower")
    n_samples = int(n_samples)
    if n_samples < 1:
        raise ValueError("n_samples must be at least 1")
    if plane_tolerance < 0.0:
        raise ValueError("plane_tolerance cannot be negative")
    if x_band_factor <= 0.0:
        raise ValueError("x_band_factor must be positive")

    points = np.asarray(body.points, dtype=float)
    node_ids = body.nodes[:, 0].astype(int)
    plane_index, extrema_index = (2, 1) if plane_axis == "z" else (1, 2)
    plane_distance = np.abs(points[:, plane_index] - float(plane_value))
    coordinate_span = float(np.ptp(points[:, plane_index]))
    numeric_tolerance = max(coordinate_span * 1e-12, 1e-12)
    slice_rows = np.flatnonzero(plane_distance <= float(plane_tolerance) + numeric_tolerance)
    if slice_rows.size < 2:
        # If the requested value lies between discrete mesh layers, use one
        # globally nearest layer. Never broaden independently at every X target:
        # doing so was the source of the visibly wavy "constant" slice.
        nearest_distance = float(plane_distance.min())
        slice_rows = np.flatnonzero(
            plane_distance <= nearest_distance + max(float(plane_tolerance), numeric_tolerance)
        )
    if slice_rows.size == 0:
        raise ValueError("No surface nodes are available near the requested slice")

    slice_points = points[slice_rows]
    xmin = float(slice_points[:, 0].min())
    xmax = float(slice_points[:, 0].max())
    targets = np.linspace(xmin, xmax, n_samples)
    x_step = (xmax - xmin) / max(n_samples - 1, 1)
    x_band = max(x_step * float(x_band_factor), np.finfo(float).eps)

    upper_rows: list[int] = []
    lower_rows: list[int] = []
    upper_targets: list[float] = []
    lower_targets: list[float] = []
    for target_x in targets:
        slice_dx = np.abs(slice_points[:, 0] - target_x)
        # Estimate and sample both branches from a local context. A narrow bin
        # can occasionally contain nodes from only one side; splitting that bin
        # by its own min/max incorrectly labels the same side as both branches.
        context_band = max(x_band, x_step * 0.5)
        context = np.flatnonzero(slice_dx <= context_band)
        if context.size < 2:
            typical_count = max(2, int(np.ceil(slice_rows.size / max(n_samples, 1))))
            count = min(slice_rows.size, min(24, typical_count))
            context = np.argpartition(slice_dx, count - 1)[:count]

        context_rows = slice_rows[context]
        context_values = points[context_rows, extrema_index]
        split_value = 0.5 * (float(context_values.min()) + float(context_values.max()))
        upper_candidates = context_rows[context_values >= split_value]
        lower_candidates = context_rows[context_values <= split_value]
        x_scale = max(x_band, x_step * 0.5, numeric_tolerance)
        # The slice coordinate is visually more sensitive than a small offset
        # inside the X neighbourhood.  Keep X inside the local half-station
        # context, then strongly prefer nodes that actually lie on the requested
        # plane (64x squared weight at the full user tolerance).
        plane_scale = max(float(plane_tolerance) * 0.125, numeric_tolerance)
        upper_rows.append(
            _closest_slice_row(points, plane_distance, upper_candidates, target_x, x_scale, plane_scale)
        )
        lower_rows.append(
            _closest_slice_row(points, plane_distance, lower_candidates, target_x, x_scale, plane_scale)
        )
        upper_targets.append(float(target_x))
        lower_targets.append(float(target_x))

    selected: list[tuple[int, float, str]] = []
    if sides in {"both", "lower"}:
        selected.extend(zip(lower_rows, lower_targets, ["lower"] * len(lower_rows)))
    if sides in {"both", "upper"}:
        selected.extend(zip(upper_rows, upper_targets, ["upper"] * len(upper_rows)))
    if deduplicate:
        selected = list({row: (row, target_x, side) for row, target_x, side in selected}.values())

    return [
        {
            "body": int(body_id),
            "reference": int(node_ids[row]),
            "point": [float(value) for value in points[row]],
            "source": "node",
            "side": side,
            "target_x": float(target_x),
            "x_error": abs(float(points[row, 0]) - float(target_x)),
            "plane_error": abs(float(points[row, plane_index]) - float(plane_value)),
        }
        for row, target_x, side in selected
    ]


def _closest_slice_row(
    points: np.ndarray,
    plane_distance: np.ndarray,
    rows: np.ndarray,
    target_x: float,
    x_scale: float,
    plane_scale: float,
) -> int:
    """Choose a branch node with a normalized X/slice distance score.

    This avoids sacrificing almost the whole plane tolerance for a tiny X gain,
    while still preventing a plane-perfect node from jumping to a distant X
    station.
    """
    if rows.size == 0:
        raise ValueError("Could not find both sides of the requested surface slice")
    dx = np.abs(points[rows, 0] - float(target_x))
    score = (dx / float(x_scale)) ** 2 + (plane_distance[rows] / float(plane_scale)) ** 2
    local = int(np.lexsort((dx, plane_distance[rows], score))[0])
    return int(rows[local])


def read_probe_payload(path: str | Path, bodies: list[SurfaceBody] | None = None) -> dict[str, object]:
    """Read probe_in.dat and return JSON-ready marker/fluid probe positions."""
    path = Path(path)
    if not path.exists():
        return {
            "ok": False,
            "exists": False,
            "path": str(path),
            "marker_count": 0,
            "fluid_count": 0,
            "markers": [],
            "fluids": [],
            "errors": [f"Missing probe file: {path}"],
        }

    spec = parse_probe_text(path.read_text(encoding="utf-8", errors="replace"))
    markers, marker_errors = resolve_marker_probes(spec, bodies or [])
    errors = spec.errors + marker_errors
    return {
        "ok": not errors,
        "exists": True,
        "path": str(path),
        "marker_count": spec.marker_count,
        "fluid_count": spec.fluid_count,
        "plotted_marker_count": len(markers),
        "unmatched_marker_count": max(0, spec.marker_count - len(markers)),
        "markers": markers,
        "fluids": [
            {"index": index, "point": [float(x), float(y), float(z)]}
            for index, (x, y, z) in enumerate(spec.fluid_points, start=1)
        ],
        "errors": errors,
    }


def parse_probe_text(text: str) -> ProbeSpec:
    """Parse the common PICAR probe_in.dat marker/fluid layout."""
    lines = text.splitlines()
    marker_start = _find_section(lines, "marker")
    fluid_start = _find_section(lines, "fluid")
    errors: list[str] = []

    marker_bodies: list[int] = []
    marker_refs: list[int] = []
    if marker_start is not None:
        marker_numbers = _numbers_between(lines, marker_start + 1, fluid_start)
        if marker_numbers:
            nmarker = max(0, int(marker_numbers[0]))
            marker_values = marker_numbers[1:]
            marker_bodies = [int(value) for value in marker_values[:nmarker]]
            marker_refs = [int(value) for value in marker_values[nmarker : nmarker * 2]]
            if len(marker_bodies) < nmarker:
                errors.append(f"Expected {nmarker} marker probe body ids, found {len(marker_bodies)}")
            if len(marker_refs) < nmarker:
                errors.append(f"Expected {nmarker} marker probe references, found {len(marker_refs)}")
        else:
            errors.append("Marker probe section is present but has no numeric count")

    fluid_points: list[tuple[float, float, float]] = []
    if fluid_start is not None:
        fluid_numbers = _numbers_between(lines, fluid_start + 1, None)
        if fluid_numbers:
            nfluid = max(0, int(fluid_numbers[0]))
            coords = fluid_numbers[1 : 1 + nfluid * 3]
            if len(coords) < nfluid * 3:
                errors.append(f"Expected {nfluid} fluid probe coordinate triples, found {len(coords) // 3}")
            for index in range(0, len(coords) - 2, 3):
                fluid_points.append((float(coords[index]), float(coords[index + 1]), float(coords[index + 2])))
    return ProbeSpec(marker_bodies=marker_bodies, marker_refs=marker_refs, fluid_points=fluid_points, errors=errors)


def resolve_marker_probes(spec: ProbeSpec, bodies: list[SurfaceBody]) -> tuple[list[dict[str, object]], list[str]]:
    markers: list[dict[str, object]] = []
    errors: list[str] = []
    max_unmatched_messages = 8
    unmatched_messages = 0
    body_lookups = [_body_lookup(body) for body in bodies]

    for index, (body_id, marker_ref) in enumerate(zip(spec.marker_bodies, spec.marker_refs), start=1):
        body_index = body_id - 1
        if body_index < 0 or body_index >= len(bodies):
            if unmatched_messages < max_unmatched_messages:
                errors.append(f"Marker probe {index} references missing body {body_id}")
                unmatched_messages += 1
            continue
        point, source = _marker_point(bodies[body_index], body_lookups[body_index], marker_ref)
        if point is None:
            if unmatched_messages < max_unmatched_messages:
                errors.append(f"Marker probe {index} on body {body_id} references missing element/node {marker_ref}")
                unmatched_messages += 1
            continue
        markers.append(
            {
                "index": index,
                "body": body_id,
                "reference": marker_ref,
                "source": source,
                "point": [float(point[0]), float(point[1]), float(point[2])],
            }
        )
    skipped = spec.marker_count - len(markers) - unmatched_messages
    if skipped > 0:
        errors.append(f"{skipped} additional marker probes could not be resolved")
    return markers, errors


def _body_lookup(body: SurfaceBody) -> dict[str, object]:
    return {
        "node_by_id": {int(row[0]): row[1:4] for row in body.nodes},
        "elem_by_id": {int(row[0]): row for row in body.elems},
    }


def _marker_point(
    body: SurfaceBody,
    lookup: dict[str, object],
    marker_ref: int,
) -> tuple[tuple[float, float, float], str] | tuple[None, None]:
    node_by_id = lookup["node_by_id"]
    elem_by_id = lookup["elem_by_id"]

    # Marker probes in existing cases reference surface marker/node ids.
    point = node_by_id.get(marker_ref)
    if point is not None:
        return (float(point[0]), float(point[1]), float(point[2])), "node"

    elem = elem_by_id.get(marker_ref)
    if elem is not None:
        point = _element_centroid(elem, node_by_id)
        if point is None:
            return None, None
        return point, "element"

    if 1 <= marker_ref <= body.elem_count:
        elem = body.elems[marker_ref - 1]
        point = _element_centroid(elem, node_by_id)
        if point is not None:
            return point, "element-index"

    return None, None


def _element_centroid(elem, node_by_id) -> tuple[float, float, float] | None:
    points = [node_by_id.get(int(node_id)) for node_id in elem[1:4]]
    if any(point is None for point in points):
        return None
    centroid = sum(points) / 3.0
    return float(centroid[0]), float(centroid[1]), float(centroid[2])


def _find_section(lines: list[str], name: str) -> int | None:
    needle = name.lower()
    for index, line in enumerate(lines):
        if needle in line.lower() and "probe" in line.lower():
            return index
    return None


def _numbers_between(lines: list[str], start: int, end: int | None) -> list[float]:
    out: list[float] = []
    for line in lines[start:end]:
        out.extend(_numbers(line.split("!", 1)[0]))
    return out


def _numbers(text: str) -> list[float]:
    return [
        float(item.replace("D", "E").replace("d", "e"))
        for item in re.findall(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?", text)
    ]
