from __future__ import annotations

from pathlib import Path

import numpy as np

from geometry.unstructure_surface.surface import SurfaceBody

from .analysis import CenterlineMotionAnalysis
from .fort import fort_motion_info, read_frame


def deformed_body(body: SurfaceBody, motion: np.ndarray, mode: str = "displacement") -> SurfaceBody:
    """Return one body frame from fort.* motion data.

    mode="relative" treats fort values as marker positions relative to the
    reference body center. mode="displacement" treats fort values as nodal
    displacements added to the reference surface.
    """
    motion = np.asarray(motion, dtype=float)
    if motion.shape != body.points.shape:
        raise ValueError(f"Motion shape {motion.shape} does not match body points {body.points.shape}")

    nodes = body.nodes.copy()
    if mode == "relative":
        nodes[:, 1:4] = body.points.mean(axis=0).reshape(1, 3) + motion
    elif mode == "displacement":
        nodes[:, 1:4] = body.points + motion
    else:
        raise ValueError("mode must be 'relative' or 'displacement'")
    return SurfaceBody(nodes=nodes, elems=body.elems.copy(), bbox=body.bbox)


def body_from_points(body: SurfaceBody, points: np.ndarray) -> SurfaceBody:
    """Return a body with replaced point coordinates and preserved topology."""
    points = np.asarray(points, dtype=float)
    if points.shape != body.points.shape:
        raise ValueError(f"Point shape {points.shape} does not match body points {body.points.shape}")
    nodes = body.nodes.copy()
    nodes[:, 1:4] = points
    return SurfaceBody(nodes=nodes, elems=body.elems.copy(), bbox=body.bbox)


def sample_frame_indices(frame_count: int, samples: int, highlight_frame: int | None = None) -> list[int]:
    """Return sorted unique frame indices for motion envelope plotting."""
    if frame_count <= 0:
        return []
    samples = max(1, min(int(samples), frame_count))
    indices = set(np.linspace(0, frame_count - 1, samples, dtype=int).tolist())
    if highlight_frame is not None:
        indices.add(int(highlight_frame))
    return sorted(indices)


def plot_motion_2d(
    body: SurfaceBody,
    fort_path: str | Path,
    *,
    frame: int = -1,
    samples: int = 24,
    plane: str = "xy",
    component_order: str = "xyz",
    motion_mode: str = "velocity",
    save_path: str | Path | None = None,
    show: bool = True,
    figsize: tuple[float, float] = (8.0, 8.0),
):
    """Plot sampled prescribed motion as a 2D projected envelope."""
    if not show or save_path is not None:
        import matplotlib

        matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    _apply_jfm_style(plt)

    info = fort_motion_info(fort_path)
    frame = _normalize_frame(frame, info.frame_count)
    axes = _plane_axes(plane)
    sample_indices = sample_frame_indices(info.frame_count, samples, highlight_frame=frame)
    frame_points, _ = motion_points_for_frames(
        body,
        fort_path,
        sample_indices,
        component_order=component_order,
        motion_mode=motion_mode,
    )

    fig, ax = plt.subplots(figsize=figsize)
    all_points = []
    line_indices = _reference_polyline_indices(body, axes)

    for sample_idx in sample_indices:
        deformed = body_from_points(body, frame_points[sample_idx])
        all_points.append(deformed.points[:, axes])
        color = "red" if sample_idx == frame else "0.65"
        linewidth = 1.8 if sample_idx == frame else 0.45
        alpha = 0.95 if sample_idx == frame else 0.35
        zorder = 5 if sample_idx == frame else 1
        lines = _polyline_from_indices(deformed.points[:, axes], line_indices) if line_indices is not None else _projected_lines(deformed, axes)
        if lines:
            ax.add_collection(LineCollection(lines, colors=color, linewidths=linewidth, alpha=alpha, zorder=zorder))
        else:
            pts = deformed.points[:, axes]
            ax.plot(pts[:, 0], pts[:, 1], color=color, linewidth=linewidth, alpha=alpha, zorder=zorder)

    all_points_arr = np.vstack(all_points)
    _set_equal_2d_limits(ax, all_points_arr)
    ax.set_aspect("equal", adjustable="box")
    if hasattr(ax, "set_box_aspect"):
        ax.set_box_aspect(1)
    ax.grid(False)
    ax.set_xlabel(_axis_math_label(plane[0]))
    ax.set_ylabel(_axis_math_label(plane[1]))
    _apply_jfm_axes(ax)

    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        print()
        print("Saved Figure")
        print("============")
        print(f"Path: {save_path}")

    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig, ax


