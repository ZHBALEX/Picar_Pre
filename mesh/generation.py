from __future__ import annotations

from pathlib import Path
import shutil
import warnings

import numpy as np

from .io import MeshAxis, MeshConfig, read_mesh_input, write_mesh


def geometric_sizes(total_length: float, count: int, ratio: float = 1.0) -> np.ndarray:
    """Split a length into positive geometric interval sizes."""
    count = int(count)
    total_length = float(total_length)
    ratio = float(ratio)
    if count <= 0 or total_length <= 0.0:
        return np.asarray([], dtype=float)
    if ratio <= 0.0:
        raise ValueError("Stretching ratio must be positive")
    if abs(ratio - 1.0) < 1e-14:
        return np.full(count, total_length / count, dtype=float)
    first = total_length * (1.0 - ratio) / (1.0 - ratio**count)
    return first * ratio ** np.arange(count, dtype=float)


def make_axis_nodes(
    length: float,
    center_dense: float,
    dense_length: float,
    dense_count: int,
    left_length_hint: float = 0.0,
    right_length_hint: float = 0.0,
    left_stretch_count: int = 0,
    left_uniform_count: int = 0,
    right_uniform_count: int = 0,
    right_stretch_count: int = 0,
    left_ratio: float = 1.0,
    right_ratio: float = 1.0,
    repair_degenerate: bool = False,
) -> np.ndarray:
    """Generate one monotone coordinate axis from dense-region parameters.

    Counts are interval counts. The returned array therefore has total interval
    count + 1 nodes.
    """
    length = float(length)
    if length <= 0.0:
        raise ValueError("Axis length must be positive")

    x0 = float(center_dense) - 0.5 * float(dense_length)
    x1 = float(center_dense) + 0.5 * float(dense_length)
    if x0 < -1e-12 or x1 > length + 1e-12:
        raise ValueError(f"Dense region [{x0:.6g}, {x1:.6g}] is outside [0, {length:.6g}]")
    x0 = max(0.0, min(length, x0))
    x1 = max(0.0, min(length, x1))

    left_total = x0
    right_total = length - x1

    left_uniform_count = max(0, int(left_uniform_count))
    left_stretch_count = max(0, int(left_stretch_count))
    dense_count = max(0, int(dense_count))
    right_stretch_count = max(0, int(right_stretch_count))
    right_uniform_count = max(0, int(right_uniform_count))

    left_uniform_length, left_stretch_length = _split_layer_lengths(
        left_total,
        left_length_hint,
        left_uniform_count,
        left_stretch_count,
        "left",
    )
    right_uniform_length, right_stretch_length = _split_layer_lengths(
        right_total,
        right_length_hint,
        right_uniform_count,
        right_stretch_count,
        "right",
    )

    left_ratio = _effective_ratio(left_ratio)
    right_ratio = _effective_ratio(right_ratio)

    sizes = np.concatenate(
        [
            geometric_sizes(left_stretch_length, left_stretch_count, left_ratio)[::-1],
            geometric_sizes(left_uniform_length, left_uniform_count, 1.0),
            geometric_sizes(x1 - x0, dense_count, 1.0),
            geometric_sizes(right_uniform_length, right_uniform_count, 1.0),
            geometric_sizes(right_stretch_length, right_stretch_count, right_ratio),
        ]
    )

    if sizes.size == 0:
        return np.asarray([0.0, length], dtype=float)

    nodes = np.concatenate([[0.0], np.cumsum(sizes)])
    nodes[-1] = length
    if np.any(np.diff(nodes) <= 0):
        if repair_degenerate:
            warnings.warn(
                "Some requested intervals were too small for floating-point coordinates; "
                "the preview repaired duplicate nodes with nextafter(). "
                "Consider reducing the stretching aggressiveness or interval count before generating production grids.",
                RuntimeWarning,
                stacklevel=2,
            )
            nodes = _repair_strictly_increasing(nodes, length)
        else:
            min_positive = float(np.min(sizes[sizes > 0])) if np.any(sizes > 0) else 0.0
            raise ValueError(
                "Generated axis is not strictly increasing. "
                f"The smallest requested interval is {min_positive:.3e}; "
                "this usually means a stretching ratio is too aggressive for the interval count."
            )
    return nodes


