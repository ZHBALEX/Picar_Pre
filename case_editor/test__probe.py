from __future__ import annotations

from pathlib import Path

import numpy as np

from case_editor.probe import (
    ProbeSpec,
    generate_surface_marker_probes,
    nearest_surface_node,
    parse_probe_text,
    read_probe_payload,
    resolve_marker_reference,
    write_probe_file,
)
from case_editor.run_picar_console import _generate_probe_payload, _resolve_probe_payload, _save_probe_payload, _snap_probe_payload
from geometry.unstructure_surface.surface import SurfaceBody, write_surface


def _sample_body() -> SurfaceBody:
    # Deliberately use sparse node ids to verify that generation never assumes
    # an array index plus one is the solver reference.
    nodes = np.array(
        [
            [101, -1.0, 0.0, 1.0],
            [105, -1.0, 0.0, -1.0],
            [110, 0.0, 0.0, 1.0],
            [120, 0.0, 0.0, -1.0],
            [135, 1.0, 0.0, 1.0],
            [150, 1.0, 0.0, -1.0],
        ],
        dtype=float,
    )
    return SurfaceBody(nodes=nodes, elems=np.empty((0, 4), dtype=int))


def test_generate_surface_probes_uses_real_node_ids() -> None:
    probes = generate_surface_marker_probes(
        _sample_body(),
        1,
        plane_axis="y",
        plane_value=0.0,
        n_samples=3,
        plane_tolerance=1e-12,
        x_band_factor=0.25,
    )

    assert [probe["reference"] for probe in probes] == [105, 120, 150, 101, 110, 135]
    assert all(probe["body"] == 1 for probe in probes)


def test_wide_x_band_still_selects_uniform_nearest_stations() -> None:
    nodes = []
    node_id = 10
    for x, half_width in [(-1.0, 8.0), (0.0, 1.0), (1.0, 6.0)]:
        nodes.append([node_id, x, -half_width, 0.0])
        nodes.append([node_id + 1, x, half_width, 0.0])
        node_id += 10
    body = SurfaceBody(nodes=np.asarray(nodes), elems=np.empty((0, 4), dtype=int))

    probes = generate_surface_marker_probes(
        body,
        1,
        plane_axis="z",
        plane_value=0.0,
        n_samples=3,
        plane_tolerance=1e-12,
        x_band_factor=1.5,
        deduplicate=False,
    )

    lower_x = [probe["point"][0] for probe in probes if probe["side"] == "lower"]
    upper_x = [probe["point"][0] for probe in probes if probe["side"] == "upper"]
    assert lower_x == [-1.0, 0.0, 1.0]
    assert upper_x == [-1.0, 0.0, 1.0]
    assert max(probe["x_error"] for probe in probes) == 0.0
    assert max(probe["plane_error"] for probe in probes) == 0.0


def test_slice_selection_never_mixes_distant_plane_points() -> None:
    nodes = []
    node_id = 1
    for x in [-1.0, 0.0, 1.0]:
        nodes.extend(
            [
                [node_id, x, -1.0, 0.0],
                [node_id + 1, x, 1.0, 0.0],
                [node_id + 2, x, -20.0, 0.5],
                [node_id + 3, x, 20.0, 0.5],
            ]
        )
        node_id += 10
    body = SurfaceBody(nodes=np.asarray(nodes), elems=np.empty((0, 4), dtype=int))

    probes = generate_surface_marker_probes(
        body,
        1,
        plane_axis="z",
        plane_value=0.0,
        n_samples=3,
        plane_tolerance=0.01,
        x_band_factor=1.5,
    )

    assert probes
    assert {probe["point"][2] for probe in probes} == {0.0}
    assert all(abs(probe["point"][1]) == 1.0 for probe in probes)


