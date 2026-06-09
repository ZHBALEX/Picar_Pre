from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral, Real
from pathlib import Path
from typing import Iterable

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_DIR = REPO_ROOT / "example" / "run_case"

MESH_INPUT_FIELDS: tuple[tuple[str, type, str], ...] = (
    ("scale_ref", float, "primary length scale"),
    ("Lx", float, "domain length in x"),
    ("Ly", float, "domain length in y"),
    ("Lz", float, "domain length in z"),
    ("x_center_dense", float, "dense-region center in x"),
    ("y_center_dense", float, "dense-region center in y"),
    ("z_center_dense", float, "dense-region center in z"),
    ("Lx_dense", float, "dense-region length in x"),
    ("Ly_dense", float, "dense-region length in y"),
    ("Lz_dense", float, "dense-region length in z"),
    ("Nx_dense", int, "dense-region interval count in x"),
    ("Ny_dense", int, "dense-region interval count in y"),
    ("Nz_dense", int, "dense-region interval count in z"),
    ("len_left", float, "left uniform layer length near dense region"),
    ("len_right", float, "right uniform layer length near dense region"),
    ("len_bottom", float, "bottom uniform layer length near dense region"),
    ("len_top", float, "top uniform layer length near dense region"),
    ("len_front", float, "front uniform layer length near dense region"),
    ("len_back", float, "back uniform layer length near dense region"),
    ("n_left_stretch", int, "left stretched interval count"),
    ("n_left_uniform", int, "left uniform interval count"),
    ("n_right_uniform", int, "right uniform interval count"),
    ("n_right_stretch", int, "right stretched interval count"),
    ("n_bottom_stretch", int, "bottom stretched interval count"),
    ("n_bottom_uniform", int, "bottom uniform interval count"),
    ("n_top_uniform", int, "top uniform interval count"),
    ("n_top_stretch", int, "top stretched interval count"),
    ("n_front_stretch", int, "front stretched interval count"),
    ("n_front_uniform", int, "front uniform interval count"),
    ("n_back_uniform", int, "back uniform interval count"),
    ("n_back_stretch", int, "back stretched interval count"),
    ("r_left", float, "left stretching ratio"),
    ("r_right", float, "right stretching ratio"),
    ("r_bottom", float, "bottom stretching ratio"),
    ("r_top", float, "top stretching ratio"),
    ("r_front", float, "front stretching ratio"),
    ("r_back", float, "back stretching ratio"),
    ("relax", float, "relaxation factor"),
    ("flag_plot", bool, "generate plot"),
    ("flag_preplot", bool, "preplot"),
)


@dataclass
class MeshAxis:
    """One structured grid coordinate axis."""

    name: str
    values: np.ndarray

    @property
    def count(self) -> int:
        return int(self.values.size)

    @property
    def minimum(self) -> float:
        return float(np.min(self.values))

    @property
    def maximum(self) -> float:
        return float(np.max(self.values))

    @property
    def spacing(self) -> np.ndarray:
        return np.diff(self.values)


@dataclass
class MeshConfig:
    """Structured Cartesian mesh axes."""

    x: MeshAxis
    y: MeshAxis
    z: MeshAxis | None = None

    @property
    def counts(self) -> tuple[int, int, int]:
        return self.x.count, self.y.count, self.z.count if self.z is not None else 0


def parse_scalar(value: str) -> object:
    """Parse an input.dat scalar with Fortran-style booleans."""
    value = value.strip()
    lowered = value.lower()
    if lowered in {"t", "true", ".true."}:
        return True
    if lowered in {"f", "false", ".false."}:
        return False
    try:
        if any(ch in value for ch in ".eEdD"):
            return float(value.replace("D", "E").replace("d", "e"))
        return int(value)
    except ValueError:
        return value


