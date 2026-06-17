from __future__ import annotations

from pathlib import Path

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
    mesh = surface_bodies_to_trimesh(bodies)
    mesh.export(out)
    return out


def stl_to_surface_body(stl_file: str | Path, precision: int = 8) -> SurfaceBody:
    """Convert an STL triangular mesh to one SurfaceBody."""
    import trimesh

    mesh = trimesh.load_mesh(Path(stl_file), process=False)
    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.faces)

    unique_vertices, inverse = np.unique(np.round(vertices, precision), axis=0, return_inverse=True)
    remapped_faces = inverse[faces] + 1

    nodes = np.zeros((len(unique_vertices), 4), dtype=float)
    nodes[:, 0] = np.arange(1, len(unique_vertices) + 1)
    nodes[:, 1:4] = unique_vertices

    elems = np.zeros((len(remapped_faces), 4), dtype=int)
    elems[:, 0] = np.arange(1, len(remapped_faces) + 1)
    elems[:, 1:4] = remapped_faces

    return SurfaceBody(nodes=nodes, elems=elems)


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
