from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from geometry.unstructure_surface.project import SurfaceProject

from .case_project import DEFAULT_TEMPLATE_CASE, CaseProject


@dataclass
class SurfaceBuildConfig:
    """Parametric surface settings for one generated body."""

    kind: str = "circle"
    params: dict[str, object] = field(default_factory=lambda: {"radius": 0.25, "n": 600, "layers": 3})
    center: tuple[float, float, float] = (19.2, 10.0, 0.005)
    plane: str = "xy"
    thickness: float = 0.01
    rotation: tuple[float, float, float] | None = None
    translate: tuple[float, float, float] | None = None
    scale: float = 1.0


@dataclass
class MeshBuildConfig:
    """Uniform mesh settings."""

    nx: int = 121
    ny: int = 81
    nz: int = 1
    xout: float = 24.0
    yout: float = 20.0
    zout: float = 0.0


@dataclass
class InputBuildConfig:
    """Common input.dat settings."""

    u: float = 1.0
    v: float = 0.0
    w: float = 0.0
    re: float = 1000.0
    dt: float = 0.001
    ib_present: int = 1
    body_type: int = 2
    formulation: int = 1


@dataclass
class CanonicalBuildConfig:
    """canonical_body_in.dat settings."""

    nbody_solid: int | None = 1
    nbody_membrane: int = 0
    motion_type: int = 3
    zone_max: int = 1


@dataclass
class CaseBuildConfig:
    """Complete one-body case build settings."""

    case_dir: Path | str = Path("example/generated_circle2d_case")
    template_dir: Path | str = DEFAULT_TEMPLATE_CASE
    include_large_template_files: bool = False
    surface: SurfaceBuildConfig = field(default_factory=SurfaceBuildConfig)
    mesh: MeshBuildConfig = field(default_factory=MeshBuildConfig)
    input: InputBuildConfig = field(default_factory=InputBuildConfig)
    canonical: CanonicalBuildConfig = field(default_factory=CanonicalBuildConfig)


def build_case(config: CaseBuildConfig) -> CaseProject:
    """Build a complete editable Picar case from one config object."""
    case = CaseProject(config.case_dir)
    case.copy_template(config.template_dir, include_large=config.include_large_template_files)

    surface_project = SurfaceProject(case.case_dir)
    surface_kwargs = {
        **config.surface.params,
        "center": config.surface.center,
        "plane": config.surface.plane,
        "thickness": config.surface.thickness,
        "rotation": config.surface.rotation,
        "translate": config.surface.translate,
        "scale": config.surface.scale,
    }
    surface_project.generate(config.surface.kind, **surface_kwargs)

    case.sync_canonical_from_surface(
        nbody_solid=config.canonical.nbody_solid,
        nbody_membrane=config.canonical.nbody_membrane,
        motion_type=config.canonical.motion_type,
        zone_max=config.canonical.zone_max,
    )
    case.generate_mesh(
        nx=config.mesh.nx,
        ny=config.mesh.ny,
        nz=config.mesh.nz,
        xout=config.mesh.xout,
        yout=config.mesh.yout,
        zout=config.mesh.zout,
    )

    editor = case.input_editor()
    editor.set_initial_velocity(config.input.u, config.input.v, config.input.w)
    editor.set_re_dt(config.input.re, config.input.dt)
    editor.set_internal_boundary(
        present=config.input.ib_present,
        body_type=config.input.body_type,
        formulation=config.input.formulation,
    )
    editor.write()

    errors = case.validate()
    if errors:
        raise RuntimeError("Case validation failed:\n" + "\n".join(f"- {error}" for error in errors))
    return case


def build_2d_cylinder_case(
    case_dir: str | Path = "example/generated_circle2d_case",
    center: tuple[float, float, float] = (19.2, 10.0, 0.005),
    radius: float = 0.25,
    points: int = 600,
    thickness: float = 0.01,
    layers: int = 3,
) -> CaseProject:
    """Build the default thin side-wall 2D cylinder case."""
    config = CaseBuildConfig(
        case_dir=case_dir,
        surface=SurfaceBuildConfig(
            kind="circle",
            params={"radius": radius, "n": points, "layers": layers},
            center=center,
            thickness=thickness,
        ),
    )
    return build_case(config)
