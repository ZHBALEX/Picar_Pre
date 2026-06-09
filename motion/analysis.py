from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geometry.unstructure_surface.surface import SurfaceBody

from .fort import fort_motion_info, read_frame


AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


@dataclass(frozen=True)
class HarmonicFit:
    """First-harmonic fit y(t)=offset+a*cos(wt)+b*sin(wt)."""

    offset: float
    cos_coeff: float
    sin_coeff: float
    amplitude: float
    phase: float
    rmse: float
    samples: int

    def equation(self, variable: str, period: float = 1.0) -> str:
        return (
            f"{variable}(t) = {self.offset:.8g} "
            f"+ {self.amplitude:.8g} * cos(2*pi*t/{period:.8g} + {self.phase:.8g})"
        )


@dataclass(frozen=True)
class CentroidMotionAnalysis:
    """Centroid time series and harmonic fits."""

    times: np.ndarray
    centroids: np.ndarray
    fits: dict[str, HarmonicFit]


@dataclass(frozen=True)
class CenterlineMotionAnalysis:
    """Station-wise centerline time series and harmonic fits."""

    times: np.ndarray
    stations: np.ndarray
    values: np.ndarray
    value_axes: tuple[str, ...]
    fits: dict[str, list[HarmonicFit | None]]


def frame_indices(frame_count: int, stride: int = 1) -> list[int]:
    """Return frame indices sampled by stride, always including the last frame."""
    if frame_count <= 0:
        return []
    stride = max(1, int(stride))
    indices = list(range(0, frame_count, stride))
    if indices[-1] != frame_count - 1:
        indices.append(frame_count - 1)
    return indices


def fit_first_harmonic(times: np.ndarray, values: np.ndarray, period: float = 1.0) -> HarmonicFit:
    """Fit values to offset + a*cos(wt) + b*sin(wt)."""
    times = np.asarray(times, dtype=float)
    values = np.asarray(values, dtype=float)
    mask = np.isfinite(times) & np.isfinite(values)
    if np.count_nonzero(mask) < 3:
        raise ValueError("At least three finite samples are required for a harmonic fit")

    t = times[mask]
    y = values[mask]
    omega = 2.0 * np.pi / float(period)
    design = np.column_stack([np.ones_like(t), np.cos(omega * t), np.sin(omega * t)])
    coeffs, *_ = np.linalg.lstsq(design, y, rcond=None)
    fitted = design @ coeffs
    residual = y - fitted

    offset, cos_coeff, sin_coeff = (float(item) for item in coeffs)
    amplitude = float(np.hypot(cos_coeff, sin_coeff))
    phase = float(np.arctan2(-sin_coeff, cos_coeff))
    rmse = float(np.sqrt(np.mean(residual**2)))
    return HarmonicFit(
        offset=offset,
        cos_coeff=cos_coeff,
        sin_coeff=sin_coeff,
        amplitude=amplitude,
        phase=phase,
        rmse=rmse,
        samples=int(len(y)),
    )


def analyze_centroid_motion(
    body: SurfaceBody,
    fort_path: str | Path,
    stride: int = 1,
    period: float = 1.0,
    component_order: str = "xyz",
    motion_mode: str = "velocity",
) -> CentroidMotionAnalysis:
    """Analyze centroid motion from surface coordinates plus fort.* displacement."""
    info = fort_motion_info(fort_path)
    if info.node_count != body.node_count:
        raise ValueError(f"fort node count {info.node_count} does not match surface node count {body.node_count}")

    indices = frame_indices(info.frame_count, stride=stride)
    times = np.zeros(len(indices), dtype=float)
    centroids = np.zeros((len(indices), 3), dtype=float)
    base_centroid = body.points.mean(axis=0)
    points = body.points.copy()
    target_rows = {frame_index: row for row, frame_index in enumerate(indices)}

    if motion_mode == "velocity":
        for frame_index in range(indices[-1] + 1):
            header, velocity = read_frame(fort_path, frame_index, node_count=body.node_count, component_order=component_order)
            points = points + velocity * header.dt
            if frame_index in target_rows:
                row = target_rows[frame_index]
                times[row] = header.time
                centroids[row] = points.mean(axis=0)
    else:
        for row, frame_index in enumerate(indices):
            header, motion = read_frame(fort_path, frame_index, node_count=body.node_count, component_order=component_order)
            times[row] = header.time
            if motion_mode == "relative":
                centroids[row] = base_centroid + motion.mean(axis=0)
            elif motion_mode == "displacement":
                centroids[row] = base_centroid + motion.mean(axis=0)
            else:
                raise ValueError("motion_mode must be 'velocity', 'relative', or 'displacement'")

    fits = {axis: fit_first_harmonic(times, centroids[:, idx], period=period) for axis, idx in AXIS_INDEX.items()}
    return CentroidMotionAnalysis(times=times, centroids=centroids, fits=fits)


