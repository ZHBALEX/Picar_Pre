from __future__ import annotations

import base64
import io
import struct
from pathlib import Path

import numpy as np

from case_editor.run_picar_console import _handle_post_api
from geometry.unstructure_surface.modeling import make_ellipse_2d, make_rectangle_2d
from geometry.unstructure_surface.surface import SurfaceBody, read_surface, write_surface
from motion.fort import fort_motion_info, read_frame


def _surface_text(tmp_path: Path, name: str, bodies) -> str:
    path = tmp_path / name
    write_surface(path, bodies)
    return path.read_text(encoding="utf-8")


def _fort_bytes(node_count: int, frames: int = 1, dt: float = 0.01, vector: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> bytes:
    stream = io.BytesIO()
    for frame in range(frames):
        stream.write(struct.pack("<iddii", 20, dt, frame * dt, node_count, 20))
        for _ in range(node_count):
            stream.write(struct.pack("<i3di", 24, *vector, 24))
    return stream.getvalue()


def _fort_series_bytes(vectors: list[tuple[float, float, float]], dt: float) -> bytes:
    stream = io.BytesIO()
    for frame, vector in enumerate(vectors, start=1):
        stream.write(struct.pack("<iddii", 20, dt, frame * dt, 1, 20))
        stream.write(struct.pack("<i3di", 24, *vector, 24))
    return stream.getvalue()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def test_surface_dat_append_adds_uploaded_bodies(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    first = make_ellipse_2d(n=8)
    second = make_rectangle_2d()
    write_surface(case_dir / "unstruc_surface_in.dat", [first])

    result = _handle_post_api(
        "/api/geometry/save-surface",
        {
            "case_dir": str(case_dir),
            "content": _surface_text(tmp_path, "upload_surface.dat", [second]),
            "mode": "append",
        },
        case_dir,
    )

    bodies = read_surface(case_dir / "unstruc_surface_in.dat")
    assert result["mode"] == "append"
    assert result["imported_bodies"] == 1
    assert len(bodies) == 2
    assert bodies[0].node_count == first.node_count
    assert bodies[1].node_count == second.node_count


def test_surface_dat_replace_keeps_only_uploaded_bodies(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    first = make_ellipse_2d(n=8)
    second = make_rectangle_2d()
    write_surface(case_dir / "unstruc_surface_in.dat", [first])

    _handle_post_api(
        "/api/geometry/save-surface",
        {
            "case_dir": str(case_dir),
            "content": _surface_text(tmp_path, "replacement_surface.dat", [second]),
            "mode": "replace",
        },
        case_dir,
    )

    bodies = read_surface(case_dir / "unstruc_surface_in.dat")
    assert len(bodies) == 1
    assert bodies[0].node_count == second.node_count


def test_fort_append_uses_first_missing_body_fort_name(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    bodies = [make_ellipse_2d(n=8), make_rectangle_2d()]
    write_surface(case_dir / "unstruc_surface_in.dat", bodies)
    (case_dir / "fort.41").write_bytes(_fort_bytes(bodies[0].node_count))

    result = _handle_post_api(
        "/api/fort/import",
        {
            "case_dir": str(case_dir),
            "filename": "uploaded_fort",
            "content_base64": _b64(_fort_bytes(bodies[1].node_count, frames=2)),
            "mode": "append",
            "fort_start": 41,
            "auto_rename": True,
        },
        case_dir,
    )

    info = fort_motion_info(case_dir / "fort.42")
    assert result["name"] == "fort.42"
    assert result["body"] == 2
    assert info.node_count == bodies[1].node_count
    assert info.frame_count == 2


def test_fort_replace_overwrites_selected_body_fort(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    body = make_ellipse_2d(n=8)
    write_surface(case_dir / "unstruc_surface_in.dat", [body])
    (case_dir / "fort.41").write_bytes(_fort_bytes(body.node_count))

    result = _handle_post_api(
        "/api/fort/import",
        {
            "case_dir": str(case_dir),
            "filename": "replacement_fort",
            "content_base64": _b64(_fort_bytes(4, frames=3)),
            "mode": "replace",
            "fort_start": 41,
            "body_id": 1,
        },
        case_dir,
    )

    info = fort_motion_info(case_dir / "fort.41")
    assert result["replaced"] is True
    assert result["info"]["node_match"] is False
    assert info.node_count == 4
    assert info.frame_count == 3


def test_fort_resample_interpolates_cycle_phase(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    write_surface(case_dir / "unstruc_surface_in.dat", [make_ellipse_2d(n=1)])
    (case_dir / "fort.41").write_bytes(
        _fort_series_bytes(
            [
                (10.0, 1.0, 0.0),
                (20.0, 2.0, 0.0),
                (30.0, 3.0, 0.0),
                (40.0, 4.0, 0.0),
            ],
            dt=0.25,
        )
    )

    result = _handle_post_api(
        "/api/fort/resample",
        {
            "case_dir": str(case_dir),
            "body_id": 1,
            "source_steps_per_cycle": 4,
            "target_steps_per_cycle": 3,
            "component_order": "xyz",
        },
        case_dir,
    )

    info = fort_motion_info(case_dir / "fort.41")
    headers_vectors = [read_frame(case_dir / "fort.41", frame) for frame in range(3)]
    times = [header.time for header, _ in headers_vectors]
    values = np.asarray([vectors[0] for _, vectors in headers_vectors])
    assert result["before"]["frames"] == 4
    assert result["after"]["frames"] == 3
    assert info.frame_count == 3
    np.testing.assert_allclose(times, [1.0 / 3.0, 2.0 / 3.0, 1.0])
    np.testing.assert_allclose(values[:, 0], [40.0 / 3.0, 80.0 / 3.0, 40.0])
    np.testing.assert_allclose(values[:, 1], [4.0 / 3.0, 8.0 / 3.0, 4.0])


def test_fort_preview_includes_motion_envelope_frame(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    write_surface(case_dir / "unstruc_surface_in.dat", [make_ellipse_2d(n=1)])
    (case_dir / "fort.41").write_bytes(
        _fort_series_bytes(
            [
                (0.0, 0.0, 0.0),
                (10.0, 0.0, 0.0),
                (0.0, 0.0, 0.0),
            ],
            dt=1.0,
        )
    )

    result = _handle_post_api(
        "/api/fort/preview",
        {
            "case_dir": str(case_dir),
            "body_id": 1,
            "samples": 2,
            "frame": 2,
            "motion_mode": "displacement",
        },
        case_dir,
    )

    frames = [item["frame"] for item in result["frames"]]
    assert frames == [0, 1, 2]


def test_swap_yz_surface_and_matching_fort_for_selected_body(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    body1 = make_ellipse_2d(n=4)
    body2 = SurfaceBody(
        nodes=np.asarray(
            [
                [1, 0.0, 10.0, 100.0],
                [2, 1.0, 20.0, 200.0],
                [3, 2.0, 30.0, 300.0],
            ],
            dtype=float,
        ),
        elems=np.asarray([[1, 1, 2, 3]], dtype=int),
    )
    write_surface(case_dir / "unstruc_surface_in.dat", [body1, body2])
    (case_dir / "fort.41").write_bytes(_fort_bytes(body1.node_count, vector=(1.0, 2.0, 3.0)))
    (case_dir / "fort.42").write_bytes(_fort_bytes(body2.node_count, vector=(4.0, 5.0, 6.0)))

    result = _handle_post_api(
        "/api/geometry/swap-yz-fort",
        {
            "case_dir": str(case_dir),
            "body_ids": [2],
            "fort_start": 41,
            "component_order": "xyz",
        },
        case_dir,
    )

    bodies = read_surface(case_dir / "unstruc_surface_in.dat")
    _, fort1 = read_frame(case_dir / "fort.41", 0)
    _, fort2 = read_frame(case_dir / "fort.42", 0)
    np.testing.assert_allclose(bodies[0].points, body1.points, atol=1.0e-14)
    np.testing.assert_allclose(bodies[1].points[:, 1], body2.points[:, 2])
    np.testing.assert_allclose(bodies[1].points[:, 2], body2.points[:, 1])
    np.testing.assert_array_equal(bodies[1].elems, np.asarray([[1, 1, 3, 2]], dtype=int))
    np.testing.assert_allclose(fort1[0], [1.0, 2.0, 3.0])
    np.testing.assert_allclose(fort2[0], [4.0, 6.0, 5.0])
    assert result["forts"][0]["name"] == "fort.42"


def test_swap_yz_requires_matching_fort_before_surface_write(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    body = SurfaceBody(
        nodes=np.asarray([[1, 0.0, 1.0, 2.0], [2, 1.0, 3.0, 4.0]], dtype=float),
        elems=np.empty((0, 4), dtype=int),
    )
    write_surface(case_dir / "unstruc_surface_in.dat", [body])

    try:
        _handle_post_api(
            "/api/geometry/swap-yz-fort",
            {
                "case_dir": str(case_dir),
                "body_ids": [1],
                "fort_start": 41,
            },
            case_dir,
        )
    except FileNotFoundError as exc:
        assert "fort.41" in str(exc)
    else:
        raise AssertionError("Expected missing fort file to block Y/Z swap")

    bodies = read_surface(case_dir / "unstruc_surface_in.dat")
    np.testing.assert_allclose(bodies[0].points, body.points)
