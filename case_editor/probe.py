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


def step_surface_marker(
    body: SurfaceBody,
    reference: int,
    *,
    screen_right: list[float] | tuple[float, float, float],
    screen_up: list[float] | tuple[float, float, float],
    direction: str,
) -> dict[str, object]:
    """Move a node marker by one mesh edge in a screen-space direction."""
    reference = int(reference)
    if direction not in {"left", "right", "up", "down"}:
        raise ValueError("direction must be left, right, up, or down")

    node_rows = {int(row[0]): row[1:4] for row in body.nodes}
    point = node_rows.get(reference)
    if point is None:
        raise ValueError("Surface arrow movement currently requires a node marker reference")

    neighbours: set[int] = set()
    for elem in body.elems:
        node_ids = [int(value) for value in elem[1:4]]
        if reference in node_ids:
            neighbours.update(node_id for node_id in node_ids if node_id != reference)
    candidates = [node_id for node_id in neighbours if node_id in node_rows]
    if not candidates:
        raise ValueError(f"Node marker {reference} has no connected surface neighbours")

    right = _unit_vector(screen_right, "screen_right")
    up = _unit_vector(screen_up, "screen_up")
    candidate_points = np.asarray([node_rows[node_id] for node_id in candidates], dtype=float)
    displacement = candidate_points - np.asarray(point, dtype=float)
    horizontal = displacement @ right
    vertical = displacement @ up
    forward, lateral = {
        "right": (horizontal, vertical),
        "left": (-horizontal, vertical),
        "up": (vertical, horizontal),
        "down": (-vertical, horizontal),
    }[direction]
    screen_length = np.hypot(forward, lateral)
    valid = (forward > max(float(screen_length.max()) * 1e-10, 1e-14)) & (screen_length > 0.0)
    if not np.any(valid):
        raise ValueError(f"Node marker {reference} has no connected neighbour toward screen {direction}")

    valid_rows = np.flatnonzero(valid)
    alignment = forward[valid_rows] / screen_length[valid_rows]
    aligned = alignment >= 0.35
    if not np.any(aligned):
        raise ValueError(
            f"Node marker {reference} has no sufficiently aligned surface edge toward screen {direction}; "
            "try another view"
        )
    valid_rows = valid_rows[aligned]
    alignment = alignment[aligned]
    # Directional alignment is the main criterion. Prefer the shorter edge when
    # two connected nodes project at essentially the same angle.
    local = int(np.lexsort((screen_length[valid_rows], -alignment))[0])
    selected = int(valid_rows[local])
    node_id = int(candidates[selected])
    selected_point = candidate_points[selected]
    return {
        "reference": node_id,
        "source": "node",
        "point": [float(value) for value in selected_point],
        "direction": direction,
    }


def _unit_vector(values, name: str) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain three finite coordinates")
    length = float(np.linalg.norm(vector))
    if length <= 1e-14:
        raise ValueError(f"{name} cannot be zero")
    return vector / length


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
    include_endpoints: bool = True,
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
    if include_endpoints:
        targets = np.linspace(xmin, xmax, n_samples)
    else:
        targets = np.linspace(xmin, xmax, n_samples + 2)[1:-1]
    if len(targets) > 1:
        x_step = float(np.mean(np.diff(targets)))
    elif include_endpoints:
        x_step = xmax - xmin
    else:
        x_step = 0.5 * (xmax - xmin)
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
        # The wider context is needed to identify both surface branches, but it
        # should not make a probe jump past an otherwise populated target band.
        # Prefer the user's narrow X band on each branch and widen only when
        # that branch genuinely has no local node.
        upper_candidates = _prefer_target_band(
            points,
            plane_distance,
            upper_candidates,
            target_x,
            x_band,
            plane_tolerance,
            numeric_tolerance,
        )
        lower_candidates = _prefer_target_band(
            points,
            plane_distance,
            lower_candidates,
            target_x,
            x_band,
            plane_tolerance,
            numeric_tolerance,
        )
        # Score with the scales the user actually requested.  The wider
        # half-station context is only for finding both branches; using it as the
        # X score scale made populated stations jump toward plane-perfect but
        # visibly off-centre nodes.  Likewise, plane_tolerance is a tolerance,
        # not a near-zero target that should receive a 64x squared penalty.
        x_scale = max(x_band, numeric_tolerance)
        plane_scale = max(float(plane_tolerance) * 0.75, numeric_tolerance)
        if sides == "both":
            upper_row, lower_row = _closest_slice_pair(
                points,
                plane_distance,
                upper_candidates,
                lower_candidates,
                target_x,
                x_scale,
                plane_scale,
            )
        else:
            upper_row = _closest_slice_row(
                points, plane_distance, upper_candidates, target_x, x_scale, plane_scale
            )
            lower_row = _closest_slice_row(
                points, plane_distance, lower_candidates, target_x, x_scale, plane_scale
            )
        upper_rows.append(upper_row)
        lower_rows.append(lower_row)
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


