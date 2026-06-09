from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .generation import generate_mesh
from .io import (
    DEFAULT_CASE_DIR,
    MeshConfig,
    format_mesh_summary,
    format_validation_report,
    read_mesh,
    read_mesh_input,
    validate_mesh,
    write_mesh,
    write_mesh_input,
)
from .optimization import format_count_quality_report, format_optimization_report, optimize_mesh_params


@dataclass
class MeshProject:
    """Target-directory context for structured mesh preprocessing."""

    case_dir: Path
    input_name: str = "input.dat"

    def __init__(self, case_dir: str | Path | None = None, input_name: str = "input.dat"):
        self.case_dir = Path(case_dir or DEFAULT_CASE_DIR).resolve()
        self.input_name = input_name

    @property
    def input_path(self) -> Path:
        return self.case_dir / self.input_name

    def ensure_dir(self) -> None:
        self.case_dir.mkdir(parents=True, exist_ok=True)

    def load_input(self, required: bool = True) -> dict[str, object]:
        if not self.input_path.exists():
            if required:
                raise FileNotFoundError(f"Mesh input not found: {self.input_path}")
            return {}
        return read_mesh_input(self.input_path)

    def save_input(self, params: dict[str, object], output: str | Path | None = None) -> Path:
        self.ensure_dir()
        out = Path(output) if output is not None else self.input_path
        if not out.is_absolute():
            out = self.case_dir / out
        return write_mesh_input(out, params)

    def load_mesh(self, require_z: bool = True) -> MeshConfig:
        return read_mesh(self.case_dir, require_z=require_z)

    def generate(
        self,
        output_dir: str | Path | None = None,
        include_index: bool = True,
        optimize: bool = False,
        search_window: int | None = None,
        max_relative_dense_change: float = 0.25,
        priority: str = "dense",
        method: str = "search",
        ideal_deltas: dict[str, float] | None = None,
    ) -> tuple[MeshConfig, str | None]:
        params = self.load_input(required=True)
        optimization_report = None
        if optimize:
            params, reports = optimize_mesh_params(
                params,
                search_window=search_window,
                max_relative_dense_change=max_relative_dense_change,
                priority=priority,
                method=method,
                ideal_deltas=ideal_deltas,
            )
            optimization_report = format_optimization_report(reports)
        mesh = generate_mesh(params)
        out_dir = Path(output_dir) if output_dir is not None else self.case_dir
        if not out_dir.is_absolute():
            out_dir = self.case_dir / out_dir
        write_mesh(out_dir, mesh, include_index=include_index)
        return mesh, optimization_report

    def optimize_input(
        self,
        output: str | Path | None = None,
        search_window: int | None = None,
        max_relative_dense_change: float = 0.25,
        priority: str = "dense",
        method: str = "search",
        ideal_deltas: dict[str, float] | None = None,
    ) -> tuple[Path, str]:
        params = self.load_input(required=True)
        optimized, reports = optimize_mesh_params(
            params,
            search_window=search_window,
            max_relative_dense_change=max_relative_dense_change,
            priority=priority,
            method=method,
            ideal_deltas=ideal_deltas,
        )
        output_path = self.save_input(optimized, output=output or f"{Path(self.input_name).stem}_optimized.dat")
        return output_path, format_optimization_report(reports)

    def report(self, require_z: bool = True) -> str:
        mesh = self.load_mesh(require_z=require_z)
        errors = validate_mesh(mesh)
        return "\n".join(
            [
                "Mesh Project",
                "============",
                f"Case dir   : {self.case_dir}",
                f"Input file : {self.input_path}",
                "",
                "Mesh Summary",
                "============",
                format_mesh_summary(mesh),
                "",
                format_count_quality_report(self.load_input(required=True)),
                "",
                "Validation",
                "==========",
                format_validation_report(errors),
            ]
        )