def generate_mesh(params: dict[str, object], repair_degenerate: bool = False) -> MeshConfig:
    """Generate x/y/z axes from a mesh-parameter dictionary."""
    x_axis = MeshAxis(
            "x",
            make_axis_nodes(
                params["Lx"],
                params["x_center_dense"],
                params["Lx_dense"],
                params["Nx_dense"],
                params["len_left"],
                params["len_right"],
                params["n_left_stretch"],
                params["n_left_uniform"],
                params["n_right_uniform"],
                params["n_right_stretch"],
                params["r_left"],
                params["r_right"],
                repair_degenerate=repair_degenerate,
            ),
        )
    y_axis = MeshAxis(
            "y",
            make_axis_nodes(
                params["Ly"],
                params["y_center_dense"],
                params["Ly_dense"],
                params["Ny_dense"],
                params["len_bottom"],
                params["len_top"],
                params["n_bottom_stretch"],
                params["n_bottom_uniform"],
                params["n_top_uniform"],
                params["n_top_stretch"],
                params["r_bottom"],
                params["r_top"],
                repair_degenerate=repair_degenerate,
            ),
        )
    z_axis = None
    if _has_z_params(params):
        z_axis = MeshAxis(
            "z",
            make_axis_nodes(
                params["Lz"],
                params["z_center_dense"],
                params["Lz_dense"],
                params["Nz_dense"],
                params["len_front"],
                params["len_back"],
                params["n_front_stretch"],
                params["n_front_uniform"],
                params["n_back_uniform"],
                params["n_back_stretch"],
                params["r_front"],
                params["r_back"],
                repair_degenerate=repair_degenerate,
            ),
        )
    return MeshConfig(x=x_axis, y=y_axis, z=z_axis)


def generate_mesh_from_input(path: str | Path, input_format: str = "auto", repair_degenerate: bool = False) -> MeshConfig:
    """Read mesh parameters and generate x/y/z axes."""
    return generate_mesh(read_mesh_input(path, input_format=input_format), repair_degenerate=repair_degenerate)


def generate_xyzgrid_files(
    dat_path: str | Path,
    xgrid_path: str | Path,
    ygrid_path: str | Path,
    zgrid_path: str | Path,
    include_index: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate xgrid.dat/ygrid.dat/zgrid.dat files from mesh parameters."""
    mesh = generate_mesh_from_input(dat_path)
    write_mesh(Path(xgrid_path).parent, mesh, include_index=include_index)
    target_paths = [Path(xgrid_path), Path(ygrid_path), Path(zgrid_path)]
    default_paths = [Path(xgrid_path).parent / name for name in ("xgrid.dat", "ygrid.dat", "zgrid.dat")]
    for default, target in zip(default_paths, target_paths):
        if default != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(default), str(target))
    return mesh.x.values, mesh.y.values, mesh.z.values if mesh.z is not None else np.asarray([])


def _split_layer_lengths(
    total_length: float,
    uniform_length_hint: float,
    uniform_count: int,
    stretch_count: int,
    side_name: str,
) -> tuple[float, float]:
    """Return uniform-near-dense length and far-field stretch length."""
    total_length = float(total_length)
    uniform_length_hint = float(uniform_length_hint)
    if total_length <= 0.0:
        return 0.0, 0.0
    if uniform_count <= 0:
        return 0.0, total_length
    if stretch_count <= 0:
        return total_length, 0.0
    if uniform_length_hint <= 0.0:
        total_count = uniform_count + stretch_count
        uniform_length = total_length * uniform_count / total_count
    elif uniform_length_hint >= total_length:
        raise ValueError(
            f"{side_name} layer length {uniform_length_hint:.6g} leaves no room for "
            f"{stretch_count} stretched intervals; use the uniform layer length near the dense region"
        )
    else:
        uniform_length = uniform_length_hint
    return uniform_length, total_length - uniform_length


def _effective_ratio(ratio: float) -> float:
    ratio = float(ratio)
    if ratio <= 0.0:
        raise ValueError("Stretching ratio must be positive")
    return ratio if ratio >= 1.0 else 1.0 / ratio


def _has_z_params(params: dict[str, object]) -> bool:
    z_keys = [
        "Lz",
        "z_center_dense",
        "Lz_dense",
        "Nz_dense",
        "len_front",
        "len_back",
        "n_front_stretch",
        "n_front_uniform",
        "n_back_uniform",
        "n_back_stretch",
        "r_front",
        "r_back",
    ]
    if not all(key in params for key in z_keys):
        return False
    return float(params["Lz"]) > 0.0


def _repair_strictly_increasing(nodes: np.ndarray, length: float) -> np.ndarray:
    repaired = np.asarray(nodes, dtype=float).copy()
    for idx in range(1, repaired.size - 1):
        if repaired[idx] <= repaired[idx - 1]:
            repaired[idx] = np.nextafter(repaired[idx - 1], np.inf)
    repaired[-1] = float(length)
    if repaired.size >= 2 and repaired[-1] <= repaired[-2]:
        raise ValueError(
            "Generated axis is too degenerate to preview safely; reduce stretching ratio or interval count."
        )
    return repaired
