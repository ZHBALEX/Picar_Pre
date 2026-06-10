from __future__ import annotations

from math import ceil
from pathlib import Path

import numpy as np

from .generation import generate_mesh
from .io import MeshAxis, MeshConfig, read_grid_axis, read_mesh, read_mesh_input


def plot_plane_grid(
    mesh: MeshConfig,
    plane: str = "xy",
    dense_box: tuple[float, float, float, float] | None = None,
    save_path: str | Path | None = None,
    show: bool = True,
    dpi: int = 150,
    line_width: float = 0.4,
    alpha: float = 0.9,
) -> dict[str, object]:
    """Plot a decoupled 2D plane grid such as xy, xz, or yz."""
    _prepare_matplotlib(show)
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.patches import Rectangle

    axis_a, axis_b = _axes_for_plane(mesh, plane)
    a_values = axis_a.values
    b_values = axis_b.values
    a_min, a_max = float(a_values.min()), float(a_values.max())
    b_min, b_max = float(b_values.min()), float(b_values.max())

    horizontal = [((a_min, b), (a_max, b)) for b in b_values]
    vertical = [((a, b_min), (a, b_max)) for a in a_values]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.add_collection(LineCollection(horizontal, linewidths=line_width, alpha=alpha))
    ax.add_collection(LineCollection(vertical, linewidths=line_width, alpha=alpha))
    if dense_box is not None:
        ax.add_patch(
            Rectangle(
                (dense_box[0], dense_box[1]),
                dense_box[2],
                dense_box[3],
                fill=False,
                edgecolor="#C0392B",
                linewidth=2.0,
                zorder=5,
            )
        )
    ax.set_xlim(a_min, a_max)
    ax.set_ylim(b_min, b_max)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel(axis_a.name.upper())
    ax.set_ylabel(axis_b.name.upper())
    ax.set_title(f"Structured {plane.lower()} grid")
    ax.grid(False)
    plt.tight_layout()
    _finish_plot(fig, save_path, show, dpi)

    return {
        f"{axis_a.name}_nodes": a_values,
        f"{axis_b.name}_nodes": b_values,
        "domain": (a_min, b_min, a_max, b_max),
        "plane": plane.lower(),
        "dense_box": dense_box,
    }


def plot_axis_spacing(
    mesh: MeshConfig,
    axis: str = "all",
    save_path: str | Path | None = None,
    show: bool = True,
    dpi: int = 150,
) -> dict[str, object]:
    """Plot 1D grid spacing as a function of coordinate for one or all axes."""
    _prepare_matplotlib(show)
    import matplotlib.pyplot as plt

    axes = _selected_axes(mesh, axis)
    fig, axs = plt.subplots(len(axes), 1, figsize=(10, max(3.0, 2.4 * len(axes))), squeeze=False)
    summary: dict[str, object] = {}
    for ax_plot, mesh_axis in zip(axs[:, 0], axes):
        values = mesh_axis.values
        spacing = np.diff(values)
        centers = 0.5 * (values[:-1] + values[1:])
        ax_plot.plot(centers, spacing, linewidth=1.4)
        ax_plot.set_ylabel(f"d{mesh_axis.name}")
        ax_plot.set_xlabel(mesh_axis.name.upper())
        ax_plot.grid(True, alpha=0.25)
        ax_plot.set_title(f"{mesh_axis.name.upper()} spacing")
        summary[mesh_axis.name] = {
            "count": mesh_axis.count,
            "intervals": int(spacing.size),
            "min": float(spacing.min()) if spacing.size else 0.0,
            "max": float(spacing.max()) if spacing.size else 0.0,
        }
    plt.tight_layout()
    _finish_plot(fig, save_path, show, dpi)
    return summary


def plot_3d_grid(
    mesh: MeshConfig,
    save_path: str | Path | None = None,
    show: bool = True,
    dpi: int = 150,
    max_lines_per_axis: int = 24,
) -> dict[str, object]:
    """Plot a 3D structured-grid wireframe. Interactive when shown in a GUI backend."""
    if mesh.z is None:
        raise ValueError("3D view requires zgrid.dat")

    _prepare_matplotlib(show)
    import matplotlib.pyplot as plt

    x = mesh.x.values
    y = mesh.y.values
    z = mesh.z.values
    x_sel = _subsample(x, max_lines_per_axis)
    y_sel = _subsample(y, max_lines_per_axis)
    z_sel = _subsample(z, max_lines_per_axis)

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    for yy in y_sel:
        for zz in z_sel:
            ax.plot(x, np.full_like(x, yy), np.full_like(x, zz), color="#2f7fc1", linewidth=0.45, alpha=0.55)
    for xx in x_sel:
        for zz in z_sel:
            ax.plot(np.full_like(y, xx), y, np.full_like(y, zz), color="#2f7fc1", linewidth=0.45, alpha=0.55)
    for xx in x_sel:
        for yy in y_sel:
            ax.plot(np.full_like(z, xx), np.full_like(z, yy), z, color="#2f7fc1", linewidth=0.45, alpha=0.55)

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title("Structured 3D grid")
    ax.set_box_aspect(
        (
            max(float(x.max() - x.min()), 1e-12),
            max(float(y.max() - y.min()), 1e-12),
            max(float(z.max() - z.min()), 1e-12),
        )
    )
    plt.tight_layout()
    _finish_plot(fig, save_path, show, dpi)
    return {"x": mesh.x.count, "y": mesh.y.count, "z": mesh.z.count}


