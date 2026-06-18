from __future__ import annotations

from pathlib import Path
import re
import struct

import numpy as np

from .surface import SurfaceBody


def surface_body_to_trimesh(body: SurfaceBody):
    """Convert one triangulated surface body to a trimesh mesh."""
    import trimesh

    if body.elem_count == 0:
        raise ValueError("Cannot export a body with zero elements to STL")

    vertices = np.asarray(body.points, dtype=float)
    node_ids = body.nodes[:, 0].astype(int)
    id_to_index = {node_id: idx for idx, node_id in enumerate(node_ids)}

    faces = np.zeros((body.elem_count, 3), dtype=int)
    for row, elem in enumerate(body.elems[:, 1:4].astype(int)):
        try:
            faces[row] = [id_to_index[int(node_id)] for node_id in elem]
        except KeyError as exc:
            raise ValueError(f"Element references missing node id {exc.args[0]}") from exc

    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def surface_bodies_to_trimesh(bodies: list[SurfaceBody]):
    """Convert one or more triangulated surface bodies to one trimesh mesh."""
    import trimesh

    if not bodies:
        raise ValueError("No surface bodies were provided")

    meshes = [surface_body_to_trimesh(body) for body in bodies]
    if len(meshes) == 1:
        return meshes[0]
    return trimesh.util.concatenate(meshes)


def surface_bodies_to_stl(
    bodies: list[SurfaceBody],
    output_stl: str | Path,
) -> Path:
    """Export triangulated unstructured surface bodies to an STL file."""
    out = Path(output_stl)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        mesh = surface_bodies_to_trimesh(bodies)
        mesh.export(out)
    except ImportError:
        _write_ascii_stl(bodies, out)
    return out


def stl_to_surface_body(stl_file: str | Path, precision: int = 8) -> SurfaceBody:
    """Convert an STL triangular mesh to one SurfaceBody."""
    try:
        import trimesh

        mesh = trimesh.load_mesh(Path(stl_file), process=False)
        vertices = np.asarray(mesh.vertices)
        faces = np.asarray(mesh.faces)
    except ImportError:
        vertices, faces = _read_stl_without_trimesh(Path(stl_file))

    unique_vertices, inverse = np.unique(np.round(vertices, precision), axis=0, return_inverse=True)
    remapped_faces = inverse[faces] + 1

    nodes = np.zeros((len(unique_vertices), 4), dtype=float)
    nodes[:, 0] = np.arange(1, len(unique_vertices) + 1)
    nodes[:, 1:4] = unique_vertices

    elems = np.zeros((len(remapped_faces), 4), dtype=int)
    elems[:, 0] = np.arange(1, len(remapped_faces) + 1)
    elems[:, 1:4] = remapped_faces

    return SurfaceBody(nodes=nodes, elems=elems)


def _read_stl_without_trimesh(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = path.read_bytes()
    if _looks_like_binary_stl(data):
        return _read_binary_stl(data)
    return _read_ascii_stl(data.decode("utf-8", errors="ignore"))


def _looks_like_binary_stl(data: bytes) -> bool:
    if len(data) < 84:
        return False
    tri_count = struct.unpack_from("<I", data, 80)[0]
    return 84 + tri_count * 50 == len(data)


def _read_binary_stl(data: bytes) -> tuple[np.ndarray, np.ndarray]:
    tri_count = struct.unpack_from("<I", data, 80)[0]
    vertices = np.zeros((tri_count * 3, 3), dtype=float)
    faces = np.zeros((tri_count, 3), dtype=int)
    offset = 84
    for tri in range(tri_count):
        offset += 12
        for corner in range(3):
            vertices[tri * 3 + corner] = struct.unpack_from("<fff", data, offset)
            offset += 12
        faces[tri] = [tri * 3, tri * 3 + 1, tri * 3 + 2]
        offset += 2
    return vertices, faces


def _read_ascii_stl(text: str) -> tuple[np.ndarray, np.ndarray]:
    matches = re.findall(
        r"vertex\s+([+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?)\s+"
        r"([+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?)\s+"
        r"([+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if len(matches) < 3 or len(matches) % 3 != 0:
        raise ValueError("Could not parse ASCII STL vertices")
    vertices = np.asarray([[float(v.replace("D", "E").replace("d", "e")) for v in row] for row in matches], dtype=float)
    faces = np.arange(vertices.shape[0], dtype=int).reshape(-1, 3)
    return vertices, faces


def _write_ascii_stl(bodies: list[SurfaceBody], out: Path) -> None:
    with open(out, "w", encoding="utf-8") as f:
        f.write("solid picar_surface\n")
        for body in bodies:
            points = body.points
            for _, n1, n2, n3 in body.elems:
                p1, p2, p3 = points[int(n1) - 1], points[int(n2) - 1], points[int(n3) - 1]
                normal = np.cross(p2 - p1, p3 - p1)
                norm = np.linalg.norm(normal)
                if norm > 0:
                    normal = normal / norm
                f.write(f"  facet normal {normal[0]:.8e} {normal[1]:.8e} {normal[2]:.8e}\n")
                f.write("    outer loop\n")
                for p in (p1, p2, p3):
                    f.write(f"      vertex {p[0]:.8e} {p[1]:.8e} {p[2]:.8e}\n")
                f.write("    endloop\n")
                f.write("  endfacet\n")
        f.write("endsolid picar_surface\n")


def cut_stl_with_box(stl_file: str | Path, box_bounds: list[float], output_stl: str | Path | None = None):
    """Keep STL faces whose centers are inside the given box."""
    import trimesh

    mesh = trimesh.load_mesh(Path(stl_file), process=False)
    if len(box_bounds) != 6:
        raise ValueError("box_bounds must be [xmin, xmax, ymin, ymax, zmin, zmax]")

    xmin, xmax, ymin, ymax, zmin, zmax = box_bounds
    centers = mesh.vertices[mesh.faces].mean(axis=1)
    mask = (
        (centers[:, 0] >= xmin)
        & (centers[:, 0] <= xmax)
        & (centers[:, 1] >= ymin)
        & (centers[:, 1] <= ymax)
        & (centers[:, 2] >= zmin)
        & (centers[:, 2] <= zmax)
    )

    cut_mesh = trimesh.Trimesh(vertices=mesh.vertices.copy(), faces=mesh.faces[mask], process=False)
    cut_mesh.remove_unreferenced_vertices()

    if output_stl is not None:
        cut_mesh.export(Path(output_stl))

    return mesh, cut_mesh


def mesh_report(mesh, name: str = "Mesh") -> str:
    """Return a compact mesh summary."""
    bounds = mesh.bounds if len(mesh.vertices) else np.zeros((2, 3))
    return "\n".join(
        [
            f"{name}",
            f"  vertices : {len(mesh.vertices)}",
            f"  faces    : {len(mesh.faces)}",
            f"  x range  : [{bounds[0, 0]:.6f}, {bounds[1, 0]:.6f}]",
            f"  y range  : [{bounds[0, 1]:.6f}, {bounds[1, 1]:.6f}]",
            f"  z range  : [{bounds[0, 2]:.6f}, {bounds[1, 2]:.6f}]",
        ]
    )