def analyze_centerline_motion(
    body: SurfaceBody,
    fort_path: str | Path,
    *,
    axis: str = "x",
    value_axes: tuple[str, ...] = ("y", "z"),
    bins: int = 80,
    stride: int = 1,
    period: float = 1.0,
    component_order: str = "xyz",
    motion_mode: str = "velocity",
) -> CenterlineMotionAnalysis:
    """Fit station-wise centerline motion along a reference coordinate axis.

    Stations are fixed bins in the reference surface coordinates. For each time
    frame, deformed node positions are averaged inside each station bin.
    """
    info = fort_motion_info(fort_path)
    if info.node_count != body.node_count:
        raise ValueError(f"fort node count {info.node_count} does not match surface node count {body.node_count}")

    axis = axis.lower()
    if axis not in AXIS_INDEX:
        raise ValueError("axis must be one of: x, y, z")
    value_axes = tuple(item.lower() for item in value_axes)
    for value_axis in value_axes:
        if value_axis not in AXIS_INDEX:
            raise ValueError("value axes must be chosen from: x, y, z")

    axis_idx = AXIS_INDEX[axis]
    value_indices = [AXIS_INDEX[item] for item in value_axes]
    ref_coord = body.points[:, axis_idx]
    edges = np.linspace(float(ref_coord.min()), float(ref_coord.max()), int(bins) + 1)
    stations = 0.5 * (edges[:-1] + edges[1:])
    bin_ids = np.clip(np.searchsorted(edges, ref_coord, side="right") - 1, 0, len(stations) - 1)
    bin_counts = np.bincount(bin_ids, minlength=len(stations)).astype(float)

    indices = frame_indices(info.frame_count, stride=stride)
    times = np.zeros(len(indices), dtype=float)
    values = np.full((len(indices), len(stations), len(value_axes)), np.nan, dtype=float)
    points = body.points.copy()
    target_rows = {frame_index: row for row, frame_index in enumerate(indices)}

    if motion_mode == "velocity":
        for frame_index in range(indices[-1] + 1):
            header, velocity = read_frame(fort_path, frame_index, node_count=body.node_count, component_order=component_order)
            points = points + velocity * header.dt
            if frame_index in target_rows:
                row = target_rows[frame_index]
                times[row] = header.time
                _fill_centerline_values(values, row, points, value_indices, bin_ids, bin_counts)
    else:
        for row, frame_index in enumerate(indices):
            header, motion = read_frame(fort_path, frame_index, node_count=body.node_count, component_order=component_order)
            times[row] = header.time
            if motion_mode == "relative":
                deformed = body.points.mean(axis=0).reshape(1, 3) + motion
            elif motion_mode == "displacement":
                deformed = body.points + motion
            else:
                raise ValueError("motion_mode must be 'velocity', 'relative', or 'displacement'")
            _fill_centerline_values(values, row, deformed, value_indices, bin_ids, bin_counts)

    fits: dict[str, list[HarmonicFit | None]] = {value_axis: [] for value_axis in value_axes}
    for value_col, value_axis in enumerate(value_axes):
        for station_idx in range(len(stations)):
            series = values[:, station_idx, value_col]
            if np.count_nonzero(np.isfinite(series)) < 3:
                fits[value_axis].append(None)
            else:
                fits[value_axis].append(fit_first_harmonic(times, series, period=period))

    return CenterlineMotionAnalysis(times=times, stations=stations, values=values, value_axes=value_axes, fits=fits)