def plot_grid_from_input(
    input_path: str | Path,
    input_format: str = "auto",
    mode: str = "2d",
    plane: str = "xy",
    axis: str = "all",
    save_path: str | Path | None = None,
    show: bool = True,
    dpi: int = 150,
    max_lines_per_axis: int = 24,
) -> dict[str, object]:
    """Generate and visualize a mesh from mesh parameters."""
    params = read_mesh_input(input_path, input_format=input_format)
    mesh = generate_mesh(params, repair_degenerate=True)
    return plot_mesh(
        mesh,
        mode=mode,
        plane=plane,
        axis=axis,
        dense_box=_dense_box_for_plane(params, plane) if mode.lower() == "2d" else None,
        save_path=save_path,
        show=show,
        dpi=dpi,
        max_lines_per_axis=max_lines_per_axis,
    )


def plot_grid_from_files(
    x_path: str | Path,
    y_path: str | Path,
    z_path: str | Path | None = None,
    mode: str = "2d",
    plane: str = "xy",
    axis: str = "all",
    save_path: str | Path | None = None,
    show: bool = True,
    dpi: int = 150,
    max_lines_per_axis: int = 24,
) -> dict[str, object]:
    """Read grid files and visualize them in 1D, 2D, or 3D."""
    mesh = read_mesh_files(x_path, y_path, z_path)
    return plot_mesh(
        mesh,
        mode=mode,
        plane=plane,
        axis=axis,
        save_path=save_path,
        show=show,
        dpi=dpi,
        max_lines_per_axis=max_lines_per_axis,
    )


def read_mesh_files(x_path: str | Path, y_path: str | Path, z_path: str | Path | None = None) -> MeshConfig:
    """Read decoupled x/y/z grid files without requiring z for 2D cases."""
    x_path = Path(x_path)
    y_path = Path(y_path)
    z_path = Path(z_path) if z_path is not None and Path(z_path).exists() else None
    case_dir = x_path.parent
    if y_path.parent == case_dir and (z_path is None or z_path.parent == case_dir):
        return read_mesh(case_dir, require_z=False)
    return MeshConfig(
        x=read_grid_axis(x_path, "x"),
        y=read_grid_axis(y_path, "y"),
        z=read_grid_axis(z_path, "z") if z_path is not None else None,
    )


def plot_mesh(
    mesh: MeshConfig,
    mode: str = "2d",
    plane: str = "xy",
    axis: str = "all",
    dense_box: tuple[float, float, float, float] | None = None,
    save_path: str | Path | None = None,
    show: bool = True,
    dpi: int = 150,
    max_lines_per_axis: int = 24,
) -> dict[str, object]:
    """Dispatch mesh visualization by mode."""
    mode = mode.lower()
    if mode == "1d":
        return plot_axis_spacing(mesh, axis=axis, save_path=save_path, show=show, dpi=dpi)
    if mode == "2d":
        return plot_plane_grid(mesh, plane=plane, dense_box=dense_box, save_path=save_path, show=show, dpi=dpi)
    if mode == "3d":
        return plot_3d_grid(mesh, save_path=save_path, show=show, dpi=dpi, max_lines_per_axis=max_lines_per_axis)
    raise ValueError("mode must be one of: 1d, 2d, 3d")


def _axes_for_plane(mesh: MeshConfig, plane: str) -> tuple[MeshAxis, MeshAxis]:
    plane = plane.lower()
    mapping = {"x": mesh.x, "y": mesh.y, "z": mesh.z}
    if plane not in {"xy", "xz", "yz"}:
        raise ValueError("plane must be one of: xy, xz, yz")
    first = mapping[plane[0]]
    second = mapping[plane[1]]
    if first is None or second is None:
        raise ValueError(f"{plane} view requires {plane[0]}grid.dat and {plane[1]}grid.dat")
    return first, second


def _dense_box_for_plane(params: dict[str, object], plane: str) -> tuple[float, float, float, float] | None:
    """Return a matplotlib rectangle tuple for the dense region on a 2D plane."""
    plane = plane.lower()
    if plane not in {"xy", "xz", "yz"}:
        return None

    starts: dict[str, float] = {}
    lengths: dict[str, float] = {}
    for axis in plane:
        center_key = f"{axis}_center_dense"
        length_key = f"L{axis}_dense"
        if center_key not in params or length_key not in params:
            return None
        length = float(params[length_key])
        if length <= 0.0:
            return None
        starts[axis] = float(params[center_key]) - 0.5 * length
        lengths[axis] = length

    first, second = plane[0], plane[1]
    return starts[first], starts[second], lengths[first], lengths[second]


def _selected_axes(mesh: MeshConfig, axis: str) -> list[MeshAxis]:
    axis = axis.lower()
    mapping = {"x": mesh.x, "y": mesh.y, "z": mesh.z}
    if axis == "all":
        return [item for item in (mesh.x, mesh.y, mesh.z) if item is not None]
    if axis not in mapping:
        raise ValueError("axis must be x, y, z, or all")
    selected = mapping[axis]
    if selected is None:
        raise ValueError(f"{axis}grid.dat is required for axis={axis}")
    return [selected]


def _subsample(values: np.ndarray, max_count: int) -> np.ndarray:
    if values.size <= max_count:
        return values
    step = max(1, ceil(values.size / max_count))
    sampled = values[::step]
    if sampled[-1] != values[-1]:
        sampled = np.concatenate([sampled, values[-1:]])
    return sampled


def _prepare_matplotlib(show: bool) -> None:
    if not show:
        import matplotlib

        matplotlib.use("Agg", force=True)


def _finish_plot(fig, save_path: str | Path | None, show: bool, dpi: int) -> None:
    if save_path is not None:
        out = Path(save_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=dpi)
    if show:
        import matplotlib.pyplot as plt

        plt.show()
    else:
        import matplotlib.pyplot as plt

        plt.close(fig)


# Backward-compatible name used by older tests/scripts.
def plot_xy_grid(*args, **kwargs):
    return plot_plane_grid(*args, plane="xy", **kwargs)
