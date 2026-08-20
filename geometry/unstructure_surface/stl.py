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
    except ModuleNotFoundError:
        _write_binary_stl_fallback(bodies, out)
    return out


def stl_to_surface_body(stl_file: str | Path, precision: int = 8) -> SurfaceBody:
    """Convert an STL triangular mesh to one SurfaceBody."""
    try:
        import trimesh

        mesh = trimesh.load_mesh(Path(stl_file), process=False)
        vertices = np.asarray(mesh.vertices)
        faces = np.asarray(mesh.faces)
    except ModuleNotFoundError:
        vertices, faces = _read_stl_mesh_fallback(Path(stl_file))

    unique_vertices, inverse = np.unique(np.round(vertices, precision), axis=0, return_inverse=True)
    remapped_faces = inverse[faces] + 1

    nodes = np.zeros((len(unique_vertices), 4), dtype=float)
    nodes[:, 0] = np.arange(1, len(unique_vertices) + 1)
    nodes[:, 1:4] = unique_vertices

    elems = np.zeros((len(remapped_faces), 4), dtype=int)
    elems[:, 0] = np.arange(1, len(remapped_faces) + 1)
    elems[:, 1:4] = remapped_faces

    return SurfaceBody(nodes=nodes, elems=elems)


def obj_to_surface_body(obj_file: str | Path, precision: int = 8) -> SurfaceBody:
    """Convert a Wavefront OBJ triangular/polygon mesh to one SurfaceBody."""
    try:
        import trimesh

        mesh = trimesh.load_mesh(Path(obj_file), process=False)
        vertices = np.asarray(mesh.vertices)
        faces = np.asarray(mesh.faces)
    except ModuleNotFoundError:
        vertices, faces = _read_obj_mesh_fallback(Path(obj_file))

    unique_vertices, inverse = np.unique(np.round(vertices, precision), axis=0, return_inverse=True)
    remapped_faces = inverse[faces] + 1

    nodes = np.zeros((len(unique_vertices), 4), dtype=float)
    nodes[:, 0] = np.arange(1, len(unique_vertices) + 1)
    nodes[:, 1:4] = unique_vertices

    elems = np.zeros((len(remapped_faces), 4), dtype=int)
    elems[:, 0] = np.arange(1, len(remapped_faces) + 1)
    elems[:, 1:4] = remapped_faces

    return SurfaceBody(nodes=nodes, elems=elems)


def _read_obj_mesh_fallback(obj_file: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read Wavefront OBJ vertices and polygon faces without optional trimesh."""
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    with obj_file.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if parts[0] == "v":
                if len(parts) < 4:
                    raise ValueError(f"OBJ vertex has fewer than 3 coordinates: {obj_file}")
                vertices.append([float(value) for value in parts[1:4]])
            elif parts[0] == "f":
                face = [_parse_obj_face_index(token, len(vertices), obj_file) for token in parts[1:]]
                if len(face) < 3:
                    raise ValueError(f"OBJ face has fewer than 3 vertices: {obj_file}")
                for idx in range(1, len(face) - 1):
                    faces.append([face[0], face[idx], face[idx + 1]])

    if not vertices:
        raise ValueError(f"No OBJ vertices found in {obj_file}")
    if not faces:
        raise ValueError(f"No OBJ faces found in {obj_file}")
    return np.asarray(vertices, dtype=float), np.asarray(faces, dtype=int)


def _parse_obj_face_index(token: str, vertex_count: int, obj_file: Path) -> int:
    raw = token.split("/", 1)[0]
    if raw == "":
        raise ValueError(f"OBJ face is missing a vertex index: {obj_file}")
    index = int(raw)
    if index < 0:
        index = vertex_count + index + 1
    if index < 1 or index > vertex_count:
        raise ValueError(f"OBJ face index {raw} is out of range in {obj_file}")
    return index - 1


def _read_stl_mesh_fallback(stl_file: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read ASCII or binary STL without optional trimesh dependency."""
    data = stl_file.read_bytes()
    vertices = _read_binary_stl_vertices(data)
    if vertices is None:
        vertices = _read_ascii_stl_vertices(data)
    if vertices.size == 0:
        raise ValueError(f"No STL triangles found in {stl_file}")
    if vertices.shape[0] % 3 != 0:
        raise ValueError(f"STL vertex count is not divisible by 3: {stl_file}")
    faces = np.arange(vertices.shape[0], dtype=int).reshape((-1, 3))
    return vertices, faces


def _read_binary_stl_vertices(data: bytes) -> np.ndarray | None:
    if len(data) < 84:
        return None
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected_size = 84 + triangle_count * 50
    if expected_size != len(data):
        return None
    dtype = np.dtype([
        ("normal", "<f4", (3,)),
        ("vertices", "<f4", (3, 3)),
        ("attribute", "<u2"),
    ])
    records = np.frombuffer(data, dtype=dtype, offset=84, count=triangle_count)
    return np.asarray(records["vertices"], dtype=float).reshape((-1, 3))


def _read_ascii_stl_vertices(data: bytes) -> np.ndarray:
    text = data.decode("utf-8", errors="ignore")
    points: list[list[float]] = []
    for match in re.finditer(
        r"^\s*vertex\s+([+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?)\s+"
        r"([+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?)\s+"
        r"([+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?)",
        text,
        flags=re.MULTILINE,
    ):
        points.append([float(value.replace("D", "E").replace("d", "E")) for value in match.groups()])
    return np.asarray(points, dtype=float)


def _write_binary_stl_fallback(bodies: list[SurfaceBody], output_stl: Path) -> None:
    triangles = []
    for body_index, body in enumerate(bodies, start=1):
        if body.elem_count == 0:
            raise ValueError(f"Cannot export body {body_index} with zero elements to STL")
        node_ids = body.nodes[:, 0].astype(int)
        id_to_index = {node_id: idx for idx, node_id in enumerate(node_ids)}
        for elem in body.elems[:, 1:4].astype(int):
            try:
                tri = body.points[[id_to_index[int(node_id)] for node_id in elem]]
            except KeyError as exc:
                raise ValueError(f"Element references missing node id {exc.args[0]}") from exc
            triangles.append(np.asarray(tri, dtype=np.float32))

    header = b"Picar_Pre binary STL".ljust(80, b" ")
    with output_stl.open("wb") as handle:
        handle.write(header)
        handle.write(struct.pack("<I", len(triangles)))
        for tri in triangles:
            normal = _triangle_normal(tri)
            handle.write(struct.pack("<12fH", *normal, *tri.reshape(9), 0))


def _triangle_normal(triangle: np.ndarray) -> np.ndarray:
    normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
    length = float(np.linalg.norm(normal))
    if length <= 0.0:
        return np.zeros(3, dtype=np.float32)
    return np.asarray(normal / length, dtype=np.float32)


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
