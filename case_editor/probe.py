from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

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