def _prefer_target_band(
    points: np.ndarray,
    plane_distance: np.ndarray,
    rows: np.ndarray,
    target_x: float,
    x_band: float,
    plane_tolerance: float,
    numeric_tolerance: float,
) -> np.ndarray:
    """Prefer the requested X band unless its slice quality is much worse."""
    near = rows[
        np.abs(points[rows, 0] - float(target_x))
        <= float(x_band) + float(numeric_tolerance)
    ]
    if near.size == 0:
        return rows
    near_plane = float(plane_distance[near].min())
    context_plane = float(plane_distance[rows].min())
    allowed_penalty = max(float(plane_tolerance) * 0.25, float(numeric_tolerance))
    return near if near_plane <= context_plane + allowed_penalty else rows


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


def _closest_slice_pair(
    points: np.ndarray,
    plane_distance: np.ndarray,
    upper_rows: np.ndarray,
    lower_rows: np.ndarray,
    target_x: float,
    x_scale: float,
    plane_scale: float,
) -> tuple[int, int]:
    """Choose upper/lower jointly so a probe pair shares one X station."""
    if upper_rows.size == 0 or lower_rows.size == 0:
        raise ValueError("Could not find both sides of the requested surface slice")

    upper_dx = np.abs(points[upper_rows, 0] - float(target_x))
    lower_dx = np.abs(points[lower_rows, 0] - float(target_x))
    upper_score = (upper_dx / float(x_scale)) ** 2 + (
        plane_distance[upper_rows] / float(plane_scale)
    ) ** 2
    lower_score = (lower_dx / float(x_scale)) ** 2 + (
        plane_distance[lower_rows] / float(plane_scale)
    ) ** 2

    pair_dx = np.abs(
        points[upper_rows, 0, None] - points[lower_rows, 0][None, :]
    )
    # Independent station scores already pull both nodes toward target_x.  This
    # additional half-weight term makes vertical pairing explicit without
    # overwhelming slice accuracy when the mesh has staggered node rings.
    score = (
        upper_score[:, None]
        + lower_score[None, :]
        + 0.5 * (pair_dx / float(x_scale)) ** 2
    )
    upper_local, lower_local = np.unravel_index(int(np.argmin(score)), score.shape)
    return int(upper_rows[upper_local]), int(lower_rows[lower_local])


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
        "layout": summarize_probe_layout(markers),
    }


def summarize_probe_layout(
    markers: list[dict[str, object]],
    *,
    plane_axis: str | None = None,
    plane_value: float | None = None,
) -> dict[str, object]:
    """Summarize marker-probe spacing and slice quality from resolved points."""
    points = _marker_points(markers)
    if points.size == 0:
        return {
            "marker_count": 0,
            "run_count": 0,
            "runs": [],
        }

    inferred_axis = _infer_probe_plane_axis(points) if plane_axis is None else plane_axis.lower()
    if inferred_axis not in {"y", "z"}:
        raise ValueError("plane_axis must be 'y' or 'z'")
    plane_index = 1 if inferred_axis == "y" else 2
    resolved_plane_value = (
        float(np.median(points[:, plane_index]))
        if plane_value is None
        else float(plane_value)
    )
    plane_errors = np.abs(points[:, plane_index] - resolved_plane_value)
    runs = _probe_marker_runs(markers)
    x_spacings: list[float] = []
    point_spacings: list[float] = []
    run_payloads: list[dict[str, object]] = []

    for run_index, run in enumerate(runs, start=1):
        run_points = _marker_points(run)
        run_item: dict[str, object] = {
            "body": int(run[0].get("body", 0)) if run else 0,
            "run": run_index,
            "count": len(run),
        }
        if len(run_points) >= 2:
            dx = np.diff(run_points[:, 0])
            ds = np.linalg.norm(np.diff(run_points, axis=0), axis=1)
            x_spacings.extend(float(abs(value)) for value in dx)
            point_spacings.extend(float(value) for value in ds)
            run_item.update(
                {
                    "min_x_spacing": float(np.min(np.abs(dx))),
                    "mean_x_spacing": float(np.mean(np.abs(dx))),
                    "max_x_spacing": float(np.max(np.abs(dx))),
                    "min_probe_spacing": float(np.min(ds)),
                    "mean_probe_spacing": float(np.mean(ds)),
                    "max_probe_spacing": float(np.max(ds)),
                }
            )
        run_payloads.append(run_item)

    x_errors = [float(marker["x_error"]) for marker in markers if "x_error" in marker]
    plane_meta_errors = [float(marker["plane_error"]) for marker in markers if "plane_error" in marker]
    pair_differences = _probe_pair_x_differences(runs)
    layout: dict[str, object] = {
        "marker_count": len(markers),
        "run_count": len(runs),
        "runs": run_payloads,
        "plane_axis": inferred_axis,
        "plane_value": resolved_plane_value,
        "max_plane_error": float(np.max(plane_errors)),
        "mean_plane_error": float(np.mean(plane_errors)),
        "has_target_errors": bool(x_errors or plane_meta_errors),
    }
    if plane_meta_errors:
        layout["max_plane_error"] = max(plane_meta_errors)
        layout["mean_plane_error"] = float(np.mean(plane_meta_errors))
    if x_errors:
        layout["max_x_error"] = max(x_errors)
        layout["mean_x_error"] = float(np.mean(x_errors))
    layout.update(_spacing_stats("x_spacing", x_spacings))
    layout.update(_spacing_stats("probe_spacing", point_spacings))
    layout.update(_spacing_difference_stats("x_spacing_difference", x_spacings))
    layout.update(_spacing_difference_stats("probe_spacing_difference", point_spacings))
    layout.update(_spacing_stats("pair_x_difference", pair_differences))
    return layout