def format_centroid_report(analysis: CentroidMotionAnalysis, period: float = 1.0) -> str:
    """Format a centroid motion analysis report."""
    lines = [
        "Centroid Motion",
        "===============",
        f"Samples    : {len(analysis.times)}",
        f"Time range : {analysis.times.min():.8g} .. {analysis.times.max():.8g}",
        "",
        "First Harmonic Fits",
        "===================",
    ]
    for axis in ("x", "y", "z"):
        fit = analysis.fits[axis]
        lines.extend(
            [
                f"{axis.upper()}",
                "-" * 1,
                f"  {fit.equation(axis, period=period)}",
                f"  cos coeff : {fit.cos_coeff:.8g}",
                f"  sin coeff : {fit.sin_coeff:.8g}",
                f"  amplitude : {fit.amplitude:.8g}",
                f"  phase     : {fit.phase:.8g}",
                f"  rmse      : {fit.rmse:.8g}",
            ]
        )
    return "\n".join(lines)


def _fill_centerline_values(
    values: np.ndarray,
    row: int,
    points: np.ndarray,
    value_indices: list[int],
    bin_ids: np.ndarray,
    bin_counts: np.ndarray,
) -> None:
    for value_col, value_idx in enumerate(value_indices):
        sums = np.bincount(bin_ids, weights=points[:, value_idx], minlength=len(bin_counts))
        valid = bin_counts > 0
        values[row, valid, value_col] = sums[valid] / bin_counts[valid]


def format_centerline_report(analysis: CenterlineMotionAnalysis, axis: str = "x", period: float = 1.0, preview: int = 8) -> str:
    """Format a compact centerline motion report."""
    valid_count = sum(1 for fit in analysis.fits[analysis.value_axes[0]] if fit is not None)
    lines = [
        "Centerline Motion",
        "=================",
        f"Samples       : {len(analysis.times)}",
        f"Stations      : {len(analysis.stations)}",
        f"Valid stations: {valid_count}",
        f"Reference axis: {axis}",
        f"Value axes    : {', '.join(analysis.value_axes)}",
        "",
        "Preview",
        "=======",
    ]

    shown = 0
    for idx, station in enumerate(analysis.stations):
        row_parts = [f"{axis}={station:.8g}"]
        has_fit = False
        for value_axis in analysis.value_axes:
            fit = analysis.fits[value_axis][idx]
            if fit is None:
                continue
            has_fit = True
            row_parts.append(f"{value_axis}: offset={fit.offset:.6g}, amp={fit.amplitude:.6g}, phase={fit.phase:.6g}, rmse={fit.rmse:.3g}")
        if has_fit:
            lines.append("  " + " | ".join(row_parts))
            shown += 1
        if shown >= preview:
            break

    if shown == 0:
        lines.append("  No valid station fits.")
    else:
        lines.append("")
        lines.append(f"Equation form: q(t) = offset + amplitude*cos(2*pi*t/{period:.8g} + phase)")
    return "\n".join(lines)


def write_centerline_csv(path: str | Path, analysis: CenterlineMotionAnalysis, axis: str = "x") -> Path:
    """Write centerline harmonic coefficients to CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["station_axis", "station", "value_axis", "offset", "cos_coeff", "sin_coeff", "amplitude", "phase", "rmse", "samples"])
        for station_idx, station in enumerate(analysis.stations):
            for value_axis in analysis.value_axes:
                fit = analysis.fits[value_axis][station_idx]
                if fit is None:
                    continue
                writer.writerow(
                    [
                        axis,
                        f"{station:.16g}",
                        value_axis,
                        f"{fit.offset:.16g}",
                        f"{fit.cos_coeff:.16g}",
                        f"{fit.sin_coeff:.16g}",
                        f"{fit.amplitude:.16g}",
                        f"{fit.phase:.16g}",
                        f"{fit.rmse:.16g}",
                        fit.samples,
                    ]
                )
    return path
