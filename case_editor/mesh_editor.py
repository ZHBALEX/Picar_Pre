from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class GridAxis:
    """One structured grid coordinate axis."""

    name: str
    values: np.ndarray

    @property
    def count(self) -> int:
        return int(len(self.values))

    @property
    def minimum(self) -> float:
        return float(np.min(self.values))

    @property
    def maximum(self) -> float:
        return float(np.max(self.values))


@dataclass
class MeshConfig:
    """Structured Cartesian mesh axes."""

    x: GridAxis
    y: GridAxis
    z: GridAxis

    @property
    def counts(self) -> tuple[int, int, int]:
        return self.x.count, self.y.count, self.z.count


def read_grid_axis(path: str | Path, name: str | None = None) -> GridAxis:
    """Read index/value grid file such as xgrid.dat."""
    path = Path(path)
    values = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            values.append(float(parts[1]))
    return GridAxis(name=name or path.stem[0], values=np.asarray(values, dtype=float))


def write_grid_axis(path: str | Path, axis: GridAxis) -> Path:
    """Write an index/value grid file."""
    out = Path(path)
    lines = [f"{idx:12d}   {value:.14f}     " for idx, value in enumerate(axis.values, start=1)]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def read_mesh(case_dir: str | Path) -> MeshConfig:
    """Read xgrid.dat, ygrid.dat, and zgrid.dat from a case directory."""
    case_dir = Path(case_dir)
    return MeshConfig(
        x=read_grid_axis(case_dir / "xgrid.dat", "x"),
        y=read_grid_axis(case_dir / "ygrid.dat", "y"),
        z=read_grid_axis(case_dir / "zgrid.dat", "z"),
    )


def write_mesh(case_dir: str | Path, mesh: MeshConfig) -> None:
    """Write xgrid.dat, ygrid.dat, and zgrid.dat into a case directory."""
    case_dir = Path(case_dir)
    case_dir.mkdir(parents=True, exist_ok=True)
    write_grid_axis(case_dir / "xgrid.dat", mesh.x)
    write_grid_axis(case_dir / "ygrid.dat", mesh.y)
    write_grid_axis(case_dir / "zgrid.dat", mesh.z)


def generate_uniform_grids(nx: int, ny: int, nz: int, xout: float, yout: float, zout: float) -> MeshConfig:
    """Generate uniform x/y/z grid axes."""
    return MeshConfig(
        x=GridAxis("x", np.linspace(0.0, xout, nx)),
        y=GridAxis("y", np.linspace(0.0, yout, ny)),
        z=GridAxis("z", np.linspace(0.0, zout, nz)),
    )


def mesh_summary(mesh: MeshConfig) -> str:
    """Return a compact mesh summary."""
    lines = [
        "Mesh",
        "====",
        "Axis  Count       Min       Max",
        "-------------------------------",
    ]
    for axis in [mesh.x, mesh.y, mesh.z]:
        lines.append(f"{axis.name:>4}  {axis.count:>5}  {axis.minimum:>8.4f}  {axis.maximum:>8.4f}")
    return "\n".join(lines)
