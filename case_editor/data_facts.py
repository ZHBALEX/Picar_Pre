from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from geometry.unstructure_surface.surface import read_surface
from mesh.io import read_grid_axis
from motion.fort import fort_motion_info


@dataclass(frozen=True)
class DataScanIssue:
    severity: str
    message: str


@dataclass(frozen=True)
class GridAxisFacts:
    name: str
    path: Path
    count: int
    minimum: float
    maximum: float
    uniform: bool
    minimum_spacing: float | None
    maximum_spacing: float | None


@dataclass(frozen=True)
class SurfaceBodyFacts:
    body_id: int
    node_count: int
    element_count: int


@dataclass(frozen=True)
class FortFileFacts:
    body_id: int
    fort_number: int
    path: Path
    node_count: int
    frame_count: int
    dt: float
    first_time: float
    last_time: float


@dataclass
class CaseFacts:
    case_dir: Path
    grids: dict[str, GridAxisFacts] = field(default_factory=dict)
    surface_bodies: list[SurfaceBodyFacts] = field(default_factory=list)
    surface_present: bool = False
    fort_files: list[FortFileFacts] = field(default_factory=list)
    issues: list[DataScanIssue] = field(default_factory=list)


def scan_case_data(case_dir: str | Path, fort_start: int = 41) -> CaseFacts:
    """Read data files into solver-independent facts without editing the case."""
    case_dir = Path(case_dir).resolve()
    facts = CaseFacts(case_dir=case_dir)

    for axis_name in "xyz":
        path = case_dir / f"{axis_name}grid.dat"
        if not path.exists():
            continue
        try:
            axis = read_grid_axis(path, axis_name)
            spacing = axis.spacing
            uniform = spacing.size <= 1 or bool(
                np.allclose(
                    spacing,
                    spacing[0],
                    rtol=1e-9,
                    atol=max(1e-12, abs(float(spacing[0])) * 1e-10),
                )
            )
            facts.grids[axis_name] = GridAxisFacts(
                name=axis_name,
                path=path,
                count=axis.count,
                minimum=axis.minimum,
                maximum=axis.maximum,
                uniform=uniform,
                minimum_spacing=float(np.min(spacing)) if spacing.size else None,
                maximum_spacing=float(np.max(spacing)) if spacing.size else None,
            )
        except Exception as exc:
            facts.issues.append(DataScanIssue("error", f"Cannot read {path.name}: {exc}"))

    surface_path = case_dir / "unstruc_surface_in.dat"
    facts.surface_present = surface_path.exists()
    if facts.surface_present:
        try:
            bodies = read_surface(surface_path)
            facts.surface_bodies = [
                SurfaceBodyFacts(body_id=index, node_count=body.node_count, element_count=body.elem_count)
                for index, body in enumerate(bodies, start=1)
            ]
        except Exception as exc:
            facts.issues.append(DataScanIssue("error", f"Cannot read {surface_path.name}: {exc}"))

    for path in sorted(case_dir.glob("fort.*")):
        suffix = path.name.split(".", 1)[1]
        if not suffix.isdigit():
            continue
        fort_number = int(suffix)
        body_id = fort_number - int(fort_start) + 1
        if body_id < 1:
            continue
        try:
            info = fort_motion_info(path)
            facts.fort_files.append(
                FortFileFacts(
                    body_id=body_id,
                    fort_number=fort_number,
                    path=path,
                    node_count=info.node_count,
                    frame_count=info.frame_count,
                    dt=info.dt,
                    first_time=info.first_time,
                    last_time=info.last_time,
                )
            )
        except Exception as exc:
            facts.issues.append(DataScanIssue("error", f"Cannot read {path.name}: {exc}"))

    return facts