def plot_motion_3d(
    body: SurfaceBody,
    fort_path: str | Path,
    *,
    frame: int = -1,
    samples: int = 16,
    component_order: str = "xyz",
    motion_mode: str = "velocity",
    save_path: str | Path | None = None,
    show: bool = True,
):
    """Plot sampled prescribed motion as a 3D envelope."""
    import pyvista as pv

    from geometry.unstructure_surface.visualize import body_to_pyvista_mesh

    info = fort_motion_info(fort_path)
    frame = _normalize_frame(frame, info.frame_count)
    sample_indices = sample_frame_indices(info.frame_count, samples, highlight_frame=frame)
    frame_points, _ = motion_points_for_frames(
        body,
        fort_path,
        sample_indices,
        component_order=component_order,
        motion_mode=motion_mode,
    )

    plotter = pv.Plotter(off_screen=not show)
    for sample_idx in sample_indices:
        deformed = body_from_points(body, frame_points[sample_idx])
        mesh = body_to_pyvista_mesh(deformed) if body.elem_count > 0 else pv.PolyData(deformed.points)
        if sample_idx == frame:
            plotter.add_mesh(mesh, color="red", show_edges=True, line_width=3, point_size=4)
        else:
            plotter.add_mesh(mesh, color="lightgray", show_edges=True, opacity=0.22, line_width=1, point_size=2)

    plotter.show_axes()
    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        plotter.show(screenshot=str(save_path), auto_close=not show)
        print()
        print("Saved Figure")
        print("============")
        print(f"Path: {save_path}")
    elif show:
        plotter.show()
    else:
        plotter.close()


def plot_midline_motion(
    analysis: CenterlineMotionAnalysis,
    *,
    station_axis: str = "x",
    value_axis: str = "y",
    normalize_station: bool = True,
    center: bool = True,
    envelope: bool = True,
    save_path: str | Path | None = None,
    show: bool = True,
    figsize: tuple[float, float] = (7.0, 3.6),
):
    """Plot station-wise midline motion as phase curves plus an envelope."""
    if not show or save_path is not None:
        import matplotlib

        matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    _apply_jfm_style(plt)

    value_axis = value_axis.lower()
    if value_axis not in analysis.value_axes:
        raise ValueError(f"value_axis must be one of: {', '.join(analysis.value_axes)}")
    value_col = analysis.value_axes.index(value_axis)

    stations = np.asarray(analysis.stations, dtype=float)
    values = np.asarray(analysis.values[:, :, value_col], dtype=float)
    valid_stations = np.isfinite(stations) & np.any(np.isfinite(values), axis=0)
    stations = stations[valid_stations]
    values = values[:, valid_stations]
    if stations.size == 0:
        raise ValueError("No valid centerline stations are available for plotting")

    if normalize_station:
        span = float(stations.max() - stations.min())
        if span <= 0.0:
            length_scale = 1.0
            x_values = stations.copy()
        else:
            length_scale = span
            x_values = (stations - stations.min()) / span
        x_label = rf"${station_axis}/L_B$"
    else:
        length_scale = 1.0
        x_values = stations
        x_label = _axis_math_label(station_axis)

    y_values = values.copy()
    if center:
        station_offsets = np.nanmean(y_values, axis=0)
        y_values = y_values - station_offsets.reshape(1, -1)
    y_values = y_values / length_scale
    if normalize_station:
        y_label = rf"${value_axis}/L_B$"
    else:
        y_label = _axis_math_label(value_axis)

    fig, ax = plt.subplots(figsize=figsize)
    colors = plt.cm.Reds(np.linspace(0.3, 1.0, len(analysis.times)))
    for row, color in enumerate(colors):
        ax.plot(x_values, y_values[row], color=color, linewidth=1.0)

    if envelope:
        upper = np.nanmax(y_values, axis=0)
        lower = np.nanmin(y_values, axis=0)
        ax.plot(x_values, upper, color="green", linestyle="--", linewidth=1.6, alpha=0.55)
        ax.plot(x_values, lower, color="green", linestyle="--", linewidth=1.6, alpha=0.55)

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(False)
    _apply_jfm_axes(ax)
    fig.tight_layout()

    if save_path:
        save_path = Path(save_path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
        print()
        print("Saved Figure")
        print("============")
        print(f"Path: {save_path}")

    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig, ax


def motion_points_for_frames(
    body: SurfaceBody,
    fort_path: str | Path,
    frame_indices: list[int],
    *,
    component_order: str = "xyz",
    motion_mode: str = "velocity",
) -> tuple[dict[int, np.ndarray], dict[int, float]]:
    """Return physical body points for requested fort frame indices."""
    if not frame_indices:
        return {}, {}
    info = fort_motion_info(fort_path)
    targets = set(int(item) for item in frame_indices)
    for frame_index in targets:
        _normalize_frame(frame_index, info.frame_count)

    if motion_mode == "velocity":
        points = body.points.copy()
        result: dict[int, np.ndarray] = {}
        times: dict[int, float] = {}
        max_target = max(targets)
        for frame_index in range(max_target + 1):
            header, velocity = read_frame(fort_path, frame_index, node_count=body.node_count, component_order=component_order)
            points = points + velocity * header.dt
            if frame_index in targets:
                result[frame_index] = points.copy()
                times[frame_index] = header.time
        return result, times

    result = {}
    times = {}
    for frame_index in sorted(targets):
        header, motion = read_frame(fort_path, frame_index, node_count=body.node_count, component_order=component_order)
        result[frame_index] = deformed_body(body, motion, mode=motion_mode).points
        times[frame_index] = header.time
    return result, times


def _normalize_frame(frame: int, frame_count: int) -> int:
    frame = int(frame)
    if frame < 0:
        frame = frame_count + frame
    if frame < 0 or frame >= frame_count:
        raise ValueError(f"frame must be in [-{frame_count}, {frame_count - 1}], got {frame}")
    return frame


def _plane_axes(plane: str) -> tuple[int, int]:
    plane = plane.lower()
    axes = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}
    if plane not in axes:
        raise ValueError("plane must be one of: xy, xz, yz")
    return axes[plane]


