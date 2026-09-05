from __future__ import annotations

import shutil
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geometry.unstructure_surface.surface import SurfaceBody, read_surface, transform_body, write_surface

SURFACE_NAME = "unstruc_surface_in.dat"


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


@dataclass(frozen=True)
class PositionVariant:
    name: str
    case_dir: Path
    translations: dict[int, tuple[float, float, float]]


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
        groups.append(BodyGroup(body_ids, parse_series(raw.get("x")), parse_series(raw.get("y")), parse_series(raw.get("z"))))
    case_count = max(len(series) for group in groups for series in (group.x, group.y, group.z))
    for group in groups:
        for axis, series in zip("XYZ", (group.x, group.y, group.z)):
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


def translation_label(vector: tuple[float, float, float]) -> str:
    labels = []
    for axis, value in zip("XYZ", vector):
        if abs(value) <= 1e-14:
            continue
        labels.append(f"{axis}{'P' if value > 0 else 'M'}{position_value_label(value)}")
    return "_".join(labels) or "BASE"


def grouped_case_suffix(groups: list[BodyGroup], index: int) -> str:
    parts: list[str] = []
    for group in groups:
        vector = tuple(series[0] if len(series) == 1 else series[index] for series in (group.x, group.y, group.z))
        label = translation_label(vector)
        if len(groups) == 1:
            parts.append(label)
        elif label != "BASE":
            parts.extend((f"B{compact_body_ids(group.body_ids)}", label))
    return "_".join(parts) or "BASE"


def plan_grouped_variants(output_root: str | Path, groups: list[BodyGroup], prefix: str = "case") -> list[PositionVariant]:
    prefix = prefix.strip() or "case"
    if not re.fullmatch(r"[A-Za-z0-9_-]+", prefix):
        raise ValueError("Case prefix may contain only letters, numbers, underscore, and hyphen")
    count = max(len(series) for group in groups for series in (group.x, group.y, group.z))
    root = Path(output_root).expanduser().resolve()
    variants: list[PositionVariant] = []
    for index in range(count):
        translations: dict[int, tuple[float, float, float]] = {}
        for group in groups:
            vector = tuple(series[0] if len(series) == 1 else series[index] for series in (group.x, group.y, group.z))
            for body_id in group.body_ids:
                translations[body_id] = vector
        name = f"{prefix}_{grouped_case_suffix(groups, index)}"
        variants.append(PositionVariant(name, root / name, translations))
    names = [variant.name for variant in variants]
    if len(set(names)) != len(names):
        raise ValueError("Two cases have the same position-derived name; remove duplicate position combinations")
    return variants


def apply_translations(bodies: list[SurfaceBody], translations: dict[int, tuple[float, float, float]]) -> list[SurfaceBody]:
    return [transform_body(body, translate=translations[index]) if index in translations else body for index, body in enumerate(bodies, 1)]


def create_grouped_cases(source_case: str | Path, output_root: str | Path, groups: list[BodyGroup], prefix: str = "case") -> list[PositionVariant]:
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
    outputs = [(variant, apply_translations(bodies, variant.translations)) for variant in variants]
    root.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    try:
        for variant, moved_bodies in outputs:
            shutil.copytree(source, variant.case_dir)
            created.append(variant.case_dir)
            write_surface(variant.case_dir / SURFACE_NAME, moved_bodies)
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


def grouped_preview_payload(source_case: str | Path, groups: list[BodyGroup], prefix: str, output_root: str | Path) -> dict[str, object]:
    source = Path(source_case).expanduser().resolve()
    bodies = read_surface(source / SURFACE_NAME)
    variants = plan_grouped_variants(output_root, groups, prefix)
    changed_ids = {body_id for variant in variants for body_id, vector in variant.translations.items() if any(abs(value) > 0 for value in vector)}
    static = [{"body_id": index, **body_points_payload(body)} for index, body in enumerate(bodies, 1) if index not in changed_ids]
    cases = []
    for variant in variants:
        case_bodies = []
        for body_id in sorted(changed_ids):
            moved = transform_body(bodies[body_id - 1], translate=variant.translations[body_id])
            case_bodies.append({"body_id": body_id, **body_points_payload(moved)})
        cases.append({"name": variant.name, "path": str(variant.case_dir), "bodies": case_bodies})
    return {"static_bodies": static, "cases": cases}
