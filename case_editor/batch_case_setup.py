from __future__ import annotations

import shutil
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geometry.unstructure_surface.surface import SurfaceBody, read_surface, transform_body, transform_points, write_surface
from motion.fort import rotate_fort_motion
from motion.project import MotionProject

SURFACE_NAME = "unstruc_surface_in.dat"
_MOTION_CENTER_CACHE: dict[tuple[object, ...], tuple[np.ndarray, list[dict[str, object]]]] = {}


@dataclass(frozen=True)
class BatchVariant:
    offset: float
    name: str
    case_dir: Path


@dataclass(frozen=True)
class BodyGroup:
    body_ids: tuple[int, ...]
    x: tuple[float, ...]
    y: tuple[float, ...]
    z: tuple[float, ...]
    rx: tuple[float, ...]
    ry: tuple[float, ...]
    rz: tuple[float, ...]


@dataclass(frozen=True)
class PositionVariant:
    name: str
    case_dir: Path
    translations: dict[int, tuple[float, float, float]]
    rotations: dict[int, tuple[float, float, float]]


def parse_offsets(text: str) -> list[float]:
    tokens = text.replace(",", " ").split()
    if not tokens:
        raise ValueError("Enter at least one offset")
    values = [float(token) for token in tokens]
    if not all(np.isfinite(value) for value in values):
        raise ValueError("Offsets must be finite numbers")
    if len(set(values)) != len(values):
        raise ValueError("Offsets must be unique")
    return values


def parse_series(value: object) -> tuple[float, ...]:
    tokens = str(value if value is not None else "0").replace(",", " ").split()
    if not tokens:
        return (0.0,)
    values = tuple(float(token) for token in tokens)
    if not all(np.isfinite(item) for item in values):
        raise ValueError("Position offsets must be finite numbers")
    return values


def parse_body_ids(value: object, body_count: int) -> tuple[int, ...]:
    ids: list[int] = []
    for token in str(value).replace(",", " ").split():
        if "-" in token:
            parts = token.split("-")
            if len(parts) != 2:
                raise ValueError(f"Invalid body range: {token}")
            start, end = (int(part) for part in parts)
            if end < start:
                raise ValueError(f"Body range must be ascending: {token}")
            ids.extend(range(start, end + 1))
        else:
            ids.append(int(token))
    if not ids:
        raise ValueError("Each body group needs at least one body id")
    if len(set(ids)) != len(ids):
        raise ValueError("A body id may appear only once within a group")
    invalid = [body_id for body_id in ids if body_id < 1 or body_id > body_count]
    if invalid:
        raise ValueError(f"Body ids {invalid} are outside 1..{body_count}")
    return tuple(ids)


def parse_body_groups(raw_groups: object, body_count: int) -> list[BodyGroup]:
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError("Add at least one body group")
    groups: list[BodyGroup] = []
    used: set[int] = set()
    for raw in raw_groups:
        if not isinstance(raw, dict):
            raise ValueError("Invalid body group")
        body_ids = parse_body_ids(raw.get("body_ids", ""), body_count)
        overlap = used.intersection(body_ids)
        if overlap:
            raise ValueError(f"Bodies {sorted(overlap)} appear in more than one group")
        used.update(body_ids)
        groups.append(BodyGroup(
            body_ids,
            parse_series(raw.get("x")), parse_series(raw.get("y")), parse_series(raw.get("z")),
            parse_series(raw.get("rx")), parse_series(raw.get("ry")), parse_series(raw.get("rz")),
        ))
    case_count = max(len(series) for group in groups for series in (group.x, group.y, group.z, group.rx, group.ry, group.rz))
    for group in groups:
        for axis, series in zip(("X", "Y", "Z", "RX", "RY", "RZ"), (group.x, group.y, group.z, group.rx, group.ry, group.rz)):
            if len(series) not in {1, case_count}:
                raise ValueError(f"Group {format_body_ids(group.body_ids)} {axis} has {len(series)} values; expected 1 or {case_count}")
    return groups


def format_body_ids(body_ids: tuple[int, ...]) -> str:
    return ",".join(map(str, body_ids))


def compact_body_ids(body_ids: tuple[int, ...]) -> str:
    if len(body_ids) > 1 and body_ids == tuple(range(body_ids[0], body_ids[-1] + 1)):
        return f"{body_ids[0]}-{body_ids[-1]}"
    return "+".join(map(str, body_ids))