def _marker_points(markers: list[dict[str, object]]) -> np.ndarray:
    points = []
    for marker in markers:
        point = marker.get("point")
        if isinstance(point, (list, tuple)) and len(point) == 3:
            values = [float(value) for value in point]
            if all(np.isfinite(value) for value in values):
                points.append(values)
    return np.asarray(points, dtype=float).reshape((-1, 3))


def _infer_probe_plane_axis(points: np.ndarray) -> str:
    y_span = float(np.ptp(points[:, 1]))
    z_span = float(np.ptp(points[:, 2]))
    return "y" if y_span <= z_span else "z"


def _probe_marker_runs(markers: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = {}
    for marker in markers:
        grouped.setdefault(int(marker.get("body", 0)), []).append(marker)

    runs: list[list[dict[str, object]]] = []
    for body_markers in grouped.values():
        points = _marker_points(body_markers)
        if points.size == 0:
            continue
        tolerance = max(float(np.ptp(points[:, 0])) * 1e-9, 1e-12)
        current: list[dict[str, object]] = []
        previous_x: float | None = None
        for marker in body_markers:
            point = marker.get("point")
            if not isinstance(point, (list, tuple)) or len(point) != 3:
                continue
            x_value = float(point[0])
            if current and previous_x is not None and x_value < previous_x - tolerance:
                runs.append(current)
                current = []
            current.append(marker)
            previous_x = x_value
        if current:
            runs.append(current)
    return runs


def _probe_pair_x_differences(runs: list[list[dict[str, object]]]) -> list[float]:
    differences: list[float] = []
    by_body: dict[int, list[list[dict[str, object]]]] = {}
    for run in runs:
        if run:
            by_body.setdefault(int(run[0].get("body", 0)), []).append(run)
    for body_runs in by_body.values():
        for first, second in zip(body_runs[::2], body_runs[1::2]):
            if len(first) != len(second):
                continue
            first_points = _marker_points(first)
            second_points = _marker_points(second)
            if len(first_points) != len(second_points):
                continue
            differences.extend(float(value) for value in np.abs(first_points[:, 0] - second_points[:, 0]))
    return differences


def _spacing_stats(prefix: str, values: list[float]) -> dict[str, object]:
    if not values:
        return {}
    array = np.asarray(values, dtype=float)
    return {
        f"min_{prefix}": float(np.min(array)),
        f"mean_{prefix}": float(np.mean(array)),
        f"max_{prefix}": float(np.max(array)),
    }


def _spacing_difference_stats(prefix: str, values: list[float]) -> dict[str, object]:
    if len(values) < 2:
        return {}
    array = np.asarray(values, dtype=float)
    difference = np.abs(array - float(np.mean(array)))
    return {
        f"mean_{prefix}": float(np.mean(difference)),
        f"max_{prefix}": float(np.max(difference)),
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
