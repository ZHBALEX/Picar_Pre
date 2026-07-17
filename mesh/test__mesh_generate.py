from __future__ import annotations

from pathlib import Path

import numpy as np

from case_editor.run_picar_console import _axis_params_from_grid
from mesh.generation import generate_mesh
from mesh.generation import make_axis_nodes
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


def test_axis_generation_matches_reference_two_layer_xgrid() -> None:
    values = make_axis_nodes(
        length=12.5,
        center_dense=10.9,
        dense_length=2.2656,
        dense_count=192,
        left_length_hint=0.0,
        right_length_hint=0.0,
        left_stretch_count=33,
        left_uniform_count=0,
        right_uniform_count=0,
        right_stretch_count=31,
        left_ratio=1.08,
        right_ratio=1.08,
    )

    assert values.size == 257
    assert np.allclose(
        values[[0, 1, 33, 34, 100, 225, 240, 255, 256]],
        [
            0.0,
            2.46658340422205,
            9.7672,
            9.779,
            10.5578,
            12.0328,
            12.2206489125264,
            12.4777838003295,
            12.5,
        ],
        rtol=0.0,
        atol=1e-12,
    )
    assert np.allclose(np.diff(values)[33:225], 0.0118, rtol=0.0, atol=1e-12)


def test_console_infers_reference_two_layer_dense_region() -> None:
    values = make_axis_nodes(
        length=12.5,
        center_dense=10.9,
        dense_length=2.2656,
        dense_count=192,
        left_length_hint=0.0,
        right_length_hint=0.0,
        left_stretch_count=33,
        left_uniform_count=0,
        right_uniform_count=0,
        right_stretch_count=31,
        left_ratio=1.08,
        right_ratio=1.08,
    )

    axis = _axis_params_from_grid(values)

    assert np.isclose(axis["center"], 10.9)
    assert np.isclose(axis["dense_length"], 2.2656)
    assert axis["dense_count"] == 192
    assert axis["left_stretch"] == 33
    assert axis["right_stretch"] == 31


def test_write_and_read_mesh(tmp_path: Path) -> None:
    mesh = generate_mesh(sample_mesh_params())
    write_mesh(tmp_path, mesh)
    reread = read_mesh(tmp_path)
    assert np.allclose(mesh.x.values, reread.x.values)
    assert np.allclose(mesh.y.values, reread.y.values)
    assert np.allclose(mesh.z.values, reread.z.values)


def test_generate_z_axis_when_lz_positive_without_dense_z() -> None:
    params = sample_mesh_params()
    params.update(
        {
            "Lz": 4.0,
            "z_center_dense": 2.0,
            "Lz_dense": 0.0,
            "Nz_dense": 0,
            "len_front": 0.0,
            "len_back": 0.0,
            "n_front_stretch": 0,
            "n_front_uniform": 0,
            "n_back_uniform": 0,
            "n_back_stretch": 0,
        }
    )
    mesh = generate_mesh(params)
    assert mesh.z is not None
    assert np.allclose(mesh.z.values, [0.0, 4.0])


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