def position_value_label(value: float) -> str:
    return f"{abs(value):.12g}".replace(".", "p").replace("+", "p").replace("-", "m")


def vector_label(vector: tuple[float, float, float], axes: tuple[str, str, str]) -> str:
    labels = []
    for axis, value in zip(axes, vector):
        if abs(value) <= 1e-14:
            continue
        labels.append(f"{axis}{'P' if value > 0 else 'M'}{position_value_label(value)}")
    return "_".join(labels) or "BASE"


def grouped_case_suffix(groups: list[BodyGroup], index: int) -> str:
    parts: list[str] = []
    for group in groups:
        translation = tuple(series[0] if len(series) == 1 else series[index] for series in (group.x, group.y, group.z))
        rotation = tuple(series[0] if len(series) == 1 else series[index] for series in (group.rx, group.ry, group.rz))
        labels = [label for label in (vector_label(translation, ("X", "Y", "Z")), vector_label(rotation, ("RX", "RY", "RZ"))) if label != "BASE"]
        label = "_".join(labels) or "BASE"
        if len(groups) == 1:
            parts.append(label)
        elif label != "BASE":
            parts.extend((f"B{compact_body_ids(group.body_ids)}", label))
    return "_".join(parts) or "BASE"


def plan_grouped_variants(output_root: str | Path, groups: list[BodyGroup], prefix: str = "case") -> list[PositionVariant]:
    prefix = prefix.strip() or "case"
    if not re.fullmatch(r"[A-Za-z0-9_-]+", prefix):
        raise ValueError("Case prefix may contain only letters, numbers, underscore, and hyphen")
    count = max(len(series) for group in groups for series in (group.x, group.y, group.z, group.rx, group.ry, group.rz))
    root = Path(output_root).expanduser().resolve()
    variants: list[PositionVariant] = []
    for index in range(count):
        translations: dict[int, tuple[float, float, float]] = {}
        rotations: dict[int, tuple[float, float, float]] = {}
        for group in groups:
            vector = tuple(series[0] if len(series) == 1 else series[index] for series in (group.x, group.y, group.z))
            rotation = tuple(series[0] if len(series) == 1 else series[index] for series in (group.rx, group.ry, group.rz))
            for body_id in group.body_ids:
                translations[body_id] = vector
                rotations[body_id] = rotation
        name = f"{prefix}_{grouped_case_suffix(groups, index)}"
        variants.append(PositionVariant(name, root / name, translations, rotations))
    names = [variant.name for variant in variants]
    if len(set(names)) != len(names):
        raise ValueError("Two cases have the same position-derived name; remove duplicate position combinations")
    return variants


def group_rotation_pivots(bodies: list[SurfaceBody], groups: list[BodyGroup]) -> dict[int, np.ndarray]:
    pivots: dict[int, np.ndarray] = {}
    for group in groups:
        points = np.vstack([bodies[body_id - 1].points for body_id in group.body_ids])
        # Keep the group's own center fixed instead of orbiting the global origin.
        pivot = points.mean(axis=0)
        for body_id in group.body_ids:
            pivots[body_id] = pivot
    return pivots


def _group_has_rotation(group: BodyGroup) -> bool:
    return any(abs(value) > 1e-14 for series in (group.rx, group.ry, group.rz) for value in series)


def motion_rotation_pivots(
    source: Path,
    bodies: list[SurfaceBody],
    groups: list[BodyGroup],
    *,
    fort_start: int,
    component_order: str,
) -> tuple[dict[int, np.ndarray], list[dict[str, object]]]:
    """Resolve rotating groups around their cycle-average fort motion center."""
    pivots = group_rotation_pivots(bodies, groups)
    reports: list[dict[str, object]] = []
    project = MotionProject(source, fort_start=fort_start)
    surface_stat = (source / SURFACE_NAME).stat()
    for group in groups:
        if not _group_has_rotation(group):
            continue
        fort_stats = []
        for body_id in group.body_ids:
            fort_path = project.fort_path_for_body(body_id)
            if not fort_path.is_file():
                raise FileNotFoundError(f"Rotation requires matching motion file for body {body_id}: {fort_path}")
            stat = fort_path.stat()
            fort_stats.append((str(fort_path), stat.st_size, stat.st_mtime_ns))
        key = (
            str(source), surface_stat.st_size, surface_stat.st_mtime_ns,
            group.body_ids, int(fort_start), component_order.lower(), tuple(fort_stats),
        )
        cached = _MOTION_CENTER_CACHE.get(key)
        if cached is None:
            center, stats = project.cycle_average_group_center(
                list(group.body_ids), component_order=component_order, motion_mode="velocity"
            )
            diagnostics = [
                {"body_id": item.body_id, "frames": item.frames, "max_cycle_drift": item.max_cycle_drift}
                for item in stats
            ]
            cached = (center.copy(), diagnostics)
            _MOTION_CENTER_CACHE[key] = cached
        center, diagnostics = cached
        for body_id in group.body_ids:
            pivots[body_id] = center
        reports.append({
            "body_ids": list(group.body_ids),
            "center": center.tolist(),
            "source": "cycle-average fort trajectory",
            "forts": diagnostics,
        })
    return pivots, reports