def test_missing_branch_in_narrow_x_bin_uses_neighbouring_branch() -> None:
    # At x=0 the narrow target bin contains only upper-side nodes.  The lower
    # branch is still present just outside that bin and must not be replaced by
    # a second upper point (the failure seen on the fish surface).
    nodes = np.asarray(
        [
            [1, -1.0, -1.0, 0.0],
            [2, -1.0, 1.0, 0.0],
            [3, -0.49, -1.0, 0.001],
            [4, -0.05, 0.9, 0.002],
            [5, 0.04, 1.1, 0.001],
            [6, 0.49, -1.0, 0.001],
            [7, 1.0, -1.0, 0.0],
            [8, 1.0, 1.0, 0.0],
        ],
        dtype=float,
    )
    body = SurfaceBody(nodes=nodes, elems=np.empty((0, 4), dtype=int))

    probes = generate_surface_marker_probes(
        body,
        1,
        plane_axis="z",
        plane_value=0.0,
        n_samples=3,
        plane_tolerance=0.01,
        x_band_factor=0.25,
        deduplicate=False,
    )

    middle = [probe for probe in probes if np.isclose(probe["target_x"], 0.0)]
    lower = next(probe for probe in middle if probe["side"] == "lower")
    upper = next(probe for probe in middle if probe["side"] == "upper")
    assert lower["point"][1] < 0.0
    assert upper["point"][1] > 0.0


def test_probe_writer_roundtrips_marker_and_fluid_records(tmp_path: Path) -> None:
    path = tmp_path / "probe_in.dat"
    source = ProbeSpec(
        marker_bodies=[1, 2],
        marker_refs=[101, 202],
        fluid_points=[(1.25, -2.5, 3.75)],
        errors=[],
    )

    write_probe_file(path, source)
    parsed = parse_probe_text(path.read_text(encoding="utf-8"))

    assert parsed.marker_bodies == source.marker_bodies
    assert parsed.marker_refs == source.marker_refs
    assert parsed.fluid_points == source.fluid_points
    assert parsed.errors == []


def test_empty_probe_file_layout_remains_parseable(tmp_path: Path) -> None:
    path = tmp_path / "probe_in.dat"
    write_probe_file(path, ProbeSpec([], [], [], []))

    parsed = parse_probe_text(path.read_text(encoding="utf-8"))

    assert parsed.marker_count == 0
    assert parsed.fluid_count == 0
    assert parsed.errors == []


def test_nearest_surface_node_returns_reference_position_and_distance() -> None:
    result = nearest_surface_node(_sample_body(), [0.05, 0.0, 0.8])

    assert result["reference"] == 110
    assert result["point"] == [0.0, 0.0, 1.0]
    assert np.isclose(result["distance"], np.sqrt(0.05**2 + 0.2**2))


def test_marker_reference_resolves_for_manual_target_highlight() -> None:
    result = resolve_marker_reference(_sample_body(), 120)

    assert result == {"reference": 120, "source": "node", "point": [0.0, 0.0, -1.0]}


def test_console_probe_generate_snap_and_save_workflow(tmp_path: Path) -> None:
    write_surface(tmp_path / "unstruc_surface_in.dat", [_sample_body()])

    generated = _generate_probe_payload(
        tmp_path,
        {
            "body_id": 1,
            "plane_axis": "y",
            "plane_value": 0.0,
            "n_samples": 3,
            "plane_tolerance": 1e-12,
            "x_band_factor": 0.25,
            "sides": "both",
            "deduplicate": True,
        },
    )
    assert generated["preview"] is True
    assert generated["marker_count"] == 6
    assert not (tmp_path / "probe_in.dat").exists()

    snapped = _snap_probe_payload(tmp_path, {"body_id": 1, "point": [0.1, 0.0, -0.9]})
    assert snapped["reference"] == 120
    resolved = _resolve_probe_payload(tmp_path, {"body_id": 1, "reference": 135})
    assert resolved["point"] == [1.0, 0.0, 1.0]

    saved = _save_probe_payload(
        tmp_path,
        {
            "markers": generated["markers"],
            "fluids": [{"point": [2.0, 3.0, 4.0]}],
        },
    )
    reread = read_probe_payload(tmp_path / "probe_in.dat", [_sample_body()])

    assert saved["saved"] is True
    assert saved["marker_count"] == 6
    assert reread["fluid_count"] == 1
    assert reread["fluids"][0]["point"] == [2.0, 3.0, 4.0]
