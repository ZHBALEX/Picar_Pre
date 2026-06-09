from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .modeling import make_parametric_body
from .stl import stl_to_surface_body
from .surface import (
    DEFAULT_CASE_SURFACE,
    SurfaceBody,
    format_surface_summary_compact,
    format_validation_report,
    read_surface,
    transform_body,
    validate_surface,
    write_surface,
)


DEFAULT_SURFACE_NAME = "unstruc_surface_in.dat"


@dataclass
class SurfaceProject:
    """Target-directory context for unstructured surface preprocessing."""

    case_dir: Path
    surface_name: str = DEFAULT_SURFACE_NAME

    def __init__(self, case_dir: str | Path | None = None, surface_name: str = DEFAULT_SURFACE_NAME):
        if case_dir is None:
            case_dir = DEFAULT_CASE_SURFACE.parent
        self.case_dir = Path(case_dir).resolve()
        self.surface_name = surface_name

    @property
    def surface_path(self) -> Path:
        return self.case_dir / self.surface_name

    def ensure_dir(self) -> None:
        self.case_dir.mkdir(parents=True, exist_ok=True)

    def load(self, required: bool = True) -> list[SurfaceBody]:
        if not self.surface_path.exists():
            if required:
                raise FileNotFoundError(f"Surface file not found: {self.surface_path}")
            return []
        return read_surface(self.surface_path)

    def save(self, bodies: list[SurfaceBody], output: str | Path | None = None, write_final_sentinel: bool = True) -> Path:
        self.ensure_dir()
        out = Path(output) if output is not None else self.surface_path
        if not out.is_absolute():
            out = self.case_dir / out
        write_surface(out, bodies, write_final_sentinel=write_final_sentinel)
        return out

    def stl_files(self, recursive: bool = False) -> list[Path]:
        pattern = "**/*.stl" if recursive else "*.stl"
        return sorted(self.case_dir.glob(pattern))

    def convert_stl(
        self,
        stl_files: list[str | Path] | None = None,
        output: str | Path | None = None,
        append: bool = False,
        precision: int = 8,
    ) -> tuple[Path, list[SurfaceBody]]:
        if stl_files is None or len(stl_files) == 0:
            stl_paths = self.stl_files()
        else:
            stl_paths = [self._resolve_path(path) for path in stl_files]

        if not stl_paths:
            raise FileNotFoundError(f"No STL files found in {self.case_dir}")

        bodies = self.load(required=False) if append else []
        bodies.extend(stl_to_surface_body(path, precision=precision) for path in stl_paths)
        out = self.save(bodies, output=output)
        return out, bodies

    def generate(
        self,
        kind: str,
        output: str | Path | None = None,
        append: bool = False,
        **kwargs,
    ) -> tuple[Path, list[SurfaceBody]]:
        body = make_parametric_body(kind, **kwargs)
        bodies = self.load(required=False) if append else []
        bodies.append(body)
        out = self.save(bodies, output=output)
        return out, bodies

    def combine_surfaces(
        self,
        surface_files: list[str | Path],
        output: str | Path | None = None,
        append: bool = False,
    ) -> tuple[Path, list[SurfaceBody]]:
        """Combine one or more surface files into this project's surface file."""
        if not surface_files:
            raise ValueError("At least one surface file is required")

        bodies = self.load(required=False) if append else []
        for surface_file in surface_files:
            bodies.extend(read_surface(self._resolve_input_path(surface_file)))

        out = self.save(bodies, output=output)
        return out, bodies

    def transform(
        self,
        body_ids: list[int] | None = None,
        output: str | Path | None = None,
        rotation=None,
        translate=None,
        scale=1.0,
    ) -> tuple[Path, list[SurfaceBody]]:
        bodies = self.load(required=True)
        if body_ids is None or len(body_ids) == 0:
            target_ids = set(range(1, len(bodies) + 1))
        else:
            target_ids = set(body_ids)

        transformed = []
        for idx, body in enumerate(bodies, start=1):
            if idx in target_ids:
                transformed.append(transform_body(body, rotation=rotation, translate=translate, scale=scale))
            else:
                transformed.append(body)

        out = self.save(transformed, output=output)
        return out, transformed

    def report(self, surface_path: str | Path | None = None, bodies: list[SurfaceBody] | None = None) -> str:
        """Return a structured report for a surface file or loaded bodies."""
        if surface_path is None:
            report_path = self.surface_path
        else:
            report_path = Path(surface_path)
            if not report_path.is_absolute():
                report_path = self.case_dir / report_path

        if bodies is None:
            bodies = read_surface(report_path)

        return "\n".join(
            [
                "Project",
                "=======",
                f"Case dir     : {self.case_dir}",
                f"Surface file : {report_path}",
                "",
                "Surface Summary",
                "===============",
                format_surface_summary_compact(bodies),
                "",
                "Validation",
                "==========",
                format_validation_report(validate_surface(bodies)),
            ]
        )

    def _resolve_path(self, path: str | Path) -> Path:
        path = Path(path)
        return path if path.is_absolute() else self.case_dir / path

    def _resolve_input_path(self, path: str | Path) -> Path:
        path = Path(path)
        if path.is_absolute():
            return path
        if path.exists():
            return path
        return self.case_dir / path