def transform_body_about_pivot(
    body: SurfaceBody,
    rotation: tuple[float, float, float],
    translation: tuple[float, float, float],
    pivot: np.ndarray,
) -> SurfaceBody:
    nodes = body.nodes.copy()
    centered = nodes[:, 1:4] - pivot.reshape(1, 3)
    nodes[:, 1:4] = transform_points(centered, rotation=rotation) + pivot.reshape(1, 3) + np.asarray(translation).reshape(1, 3)
    return SurfaceBody(nodes=nodes, elems=body.elems.copy(), bbox=body.bbox)


def apply_variant_transform(bodies: list[SurfaceBody], variant: PositionVariant, pivots: dict[int, np.ndarray]) -> list[SurfaceBody]:
    return [
        transform_body_about_pivot(body, variant.rotations[index], variant.translations[index], pivots[index])
        if index in variant.translations else body
        for index, body in enumerate(bodies, 1)
    ]


def create_grouped_cases(
    source_case: str | Path,
    output_root: str | Path,
    groups: list[BodyGroup],
    prefix: str = "case",
    *,
    fort_start: int = 41,
    component_order: str = "xyz",
) -> list[PositionVariant]:
    source = Path(source_case).expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Source case directory not found: {source}")
    bodies = read_surface(source / SURFACE_NAME)
    variants = plan_grouped_variants(output_root, groups, prefix)
    root = Path(output_root).expanduser().resolve()
    if root == source or source in root.parents:
        raise ValueError("Output root cannot be the source case or inside it")
    conflicts = [variant.case_dir for variant in variants if variant.case_dir.exists()]
    if conflicts:
        raise FileExistsError("Refusing to overwrite existing cases: " + ", ".join(map(str, conflicts)))
    if fort_start <= 0:
        raise ValueError("fort_start must be positive")
    pivots, _pivot_reports = motion_rotation_pivots(
        source, bodies, groups, fort_start=fort_start, component_order=component_order
    )
    outputs = [(variant, apply_variant_transform(bodies, variant, pivots)) for variant in variants]
    root.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        for variant, moved_bodies in outputs:
            shutil.copytree(source, variant.case_dir)
            created.append(variant.case_dir)
            write_surface(variant.case_dir / SURFACE_NAME, moved_bodies)
            for body_id, rotation in variant.rotations.items():
                if not any(abs(value) > 1e-14 for value in rotation):
                    continue
                fort_path = variant.case_dir / f"fort.{fort_start + body_id - 1}"
                temp_path = variant.case_dir / f".{fort_path.name}.rotate.tmp"
                rotate_fort_motion(fort_path, temp_path, rotation=rotation, component_order=component_order)
                temp_path.replace(fort_path)
    except Exception:
        for path in reversed(created):
            shutil.rmtree(path)
        raise
    return variants


def offset_label(value: float) -> str:
    text = f"{abs(value):.12g}".replace(".", "p")
    return f"m{text}" if value < 0 else text


def plan_variants(output_root: str | Path, axis: str, offsets: list[float]) -> list[BatchVariant]:
    axis = axis.lower()
    if axis not in {"x", "y", "z"}:
        raise ValueError("Axis must be x, y, or z")
    root = Path(output_root).expanduser().resolve()
    return [BatchVariant(v, f"move_{axis}_{offset_label(v)}", root / f"move_{axis}_{offset_label(v)}") for v in offsets]