def read_mesh_input(path: str | Path) -> dict[str, object]:
    """Read the compact mesh-parameter input.dat used by the mesh generator."""
    path = Path(path)
    values: list[object] = []
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.split("!", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 1:
            raise ValueError(f"Expected one value before comment at {path}:{len(values) + 1}, got: {line}")
        values.append(parse_scalar(parts[0]))

    expected = len(MESH_INPUT_FIELDS)
    if len(values) < expected:
        raise ValueError(f"Mesh input has {len(values)} values, expected {expected}: {path}")

    params: dict[str, object] = {}
    for idx, (key, kind, _) in enumerate(MESH_INPUT_FIELDS):
        value = values[idx]
        if kind is bool:
            params[key] = bool(value)
        elif kind is int:
            params[key] = int(value)
        elif kind is float:
            params[key] = float(value)
        else:
            params[key] = value

    return params


def write_mesh_input(path: str | Path, params: dict[str, object]) -> Path:
    """Write mesh-parameter input.dat in the generator's canonical order."""
    missing = [key for key, _, _ in MESH_INPUT_FIELDS if key not in params]
    if missing:
        raise KeyError(f"Missing mesh parameters: {', '.join(missing)}")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(format_mesh_input(params) + "\n", encoding="utf-8")
    return path


def format_mesh_input(params: dict[str, object]) -> str:
    """Return the text form of a mesh-parameter input file."""
    lines = ["! Mesh generator parameters"]
    for key, _, comment in MESH_INPUT_FIELDS:
        lines.append(f"{_format_value(params[key]):<16} ! {comment}")
        if key in {"Lz", "z_center_dense", "Lz_dense", "Nz_dense", "len_back", "n_back_stretch", "r_back"}:
            lines.append("! " + "-" * 76)
    return "\n".join(lines)


def read_grid_axis(path: str | Path, name: str | None = None) -> MeshAxis:
    """Read a one-column or index/value grid coordinate file."""
    path = Path(path)
    arr = np.loadtxt(path, ndmin=1)
    if arr.ndim == 2:
        if arr.shape[1] < 1:
            raise ValueError(f"Empty grid file: {path}")
        values = arr[:, 1] if arr.shape[1] >= 2 else arr[:, 0]
    else:
        values = arr
    values = np.asarray(values, dtype=float).reshape(-1)
    if values.size < 1:
        raise ValueError(f"Empty grid file: {path}")
    return MeshAxis(name=name or path.stem[:1], values=values)


def write_grid_axis(path: str | Path, axis: MeshAxis, include_index: bool = True) -> Path:
    """Write a grid coordinate axis."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for idx, value in enumerate(axis.values, start=1):
        if include_index:
            lines.append(f"{idx:12d}   {value:.14f}")
        else:
            lines.append(f"{value:.16g}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def read_mesh(case_dir: str | Path, require_z: bool = True) -> MeshConfig:
    """Read xgrid.dat, ygrid.dat, and optionally zgrid.dat from a case directory."""
    case_dir = Path(case_dir)
    z_path = case_dir / "zgrid.dat"
    z_axis = read_grid_axis(z_path, "z") if z_path.exists() else None
    if require_z and z_axis is None:
        raise FileNotFoundError(f"Missing grid file: {z_path}")
    return MeshConfig(
        x=read_grid_axis(case_dir / "xgrid.dat", "x"),
        y=read_grid_axis(case_dir / "ygrid.dat", "y"),
        z=z_axis,
    )


def write_mesh(case_dir: str | Path, mesh: MeshConfig, include_index: bool = True) -> None:
    """Write xgrid.dat, ygrid.dat, and zgrid.dat into a case directory."""
    case_dir = Path(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    write_grid_axis(case_dir / "xgrid.dat", mesh.x, include_index=include_index)
    write_grid_axis(case_dir / "ygrid.dat", mesh.y, include_index=include_index)
    if mesh.z is not None:
        write_grid_axis(case_dir / "zgrid.dat", mesh.z, include_index=include_index)


def validate_mesh(mesh: MeshConfig) -> list[str]:
    """Return mesh-axis validation errors."""
    errors: list[str] = []
    for axis in (mesh.x, mesh.y, mesh.z):
        if axis is None:
            continue
        values = np.asarray(axis.values, dtype=float)
        if values.ndim != 1:
            errors.append(f"{axis.name}: values must be one-dimensional")
            continue
        if values.size < 2:
            errors.append(f"{axis.name}: at least two points are required")
            continue
        if not np.all(np.isfinite(values)):
            errors.append(f"{axis.name}: contains non-finite values")
        if np.any(np.diff(values) <= 0):
            errors.append(f"{axis.name}: values must be strictly increasing")
    return errors


def summarize_mesh(mesh: MeshConfig) -> list[dict[str, object]]:
    """Return counts, ranges, and spacing statistics for each axis."""
    rows = []
    for axis in (mesh.x, mesh.y, mesh.z):
        if axis is None:
            continue
        spacing = axis.spacing
        rows.append(
            {
                "axis": axis.name,
                "count": axis.count,
                "minimum": axis.minimum,
                "maximum": axis.maximum,
                "dmin": float(np.min(spacing)) if spacing.size else 0.0,
                "dmax": float(np.max(spacing)) if spacing.size else 0.0,
                "dmean": float(np.mean(spacing)) if spacing.size else 0.0,
            }
        )
    return rows


def format_mesh_summary(mesh: MeshConfig) -> str:
    """Format mesh-axis counts and spacing statistics."""
    rows = summarize_mesh(mesh)
    if not rows:
        return "No mesh axes found."

    header = f"{'Axis':>4}  {'Count':>8}  {'Min':>12}  {'Max':>12}  {'dmin':>12}  {'dmax':>12}  {'dmean':>12}"
    line = "-" * len(header)
    body = [header, line]
    for row in rows:
        body.append(
            f"{row['axis']:>4}  {row['count']:>8}  {row['minimum']:>12.6f}  {row['maximum']:>12.6f}  "
            f"{row['dmin']:>12.6g}  {row['dmax']:>12.6g}  {row['dmean']:>12.6g}"
        )
    return "\n".join(body)


def format_validation_report(errors: Iterable[str]) -> str:
    """Format validation results for terminal output."""
    errors = list(errors)
    if not errors:
        return "Status: PASS\nMesh validation passed."
    return "\n".join(["Status: FAIL", "Validation errors:", *[f"- {error}" for error in errors]])


def _format_value(value: object) -> str:
    if isinstance(value, bool):
        return "T" if value else "F"
    if isinstance(value, Integral) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, Real):
        return f"{value:.16g}"
    return str(value).strip()
