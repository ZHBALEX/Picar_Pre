from __future__ import annotations

import numpy as np

from mesh.io import MeshAxis as GridAxis
from mesh.io import MeshConfig, format_mesh_summary, read_grid_axis, read_mesh, write_grid_axis, write_mesh


def generate_uniform_grids(nx: int, ny: int, nz: int, xout: float, yout: float, zout: float) -> MeshConfig:
    """Generate uniform x/y/z grid axes."""
    z_axis = GridAxis("z", np.linspace(0.0, zout, nz)) if int(nz) > 0 else None
    return MeshConfig(
        x=GridAxis("x", np.linspace(0.0, xout, nx)),
        y=GridAxis("y", np.linspace(0.0, yout, ny)),
        z=z_axis,
    )


def mesh_summary(mesh: MeshConfig) -> str:
    """Return a compact mesh summary."""
    return "\n".join(["Mesh", "====", format_mesh_summary(mesh)])
