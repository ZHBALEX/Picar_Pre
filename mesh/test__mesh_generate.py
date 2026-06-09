from __future__ import annotations

from pathlib import Path

import numpy as np

from mesh.generation import generate_mesh
from mesh.io import read_mesh, validate_mesh, write_mesh
from mesh.optimization import optimize_mesh_params, preferred_count_near


def sample_mesh_params() -> dict[str, object]:
    return {
        "scale_ref": 1.0,
        "Lx": 10.0,
        "Ly": 6.0,
        "Lz": 4.0,
        "x_center_dense": 5.0,
        "y_center_dense": 3.0,
        "z_center_dense": 2.0,
        "Lx_dense": 2.0,
        "Ly_dense": 2.0,
        "Lz_dense": 1.0,
        "Nx_dense": 8,
        "Ny_dense": 6,
        "Nz_dense": 4,
        "len_left": 0.5,
        "len_right": 0.5,
        "len_bottom": 0.5,
        "len_top": 0.5,
        "len_front": 0.25,
        "len_back": 0.25,
        "n_left_stretch": 4,
        "n_left_uniform": 2,
        "n_right_uniform": 2,
        "n_right_stretch": 4,
        "n_bottom_stretch": 3,
        "n_bottom_uniform": 1,
        "n_top_uniform": 1,
        "n_top_stretch": 3,
        "n_front_stretch": 2,
        "n_front_uniform": 1,
        "n_back_uniform": 1,
        "n_back_stretch": 2,
        "r_left": 1.2,
        "r_right": 1.2,
        "r_bottom": 1.1,
        "r_top": 1.1,
        "r_front": 1.05,
        "r_back": 1.05,
        "relax": 0.001,
        "flag_plot": False,
        "flag_preplot": False,
    }


def test_generate_mesh_is_monotone() -> None:
    mesh = generate_mesh(sample_mesh_params())
    assert validate_mesh(mesh) == []
    assert mesh.counts == (21, 15, 11)
    assert np.isclose(mesh.x.values[0], 0.0)
    assert np.isclose(mesh.x.values[-1], 10.0)


def test_write_and_read_mesh(tmp_path: Path) -> None:
    mesh = generate_mesh(sample_mesh_params())
    write_mesh(tmp_path, mesh)
    reread = read_mesh(tmp_path)
    assert np.allclose(mesh.x.values, reread.x.values)
    assert np.allclose(mesh.y.values, reread.y.values)
    assert np.allclose(mesh.z.values, reread.z.values)


def test_optimizer_supports_dense_and_balanced_priorities() -> None:
    params = sample_mesh_params()
    params.update(
        {
            "Lx": 24.0,
            "x_center_dense": 12.0,
            "Lx_dense": 8.0,
            "Nx_dense": 64,
            "len_left": 1.0,
            "len_right": 1.0,
            "n_left_stretch": 16,
            "n_left_uniform": 8,
            "n_right_uniform": 8,
            "n_right_stretch": 16,
        }
    )
    dense_params, _ = optimize_mesh_params(params, priority="dense")
    balanced_params, _ = optimize_mesh_params(params, priority="balanced")

    assert dense_params["Nx_dense"] == params["Nx_dense"]
    assert balanced_params["Nx_dense"] != params["Nx_dense"]
    assert np.isclose(
        balanced_params["Lx_dense"] / balanced_params["Nx_dense"],
        params["Lx_dense"] / params["Nx_dense"],
    )


def test_preferred_count_table_matches_calculator_style() -> None:
    assert preferred_count_near(787.8787878787883) == 768
    assert preferred_count_near(1696.9696969696975) == 1664
