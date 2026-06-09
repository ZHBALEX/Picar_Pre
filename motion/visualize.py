from __future__ import annotations

from pathlib import Path

import numpy as np

from geometry.unstructure_surface.surface import SurfaceBody

from .fort import fort_motion_info, read_frame


def deformed_body(body: SurfaceBody, displacement: np.ndarray) -> SurfaceBody:
    """Return a body displaced by one fort.* frame."""
    displacement = np.asarray(displacement, dtype=float)
    if displacement.shape != body.points.shape:
        raise ValueError(f"Displacement shape {displacement.shape} does not match body points {body.points.shape}")

    nodes = body.nodes.copy()
    nodes[:, 1:4] = body.points + displacement
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
    save_path: str | Path | None = None,
    show: bool = True,
    figsize: tuple[float, float] = (12.0, 5.0),
):
    """Plot sampled prescribed motion as a 2D projected envelope."""
    if not show or save_path is not None:
        import matplotlib

        matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    info = fort_motion_info(fort_path)
    frame = _normalize_frame(frame, info.frame_count)
    axes = _plane_axes(plane)
    sample_indices = sample_frame_indices(info.frame_count, samples, highlight_frame=frame)

    fig, ax = plt.subplots(figsize=figsize)
    all_points = []

    for sample_idx in sample_indices:
        _, displacement = read_frame(fort_path, sample_idx, node_count=body.node_count)
        deformed = deformed_body(body, displacement)
        all_points.append(deformed.points[:, axes])
        color = "red" if sample_idx == frame else "0.65"
        linewidth = 1.8 if sample_idx == frame else 0.45
        alpha = 0.95 if sample_idx == frame else 0.35
        zorder = 5 if sample_idx == frame else 1
        lines = _projected_lines(deformed, axes)
        if lines:
            ax.add_collection(LineCollection(lines, colors=color, linewidths=linewidth, alpha=alpha, zorder=zorder))
        else:
            pts = deformed.points[:, axes]
            ax.plot(pts[:, 0], pts[:, 1], color=color, linewidth=linewidth, alpha=alpha, zorder=zorder)

    all_points_arr = np.vstack(all_points)
    _set_equal_2d_limits(ax, all_points_arr)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.18)
    ax.set_xlabel(plane[0].upper())
    ax.set_ylabel(plane[1].upper())
    ax.set_title(f"Body motion envelope: frame {frame} / {info.frame_count - 1}, time={read_frame(fort_path, frame, body.node_count)[0].time:.6g}")

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
    save_path: str | Path | None = None,
    show: bool = True,
):
    """Plot sampled prescribed motion as a 3D envelope."""
    import pyvista as pv

    from geometry.unstructure_surface.visualize import body_to_pyvista_mesh

    info = fort_motion_info(fort_path)
    frame = _normalize_frame(frame, info.frame_count)
    sample_indices = sample_frame_indices(info.frame_count, samples, highlight_frame=frame)

    plotter = pv.Plotter(off_screen=not show)
    for sample_idx in sample_indices:
        _, displacement = read_frame(fort_path, sample_idx, node_count=body.node_count)
        deformed = deformed_body(body, displacement)
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
    layered_boundary = _layered_boundary_lines(body, axes)
    if layered_boundary:
        return layered_boundary

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


def _layered_boundary_lines(body: SurfaceBody, axes: tuple[int, int]) -> list[list[np.ndarray]]:
    """Return one representative closed layer for thin side-wall XY projections."""
    if axes != (0, 1) or body.node_count < 6:
        return []

    z_values = body.points[:, 2]
    z_span = float(z_values.max() - z_values.min())
    xy_span = float((body.points[:, :2].max(axis=0) - body.points[:, :2].min(axis=0)).max())
    if xy_span <= 0.0 or z_span > 0.1 * xy_span:
        return []

    rounded_z = np.round(z_values, decimals=10)
    unique_z = np.unique(rounded_z)
    if len(unique_z) < 2 or len(unique_z) > 20:
        return []

    target_z = unique_z[np.argmin(np.abs(unique_z - np.median(unique_z)))]
    layer_idx = np.flatnonzero(rounded_z == target_z)
    if len(layer_idx) < 3:
        return []

    points = body.points[layer_idx][:, axes]
    lines = [[points[idx], points[idx + 1]] for idx in range(len(points) - 1)]
    lines.append([points[-1], points[0]])
    return lines


def _set_equal_2d_limits(ax, points: np.ndarray) -> None:
    xy_min = points.min(axis=0)
    xy_max = points.max(axis=0)
    center = 0.5 * (xy_min + xy_max)
    span = max(float((xy_max - xy_min).max()), 1.0e-12)
    margin = 0.06 * span
    half = 0.5 * span + margin
    ax.set_xlim(center[0] - half, center[0] + half)
    ax.set_ylim(center[1] - half, center[1] + half)
