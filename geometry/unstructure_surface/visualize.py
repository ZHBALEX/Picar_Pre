from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np

from .surface import SurfaceBody, sample_two_sides_indices


COLOR_CYCLE = ["#ed6b9f", "#bebed8", "#9bc9dd", "#a2d59b", "#ffd4af", "red", "blue", "green"]


def body_to_pyvista_mesh(body: SurfaceBody):
    """Convert a SurfaceBody to PyVista PolyData."""
    import pyvista as pv

    cells = []
    for _, n1, n2, n3 in body.elems:
        cells.extend([3, int(n1) - 1, int(n2) - 1, int(n3) - 1])
    return pv.PolyData(body.points, np.asarray(cells, dtype=int))


def visualize_multi_mesh(bodies: Iterable[SurfaceBody]) -> None:
    """Display multiple surface meshes in one PyVista scene."""
    import pyvista as pv

    plotter = pv.Plotter()
    for body in bodies:
        plotter.add_mesh(body_to_pyvista_mesh(body), show_edges=True)
    plotter.show_axes()
    plotter.show()


def visualize_body_mesh(body: SurfaceBody, show_edges: bool = True) -> None:
    """Display one triangular surface mesh."""
    import pyvista as pv

    plotter = pv.Plotter()
    plotter.add_mesh(body_to_pyvista_mesh(body), show_edges=show_edges, edge_color="black", color="lightblue")
    plotter.show_axes()
    plotter.show()


def plot_pointcloud_multi(bodies_or_points: Iterable[SurfaceBody | np.ndarray]) -> None:
    """Display multiple body point clouds with different colors."""
    import pyvista as pv

    plotter = pv.Plotter()
    for idx, item in enumerate(bodies_or_points):
        pts = item.points if isinstance(item, SurfaceBody) else np.asarray(item)
        if pts.size == 0:
            continue
        plotter.add_points(pv.PolyData(pts), color=COLOR_CYCLE[idx % len(COLOR_CYCLE)], point_size=4, opacity=0.5)
    plotter.show_axes()
    plotter.show()


def plot_pointcloud_all(points: np.ndarray) -> None:
    """Display one point cloud."""
    import pyvista as pv

    plotter = pv.Plotter()
    plotter.add_points(pv.PolyData(np.asarray(points)), render_points_as_spheres=True, point_size=5)
    plotter.show_axes()
    plotter.show_bounds()
    plotter.show()


def plot_fast(points: np.ndarray) -> None:
    """Compatibility alias for plotting one point cloud."""
    plot_pointcloud_all(points)


