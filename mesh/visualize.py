from __future__ import annotations

from pathlib import Path

from .generation import generate_mesh_from_input
from .io import MeshConfig, read_mesh


def plot_xy_grid(
    mesh: MeshConfig,
    save_path: str | Path | None = None,
    show: bool = True,
    dpi: int = 150,
    line_width: float = 0.4,
    alpha: float = 0.9,
) -> dict[str, object]:
    """Plot the x-y projection of a structured grid."""
    if not show:
        import matplotlib

        matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    x_values = mesh.x.values
    y_values = mesh.y.values
    x_min, x_max = float(x_values.min()), float(x_values.max())
    y_min, y_max = float(y_values.min()), float(y_values.max())

    h_segments = [((x_min, y), (x_max, y)) for y in y_values]
    v_segments = [((x, y_min), (x, y_max)) for x in x_values]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.add_collection(LineCollection(h_segments, linewidths=line_width, alpha=alpha))
    ax.add_collection(LineCollection(v_segments, linewidths=line_width, alpha=alpha))
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_title("Structured x-y grid")
    ax.grid(False)
    plt.tight_layout()

    if save_path is not None:
        out = Path(save_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=dpi)
    if show:
        plt.show()
    else:
        plt.close(fig)

    return {
        "x_nodes": x_values,
        "y_nodes": y_values,
        "domain": (x_min, y_min, x_max, y_max),
    }


def plot_grid_from_input(
    input_path: str | Path,
    save_path: str | Path | None = None,
    show: bool = True,
    dpi: int = 150,
) -> dict[str, object]:
    """Generate and plot an x-y grid from mesh parameters."""
    return plot_xy_grid(generate_mesh_from_input(input_path), save_path=save_path, show=show, dpi=dpi)


def plot_grid_from_files(
    x_path: str | Path,
    y_path: str | Path,
    z_path: str | Path | None = None,
    save_path: str | Path | None = None,
    show: bool = True,
    dpi: int = 150,
) -> dict[str, object]:
    """Read grid files and plot the x-y grid."""
    case_dir = Path(x_path).parent
    if Path(y_path).parent != case_dir or (z_path is not None and Path(z_path).parent != case_dir):
        from .io import MeshAxis, MeshConfig, read_grid_axis

        mesh = MeshConfig(
            x=read_grid_axis(x_path, "x"),
            y=read_grid_axis(y_path, "y"),
            z=read_grid_axis(z_path, "z") if z_path is not None else None,
        )
    else:
        mesh = read_mesh(case_dir, require_z=z_path is not None)
    return plot_xy_grid(mesh, save_path=save_path, show=show, dpi=dpi)
