from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from geometry.unstructure_surface.project import SurfaceProject
from geometry.unstructure_surface.surface import read_surface, validate_surface

from .canonical_body_editor import canonical_from_surface, canonical_summary, read_canonical_body, write_canonical_body
from .input_editor import InputDatEditor
from .mesh_editor import generate_uniform_grids, mesh_summary, read_mesh, write_mesh


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_CASE = REPO_ROOT / "example" / "run_case"


@dataclass
class CaseProject:
    """Case-directory editor inspired by pyvicar-style case objects."""

    case_dir: Path

    def __init__(self, case_dir: str | Path):
        self.case_dir = Path(case_dir).resolve()

    @property
    def input_path(self) -> Path:
        return self.case_dir / "input.dat"

    @property
    def canonical_path(self) -> Path:
        return self.case_dir / "canonical_body_in.dat"

    @property
    def surface_path(self) -> Path:
        return self.case_dir / "unstruc_surface_in.dat"

    @property
    def surface_project(self) -> SurfaceProject:
        return SurfaceProject(self.case_dir)

    def ensure_dir(self) -> None:
        self.case_dir.mkdir(parents=True, exist_ok=True)

    def copy_template(self, template_dir: str | Path = DEFAULT_TEMPLATE_CASE, include_large: bool = False) -> None:
        """Copy a small editable case template into this project."""
        self.ensure_dir()
        template_dir = Path(template_dir)
        for item in template_dir.iterdir():
            if item.is_file():
                if not include_large and item.name.startswith("fort."):
                    continue
                shutil.copy2(item, self.case_dir / item.name)

    def input_editor(self) -> InputDatEditor:
        return InputDatEditor.load(self.input_path)

    def generate_mesh(self, nx: int, ny: int, nz: int, xout: float, yout: float, zout: float, update_input: bool = True) -> None:
        mesh = generate_uniform_grids(nx, ny, nz, xout, yout, zout)
        write_mesh(self.case_dir, mesh)
        if update_input and self.input_path.exists():
            editor = self.input_editor()
            editor.set_grid_counts(nx, ny, nz)
            editor.set_domain_lengths(xout=xout, yout=yout, zout=zout)
            editor.write()

    def sync_canonical_from_surface(
        self,
        nbody_solid: int | None = None,
        nbody_membrane: int = 0,
        motion_type: int = 3,
        zone_max: int = 1,
    ) -> None:
        config = canonical_from_surface(
            self.surface_path,
            nbody_solid=nbody_solid,
            nbody_membrane=nbody_membrane,
            motion_type=motion_type,
            zone_max=zone_max,
        )
        write_canonical_body(self.canonical_path, config)

    def validate(self) -> list[str]:
        errors = []
        ndim = self._input_ndim()
        if self.surface_path.exists():
            errors.extend(validate_surface(read_surface(self.surface_path)))
        else:
            errors.append(f"Missing surface file: {self.surface_path}")

        required_files = ["input.dat", "xgrid.dat", "ygrid.dat"]
        if ndim != 2:
            required_files.append("zgrid.dat")
        for name in required_files:
            if not (self.case_dir / name).exists():
                errors.append(f"Missing file: {self.case_dir / name}")

        if self.canonical_path.exists() and self.surface_path.exists():
            canonical = read_canonical_body(self.canonical_path)
            bodies = read_surface(self.surface_path)
            if canonical.nbody != len(bodies):
                errors.append(f"canonical nbody {canonical.nbody} != surface bodies {len(bodies)}")
            for idx, (record, body) in enumerate(zip(canonical.bodies, bodies), start=1):
                if (record.nodes, record.elems) != (body.node_count, body.elem_count):
                    errors.append(
                        f"body {idx} canonical counts {(record.nodes, record.elems)} != surface counts {(body.node_count, body.elem_count)}"
                    )

        return errors

    def report(self) -> str:
        lines = [
            "Case Project",
            "============",
            f"case_dir : {self.case_dir}",
        ]
        if self.input_path.exists():
            lines.extend(["", self.input_editor().summary()])
        if all((self.case_dir / name).exists() for name in ["xgrid.dat", "ygrid.dat"]):
            lines.extend(["", mesh_summary(read_mesh(self.case_dir, require_z=self._input_ndim() != 2))])
        if self.surface_path.exists():
            lines.extend(["", self.surface_project.report()])
        if self.canonical_path.exists():
            lines.extend(["", canonical_summary(read_canonical_body(self.canonical_path))])
        errors = self.validate()
        lines.extend(["", "Case Validation", "===============", "Status: " + ("PASS" if not errors else "FAIL")])
        lines.extend(f"- {error}" for error in errors)
        return "\n".join(lines)

    def _input_ndim(self) -> int | None:
        if not self.input_path.exists():
            return None
        return self.input_editor().ndim()