def show_sample_points(
    bodies: list[SurfaceBody],
    body_id: int = 1,
    target: float = 4.0,
    plane_axis: str = "y",
    n_samples: int = 30,
    z_tol: float = 1.0e-6,
    x_band_factor: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Show sampled upper/lower points for one body and return their 1-based node ids."""
    import pyvista as pv

    body = bodies[body_id - 1]
    upper_idx, lower_idx, upper_nid, lower_nid = sample_two_sides_indices(
        body.points,
        z_target=target,
        n_samples=n_samples,
        z_tol=z_tol,
        x_band_factor=x_band_factor,
        dedup=True,
        plane_axis=plane_axis,
    )

    print()
    print("Sample Points")
    print("=" * 13)
    print(f"Body id       : {body_id}")
    print(f"Plane axis    : {plane_axis}")
    print(f"Target layer  : {target}")
    print(f"Upper count   : {len(upper_nid)}")
    print(f"Lower count   : {len(lower_nid)}")
    print("Upper node ids:")
    print("\t".join(map(str, upper_nid)))
    print("Lower node ids:")
    print("\t".join(map(str, lower_nid)))

    plotter = pv.Plotter()
    for item in bodies:
        plotter.add_mesh(pv.PolyData(item.points), style="points", point_size=4, color="lightgray")
    plotter.add_mesh(pv.PolyData(body.points[upper_idx]), style="points", point_size=12, color="red")
    plotter.add_mesh(pv.PolyData(body.points[lower_idx]), style="points", point_size=12, color="blue")
    plotter.show_axes()
    plotter.show()

    return upper_nid, lower_nid


def _triangle_lines_xy(nodes: np.ndarray, elems: np.ndarray) -> list[list[np.ndarray]]:
    points = nodes[:, 1:3]
    node_map = {int(nodes[i, 0]): i for i in range(len(nodes))}
    lines = []
    for elem in elems:
        try:
            p1 = points[node_map[int(elem[1])]]
            p2 = points[node_map[int(elem[2])]]
            p3 = points[node_map[int(elem[3])]]
        except KeyError:
            continue
        lines.extend([[p1, p2], [p2, p3], [p3, p1]])
    return lines


def _boundary_lines_xy(nodes: np.ndarray) -> list[list[np.ndarray]]:
    """Build closed XY boundary segments from node order."""
    if len(nodes) < 2:
        return []
    points = nodes[:, 1:3]
    lines = [[points[idx], points[idx + 1]] for idx in range(len(points) - 1)]
    lines.append([points[-1], points[0]])
    return lines


def plot_body_2d(
    body: SurfaceBody,
    z_slice: float | None = None,
    z_tol: float = 0.001,
    show_nodes: bool = False,
    figsize: tuple[float, float] = (10, 10),
    title: str | None = None,
    save_path: str | Path | None = None,
):
    """Plot one body as an XY mesh projection with optional node markers near a z slice."""
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    points = body.points
    fig, ax = plt.subplots(figsize=figsize)

    lines = _triangle_lines_xy(body.nodes, body.elems)
    if lines:
        ax.add_collection(LineCollection(lines, colors="blue", linewidths=0.5, alpha=0.6))
    else:
        boundary_lines = _boundary_lines_xy(body.nodes)
        if boundary_lines:
            ax.add_collection(LineCollection(boundary_lines, colors="blue", linewidths=1.5, alpha=0.9))

    if z_slice is not None:
        node_mask = np.abs(points[:, 2] - z_slice) < z_tol
        if not np.any(node_mask):
            print()
            print("2D Plot Notice")
            print("=" * 14)
            print(f"No nodes found near z={z_slice} with tolerance {z_tol}.")
            print("Node markers will use all nodes if requested.")
            node_mask = np.ones(len(points), dtype=bool)
    else:
        node_mask = np.ones(len(points), dtype=bool)

    if show_nodes:
        ax.scatter(points[node_mask, 0], points[node_mask, 1], c="red", s=10, zorder=5)

    x_min, x_max = points[:, 0].min(), points[:, 0].max()
    y_min, y_max = points[:, 1].min(), points[:, 1].max()
    margin = 0.05
    ax.set_xlim(x_min - margin * (x_max - x_min), x_max + margin * (x_max - x_min))
    ax.set_ylim(y_min - margin * (y_max - y_min), y_max + margin * (y_max - y_min))
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")

    if title is None:
        body_kind = "boundary" if body.elem_count == 0 else "mesh"
        title = f"Body {body_kind} projection" if z_slice is None else f"Body {body_kind} near z={z_slice:.3f}"
    ax.set_title(title)

    range_text = f"X: [{x_min:.3f}, {x_max:.3f}]\nY: [{y_min:.3f}, {y_max:.3f}]"
    if z_slice is not None:
        range_text += f"\nZ slice: {z_slice:.3f}"
    ax.text(
        0.98,
        0.98,
        range_text,
        transform=ax.transAxes,
        verticalalignment="top",
        horizontalalignment="right",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
        fontsize=10,
    )

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print()
        print("Saved Figure")
        print("=" * 12)
        print(f"Path: {save_path}")

    plt.show()
    return fig, ax


def compare_bodies_2d_overlay(
    body_a: SurfaceBody,
    body_b: SurfaceBody,
    labels: tuple[str, str] = ("Original", "Transformed"),
    colors: tuple[str, str] = ("blue", "red"),
    figsize: tuple[float, float] = (12, 12),
    save_path: str | Path | None = None,
):
    """Overlay two body meshes in XY projection."""
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    fig, ax = plt.subplots(figsize=figsize)
    all_points = np.vstack([body_a.points[:, :2], body_b.points[:, :2]])
    x_min, y_min = all_points.min(axis=0)
    x_max, y_max = all_points.max(axis=0)

    for body, label, color in zip([body_a, body_b], labels, colors):
        lines = _triangle_lines_xy(body.nodes, body.elems)
        if lines:
            ax.add_collection(LineCollection(lines, colors=color, linewidths=0.8, alpha=0.6, label=label))

    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.3)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.legend(loc="upper left")
    ax.set_title("Mesh comparison")

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print()
        print("Saved Figure")
        print("=" * 12)
        print(f"Path: {save_path}")

    plt.show()
    return fig, ax
