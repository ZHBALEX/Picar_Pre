from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from geometry.unstructure_surface.surface import SurfaceBody, read_surface


SEP = "_" * 124


@dataclass
class CanonicalBody:
    """One body record in canonical_body_in.dat."""

    motion_type: int
    zone_max: int
    nodes: int
    elems: int


@dataclass
class CanonicalBodyConfig:
    """Minimal canonical body configuration."""

    bodies: list[CanonicalBody]
    nbody_solid: int
    nbody_membrane: int = 0
    nsection: int = 1
    density_fluid: float = 1.0
    density_solid: float = 1.001
    plate_thickness: float = 0.1
    depth_over_length: float = 0.02
    channel_flow: bool = False
    zoneseparate: bool = False
    prsb_momentum_ref: bool = False

    @property
    def nbody(self) -> int:
        return len(self.bodies)


def canonical_from_surface(
    surface_path: str | Path,
    nbody_solid: int | None = None,
    nbody_membrane: int = 0,
    motion_type: int = 3,
    zone_max: int = 1,
) -> CanonicalBodyConfig:
    """Build a canonical body config from surface body counts."""
    surface_bodies = read_surface(surface_path)
    if nbody_solid is None:
        nbody_solid = len(surface_bodies)
    bodies = [
        CanonicalBody(motion_type=motion_type, zone_max=zone_max, nodes=body.node_count, elems=body.elem_count)
        for body in surface_bodies
    ]
    return CanonicalBodyConfig(bodies=bodies, nbody_solid=nbody_solid, nbody_membrane=nbody_membrane)


def canonical_from_bodies(
    bodies: list[SurfaceBody],
    nbody_solid: int | None = None,
    nbody_membrane: int = 0,
    motion_type: int = 3,
    zone_max: int = 1,
) -> CanonicalBodyConfig:
    """Build a canonical body config from loaded SurfaceBody objects."""
    if nbody_solid is None:
        nbody_solid = len(bodies)
    records = [
        CanonicalBody(motion_type=motion_type, zone_max=zone_max, nodes=body.node_count, elems=body.elem_count)
        for body in bodies
    ]
    return CanonicalBodyConfig(bodies=records, nbody_solid=nbody_solid, nbody_membrane=nbody_membrane)


def write_canonical_body(path: str | Path, config: CanonicalBodyConfig) -> Path:
    """Write a minimal solver-compatible canonical_body_in.dat."""
    out = Path(path)
    flags = [_bool_flag(config.channel_flow), _bool_flag(config.zoneseparate), _bool_flag(config.prsb_momentum_ref)]
    lines = [
        f"{config.nbody}   {config.nbody_solid}   {config.nbody_membrane}   {config.nsection}   {'   '.join(flags)}       ! nbody, nbody_solid, nbody_membrane, nsection, channel_flow, zoneseparate, Prsb_MomentumRef",
        f"{config.density_fluid:.6g}    {config.density_solid:.6g}                   ! density_fluid, density_solid",
        f"{config.plate_thickness:.6g}    {config.depth_over_length:.6g}                     ! plate thickness, depthOverLength",
    ]
    for body in config.bodies:
        lines.extend(
            [
                SEP,
                f"{body.motion_type:<9d} {body.zone_max:<9d}              ! motion_type, zoneMax",
                f"{body.nodes:<9d} {body.elems:<9d}              ! nPtsBodyMarker, totNumTriElem",
            ]
        )

    lines.extend(
        [
            "",
            "",
            "!=========================",
            "*  body type: (1:ellipse; 2: general_cylinder; 3: ellipsoid, 4: unstructured surface)",
            "** motion_type (0:Stationary, 1:Forced, 2:Flow Induced, 3:Prescribed)",
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def read_canonical_body(path: str | Path) -> CanonicalBodyConfig:
    """Read the minimal body counts from canonical_body_in.dat."""
    lines = [line.strip() for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
    if len(lines) < 3:
        raise ValueError(f"Invalid canonical body file: {path}")

    header = lines[0].split()
    nbody = int(header[0])
    nbody_solid = int(header[1])
    nbody_membrane = int(header[2])
    nsection = int(header[3])
    density = lines[1].split()
    thickness = lines[2].split()

    bodies: list[CanonicalBody] = []
    idx = 3
    while idx < len(lines) and len(bodies) < nbody:
        if lines[idx].startswith("_"):
            motion = lines[idx + 1].split()
            counts = lines[idx + 2].split()
            bodies.append(
                CanonicalBody(
                    motion_type=int(motion[0]),
                    zone_max=int(motion[1]),
                    nodes=int(counts[0]),
                    elems=int(counts[1]),
                )
            )
            idx += 3
        else:
            idx += 1

    if len(bodies) != nbody:
        raise ValueError(f"Expected {nbody} body records, found {len(bodies)}")

    return CanonicalBodyConfig(
        bodies=bodies,
        nbody_solid=nbody_solid,
        nbody_membrane=nbody_membrane,
        nsection=nsection,
        density_fluid=float(density[0]),
        density_solid=float(density[1]),
        plate_thickness=float(thickness[0]),
        depth_over_length=float(thickness[1]),
    )


def canonical_summary(config: CanonicalBodyConfig) -> str:
    """Return a compact canonical body summary."""
    lines = [
        "Canonical Body",
        "==============",
        f"nbody          : {config.nbody}",
        f"nbody_solid    : {config.nbody_solid}",
        f"nbody_membrane : {config.nbody_membrane}",
        "Body  Motion  Zone  Nodes  Elems",
        "---------------------------------",
    ]
    for idx, body in enumerate(config.bodies, start=1):
        lines.append(f"{idx:>4}  {body.motion_type:>6}  {body.zone_max:>4}  {body.nodes:>5}  {body.elems:>5}")
    return "\n".join(lines)


def _bool_flag(value: bool) -> str:
    return "T" if value else "F"
