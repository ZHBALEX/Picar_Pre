from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class InputDatEditor:
    """Small formatting-preserving editor for input.dat."""

    path: Path
    lines: list[str]

    @classmethod
    def load(cls, path: str | Path) -> "InputDatEditor":
        path = Path(path)
        return cls(path=path, lines=path.read_text(encoding="utf-8", errors="ignore").splitlines())

    def write(self, path: str | Path | None = None) -> Path:
        out = Path(path) if path is not None else self.path
        out.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        return out

    def get_values_after(self, marker: str) -> list[str]:
        idx = self._find_marker(marker)
        return self.lines[idx + 1].split()

    def set_values_after(self, marker: str, values) -> None:
        idx = self._find_marker(marker)
        self.lines[idx + 1] = _format_values(values)

    def set_grid_counts(self, nx: int, ny: int, nz: int) -> None:
        self.set_values_after("nx", [nx, ny, nz])

    def set_domain_lengths(self, xout: float | None = None, yout: float | None = None, zout: float | None = None) -> None:
        if xout is not None:
            vals = self.get_values_after("xgrid_unif")
            vals[1] = xout
            self.set_values_after("xgrid_unif", vals)
        if yout is not None:
            vals = self.get_values_after("ygrid_unif")
            vals[1] = yout
            self.set_values_after("ygrid_unif", vals)
        if zout is not None:
            vals = self.get_values_after("zgrid_unif")
            vals[1] = zout
            self.set_values_after("zgrid_unif", vals)

    def set_initial_velocity(self, u: float, v: float, w: float, perturbation: float | None = None) -> None:
        vals = self.get_values_after("uinit")
        vals[0:3] = [u, v, w]
        if perturbation is not None and len(vals) >= 4:
            vals[3] = perturbation
        self.set_values_after("uinit", vals)

    def set_re_dt(self, re: float, dt: float) -> None:
        self.set_values_after("re,", [re, dt])

    def set_time_control(
        self,
        no_tsteps: int | None = None,
        nmonitor: int | None = None,
        ndump: int | None = None,
        nrestart: int | None = None,
        nstat: int | None = None,
        nprobe: int | None = None,
        stats_sum: int | None = None,
        ndump_start: int | None = None,
        nperiod: int | None = None,
    ) -> None:
        vals = self.get_values_after("no_tsteps")
        updates = [no_tsteps, nmonitor, ndump, nrestart, nstat, nprobe, stats_sum, ndump_start, nperiod]
        for idx, value in enumerate(updates):
            if value is not None and idx < len(vals):
                vals[idx] = value
        self.set_values_after("no_tsteps", vals)

    def set_internal_boundary(self, present: int = 1, iblank_fast: int = 0, body_type: int = 2, formulation: int = 1) -> None:
        self.set_values_after("internal_boundary_present", [present, iblank_fast])
        self.set_values_after("body_type", [body_type])
        self.set_values_after("boundary_formulation", [formulation])

    def summary(self) -> str:
        parts = [
            "Input.dat",
            "=========",
            f"path        : {self.path}",
            f"grid counts : {' '.join(self.get_values_after('nx')[:3])}",
            f"x control   : {' '.join(self.get_values_after('xgrid_unif')[:2])}",
            f"y control   : {' '.join(self.get_values_after('ygrid_unif')[:2])}",
            f"z control   : {' '.join(self.get_values_after('zgrid_unif')[:2])}",
            f"velocity    : {' '.join(self.get_values_after('uinit')[:4])}",
            f"re/dt       : {' '.join(self.get_values_after('re,')[:2])}",
            f"IB present  : {' '.join(self.get_values_after('internal_boundary_present')[:2])}",
            f"body type   : {' '.join(self.get_values_after('body_type')[:1])}",
        ]
        return "\n".join(parts)

    def _find_marker(self, marker: str) -> int:
        marker = marker.lower()
        for idx, line in enumerate(self.lines[:-1]):
            if marker in line.lower():
                return idx
        raise ValueError(f"Cannot find marker in input.dat: {marker}")


def _format_values(values) -> str:
    return "        ".join(_format_value(value) for value in values)


def _format_value(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.16g}"
    return str(value)