def transformed_bodies(source_case: str | Path, body_id: int, axis: str, offset: float) -> list[SurfaceBody]:
    source = Path(source_case).expanduser().resolve()
    bodies = read_surface(source / SURFACE_NAME)
    if body_id < 1 or body_id > len(bodies):
        raise ValueError(f"Body id {body_id} is out of range 1..{len(bodies)}")
    delta = [0.0, 0.0, 0.0]
    delta[{"x": 0, "y": 1, "z": 2}[axis.lower()]] = float(offset)
    return [transform_body(body, translate=delta) if i == body_id else body for i, body in enumerate(bodies, 1)]


def create_batch_cases(source_case: str | Path, output_root: str | Path, body_id: int, axis: str, offsets: list[float]) -> list[BatchVariant]:
    """Copy a source case and translate one body in each new, non-existing case."""
    source = Path(source_case).expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Source case directory not found: {source}")
    if not (source / SURFACE_NAME).is_file():
        raise FileNotFoundError(f"Surface file not found: {source / SURFACE_NAME}")
    variants = plan_variants(output_root, axis, offsets)
    root = Path(output_root).expanduser().resolve()
    if root == source or source in root.parents:
        raise ValueError("Output root cannot be the source case or inside it")
    conflicts = [v.case_dir for v in variants if v.case_dir.exists()]
    if conflicts:
        raise FileExistsError("Refusing to overwrite existing cases: " + ", ".join(map(str, conflicts)))
    outputs = [(v, transformed_bodies(source, body_id, axis, v.offset)) for v in variants]
    root.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        for variant, bodies in outputs:
            shutil.copytree(source, variant.case_dir)
            created.append(variant.case_dir)
            write_surface(variant.case_dir / SURFACE_NAME, bodies)
    except Exception:
        for path in reversed(created):
            shutil.rmtree(path)
        raise
    return variants


def body_points_payload(body: SurfaceBody, max_points: int = 35_000) -> dict[str, object]:
    stride = max(1, int(np.ceil(body.node_count / max_points)))
    return {"points": body.nodes[::stride, 1:4].tolist(), "node_count": body.node_count, "stride": stride}


def batch_preview_payload(source_case: str | Path, body_id: int, axis: str, offsets: list[float]) -> dict[str, object]:
    source = Path(source_case).expanduser().resolve()
    bodies = read_surface(source / SURFACE_NAME)
    if body_id < 1 or body_id > len(bodies):
        raise ValueError(f"Body id {body_id} is out of range 1..{len(bodies)}")
    delta_index = {"x": 0, "y": 1, "z": 2}[axis.lower()]
    moving = bodies[body_id - 1]
    static = [body_points_payload(body) for index, body in enumerate(bodies, 1) if index != body_id]
    variants = []
    for offset in offsets:
        delta = [0.0, 0.0, 0.0]
        delta[delta_index] = float(offset)
        variants.append(body_points_payload(transform_body(moving, translate=delta)))
    return {"static_bodies": static, "variants": variants}


def grouped_preview_payload(
    source_case: str | Path,
    groups: list[BodyGroup],
    prefix: str,
    output_root: str | Path,
    *,
    fort_start: int = 41,
    component_order: str = "xyz",
) -> dict[str, object]:
    source = Path(source_case).expanduser().resolve()
    bodies = read_surface(source / SURFACE_NAME)
    variants = plan_grouped_variants(output_root, groups, prefix)
    pivots, pivot_reports = motion_rotation_pivots(
        source, bodies, groups, fort_start=fort_start, component_order=component_order
    )
    changed_ids = {
        body_id for variant in variants for body_id in variant.translations
        if any(abs(value) > 1e-14 for value in variant.translations[body_id] + variant.rotations[body_id])
    }
    static = [{"body_id": index, **body_points_payload(body)} for index, body in enumerate(bodies, 1) if index not in changed_ids]
    cases = []
    for variant in variants:
        case_bodies = []
        for body_id in sorted(changed_ids):
            moved = transform_body_about_pivot(
                bodies[body_id - 1], variant.rotations[body_id], variant.translations[body_id], pivots[body_id]
            )
            case_bodies.append({"body_id": body_id, **body_points_payload(moved)})
        cases.append({"name": variant.name, "path": str(variant.case_dir), "bodies": case_bodies})
    return {"static_bodies": static, "cases": cases, "rotation_pivots": pivot_reports}