def _projected_lines(body: SurfaceBody, axes: tuple[int, int]) -> list[list[np.ndarray]]:
    points = body.points[:, axes]
    if body.elem_count > 0:
        node_map = {int(body.nodes[i, 0]): i for i in range(len(body.nodes))}
        lines = []
        for _, n1, n2, n3 in body.elems:
            try:
                p1 = points[node_map[int(n1)]]
                p2 = points[node_map[int(n2)]]
                p3 = points[node_map[int(n3)]]
            except KeyError:
                continue
            lines.extend([[p1, p2], [p2, p3], [p3, p1]])
        return lines

    if len(points) < 2:
        return []
    lines = [[points[idx], points[idx + 1]] for idx in range(len(points) - 1)]
    lines.append([points[-1], points[0]])
    return lines


def _reference_polyline_indices(body: SurfaceBody, axes: tuple[int, int]) -> np.ndarray | None:
    """Return representative reference node indices for clean 2D outlines."""
    if axes != (0, 1) or body.node_count < 6:
        return None

    z_values = body.points[:, 2]
    z_span = float(z_values.max() - z_values.min())
    xy_span = float((body.points[:, :2].max(axis=0) - body.points[:, :2].min(axis=0)).max())
    if xy_span <= 0.0 or z_span > 0.1 * xy_span:
        return None

    rounded_z = np.round(z_values, decimals=10)
    unique_z = np.unique(rounded_z)
    if len(unique_z) < 2 or len(unique_z) > 20:
        return None

    target_z = unique_z[0]
    layer_idx = np.flatnonzero(rounded_z == target_z)
    if len(layer_idx) < 3:
        return None

    return layer_idx


def _polyline_from_indices(points: np.ndarray, indices: np.ndarray) -> list[list[np.ndarray]]:
    points = points[indices]
    lines = [[points[idx], points[idx + 1]] for idx in range(len(points) - 1)]
    lines.append([points[-1], points[0]])
    return lines


def _apply_jfm_style(plt) -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "axes.linewidth": 1.0,
            "axes.titlesize": 0,
            "axes.labelsize": 18,
            "xtick.labelsize": 14,
            "ytick.labelsize": 14,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "legend.frameon": False,
        }
    )


def _apply_jfm_axes(ax) -> None:
    ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(width=1.0, length=4.0, pad=6.0)


def _axis_math_label(axis: str) -> str:
    return rf"${axis.lower()}$"


def _set_equal_2d_limits(ax, points: np.ndarray) -> None:
    xy_min = points.min(axis=0)
    xy_max = points.max(axis=0)
    center = 0.5 * (xy_min + xy_max)
    span = max(float((xy_max - xy_min).max()), 1.0e-12)
    margin = 0.06 * span
    half = 0.5 * span + margin
    ax.set_xlim(center[0] - half, center[0] + half)
    ax.set_ylim(center[1] - half, center[1] + half)
