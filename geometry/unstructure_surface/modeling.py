from __future__ import annotations

import math

import numpy as np

from .surface import SurfaceBody, transform_body


def body_from_points_and_faces(points: np.ndarray, faces: np.ndarray) -> SurfaceBody:
    """Build a SurfaceBody from 0-based triangle faces."""
    points = np.asarray(points, dtype=float)
    faces = np.asarray(faces, dtype=int)

    nodes = np.zeros((len(points), 4), dtype=float)
    nodes[:, 0] = np.arange(1, len(points) + 1)
    nodes[:, 1:4] = points

    elems = np.zeros((len(faces), 4), dtype=int)
    elems[:, 0] = np.arange(1, len(faces) + 1)
    elems[:, 1:4] = faces + 1
    return SurfaceBody(nodes=nodes, elems=elems)


def body_from_boundary_points(points: np.ndarray) -> SurfaceBody:
    """Build a boundary-only SurfaceBody with no elements."""
    points = np.asarray(points, dtype=float)
    nodes = np.zeros((len(points), 4), dtype=float)
    nodes[:, 0] = np.arange(1, len(points) + 1)
    nodes[:, 1:4] = points
    return SurfaceBody(nodes=nodes, elems=np.empty((0, 4), dtype=int))


def make_ellipse_2d(
    rx: float = 0.5,
    ry: float = 0.25,
    n: int = 96,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    plane: str = "xy",
) -> SurfaceBody:
    """Create a flat ellipse boundary with no interior points or elements."""
    theta = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    local = np.column_stack([rx * np.cos(theta), ry * np.sin(theta), np.zeros_like(theta)])
    points = _place_planar_points(local, center=center, plane=plane)
    return body_from_boundary_points(points)


def make_rectangle_2d(
    width: float = 1.0,
    height: float = 0.5,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    plane: str = "xy",
) -> SurfaceBody:
    """Create a flat rectangle boundary with no interior points or elements."""
    x = width / 2.0
    y = height / 2.0
    local = np.array([[-x, -y, 0.0], [x, -y, 0.0], [x, y, 0.0], [-x, y, 0.0]])
    points = _place_planar_points(local, center=center, plane=plane)
    return body_from_boundary_points(points)


def make_naca_2d(
    code: str = "0012",
    chord: float = 1.0,
    n: int = 80,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    plane: str = "xy",
) -> SurfaceBody:
    """Create a simple NACA 4-digit airfoil boundary with no interior elements."""
    if len(code) != 4 or not code.isdigit():
        raise ValueError("NACA code must be a 4-digit string, for example '0012' or '2412'")

    m = int(code[0]) / 100.0
    p = int(code[1]) / 10.0
    t = int(code[2:]) / 100.0

    beta = np.linspace(0.0, math.pi, n)
    x = 0.5 * (1.0 - np.cos(beta))
    yt = 5.0 * t * (
        0.2969 * np.sqrt(x)
        - 0.1260 * x
        - 0.3516 * x**2
        + 0.2843 * x**3
        - 0.1015 * x**4
    )

    yc = np.zeros_like(x)
    dyc_dx = np.zeros_like(x)
    if m > 0.0 and p > 0.0:
        front = x < p
        rear = ~front
        yc[front] = m / p**2 * (2.0 * p * x[front] - x[front] ** 2)
        yc[rear] = m / (1.0 - p) ** 2 * ((1.0 - 2.0 * p) + 2.0 * p * x[rear] - x[rear] ** 2)
        dyc_dx[front] = 2.0 * m / p**2 * (p - x[front])
        dyc_dx[rear] = 2.0 * m / (1.0 - p) ** 2 * (p - x[rear])

    theta = np.arctan(dyc_dx)
    xu = x - yt * np.sin(theta)
    yu = yc + yt * np.cos(theta)
    xl = x + yt * np.sin(theta)
    yl = yc - yt * np.cos(theta)

    upper = np.column_stack([xu[::-1], yu[::-1]])
    lower = np.column_stack([xl[1:], yl[1:]])
    curve = np.vstack([upper, lower])
    curve[:, 0] -= 0.5
    curve *= chord

    local = np.column_stack([curve[:, 0], curve[:, 1], np.zeros(len(curve))])
    points = _place_planar_points(local, center=center, plane=plane)
    return body_from_boundary_points(points)


def extrude_body(body: SurfaceBody, thickness: float, axis: str = "z") -> SurfaceBody:
    """Extrude an ordered boundary curve into a side-wall surface."""
    if thickness <= 0:
        raise ValueError("thickness must be positive")

    points = body.points
    offset = np.zeros(3)
    axis_i = _axis_index(axis)
    offset[axis_i] = thickness / 2.0

    bottom = points - offset
    top = points + offset
    all_points = np.vstack([bottom, top])
    n = len(points)

    faces = []
    for a in range(n):
        b = 0 if a == n - 1 else a + 1
        faces.append([a, b, b + n])
        faces.append([a, b + n, a + n])

    return body_from_points_and_faces(all_points, np.asarray(faces, dtype=int))


def make_parametric_body(
    kind: str,
    *,
    center: tuple[float, float, float] = (0.0, 0.0, 0.0),
    plane: str = "xy",
    thickness: float = 0.0,
    rotation=None,
    translate=None,
    scale=1.0,
    **params,
) -> SurfaceBody:
    """Create a simple parametric body and apply optional transform."""
    kind = kind.lower()
    if kind == "circle":
        body = make_ellipse_2d(
            rx=float(params.get("radius", 0.5)),
            ry=float(params.get("radius", 0.5)),
            n=int(params.get("n", 96)),
            center=center,
            plane=plane,
        )
    elif kind == "ellipse":
        body = make_ellipse_2d(
            rx=float(params.get("rx", 0.5)),
            ry=float(params.get("ry", 0.25)),
            n=int(params.get("n", 96)),
            center=center,
            plane=plane,
        )
    elif kind == "rectangle":
        body = make_rectangle_2d(
            width=float(params.get("width", 1.0)),
            height=float(params.get("height", 0.5)),
            center=center,
            plane=plane,
        )
    elif kind == "naca":
        body = make_naca_2d(
            code=str(params.get("code", "0012")),
            chord=float(params.get("chord", 1.0)),
            n=int(params.get("n", 80)),
            center=center,
            plane=plane,
        )
    else:
        raise ValueError(f"Unsupported parametric body kind: {kind}")

    if thickness > 0.0:
        body = extrude_body(body, thickness=thickness, axis=_normal_axis_for_plane(plane))

    return transform_body(body, rotation=rotation, translate=translate, scale=scale)


def _place_planar_points(points: np.ndarray, center: tuple[float, float, float], plane: str) -> np.ndarray:
    center_arr = np.asarray(center, dtype=float)
    plane = plane.lower()
    placed = np.zeros_like(points)

    if plane == "xy":
        placed[:, [0, 1, 2]] = points[:, [0, 1, 2]]
    elif plane == "xz":
        placed[:, 0] = points[:, 0]
        placed[:, 2] = points[:, 1]
    elif plane == "yz":
        placed[:, 1] = points[:, 0]
        placed[:, 2] = points[:, 1]
    else:
        raise ValueError("plane must be 'xy', 'xz', or 'yz'")

    return placed + center_arr


def _normal_axis_for_plane(plane: str) -> str:
    return {"xy": "z", "xz": "y", "yz": "x"}[plane.lower()]


def _axis_index(axis: str) -> int:
    axis = axis.lower()
    if axis == "x":
        return 0
    if axis == "y":
        return 1
    if axis == "z":
        return 2
    raise ValueError("axis must be 'x', 'y', or 'z'")

