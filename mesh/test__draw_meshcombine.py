from __future__ import annotations

from pathlib import Path

import matplotlib

from mesh.test__mesh_generate import sample_mesh_params
from mesh.generation import generate_mesh
from mesh.visualize import plot_xy_grid


matplotlib.use("Agg")


def test_plot_xy_grid_saves_image(tmp_path: Path) -> None:
    mesh = generate_mesh(sample_mesh_params())
    output = tmp_path / "grid.png"
    result = plot_xy_grid(mesh, save_path=output, show=False)
    assert output.exists()
    assert result["domain"] == (0.0, 0.0, 10.0, 6.0)
