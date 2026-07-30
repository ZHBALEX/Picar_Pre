from __future__ import annotations

import shutil
import struct
from pathlib import Path

import numpy as np

from case_editor.canonical_body_editor import (
    CanonicalBody,
    CanonicalBodyConfig,
    read_canonical_body,
    write_canonical_body,
)
from case_editor.case_project import CaseProject, REPO_ROOT
from geometry.unstructure_surface.modeling import make_ellipse_2d, make_rectangle_2d
from geometry.unstructure_surface.surface import write_surface
from mesh.io import MeshAxis, read_grid_axis, write_grid_axis


def _make_case(tmp_path: Path, surface_body_count: int = 1, canonical_body_count: int = 1) -> CaseProject:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    shutil.copy2(REPO_ROOT / "example" / "run_case_2D" / "input.dat", case_dir / "input.dat")

    bodies = [make_ellipse_2d(n=8)]
    if surface_body_count > 1:
        bodies.append(make_rectangle_2d())
    write_surface(case_dir / "unstruc_surface_in.dat", bodies[:surface_body_count])

    canonical_bodies = [CanonicalBody(motion_type=0, zone_max=1, nodes=1, elems=1)]
    if canonical_body_count > 1:
        canonical_bodies.append(CanonicalBody(motion_type=0, zone_max=1, nodes=1, elems=1))
    write_canonical_body(
        case_dir / "canonical_body_in.dat",
        CanonicalBodyConfig(
            bodies=canonical_bodies[:canonical_body_count],
            nbody_solid=canonical_body_count,
        ),
    )

    write_grid_axis(case_dir / "xgrid.dat", MeshAxis("x", np.array([0.0, 1.0, 2.0])))
    write_grid_axis(case_dir / "ygrid.dat", MeshAxis("y", np.array([0.0, 0.5, 1.5])))
    return CaseProject(case_dir)


def _write_fort(path: Path, node_count: int, dt: float = 0.01) -> None:
    with path.open("wb") as stream:
        stream.write(struct.pack("<iddii", 20, dt, 0.0, node_count, 20))
        for _ in range(node_count):
            stream.write(struct.pack("<i3di", 24, 0.0, 0.0, 0.0, 24))


def test_control_sync_updates_provable_fields_and_becomes_clean(tmp_path: Path) -> None:
    case = _make_case(tmp_path)

    plan = case.sync_control_files(dry_run=True)
    fields = {change.field for change in plan.changes}
    assert not plan.has_errors
    assert fields == {
        "domain.grid_counts",
        "domain.x_grid",
        "domain.y_grid",
        "body[1].counts",
    }

    applied = case.sync_control_files()
    assert not applied.has_errors
    assert {path.name for path in applied.written_files} == {"input.dat", "canonical_body_in.dat"}

    editor = case.input_editor()
    assert tuple(map(int, editor.get_values_after("nx")[:3])) == (3, 3, 3)
    assert tuple(map(float, editor.get_values_after("xgrid_unif")[:2])) == (1.0, 2.0)
    assert tuple(map(float, editor.get_values_after("ygrid_unif")[:2])) == (2.0, 1.5)
    assert tuple(map(float, editor.get_values_after("zgrid_unif")[:2])) == (1.0, 0.03)

    canonical = read_canonical_body(case.canonical_path)
    assert (canonical.bodies[0].nodes, canonical.bodies[0].elems) == (8, 0)
    assert case.plan_control_sync().changes == []


def test_missing_canonical_body_records_are_appended(tmp_path: Path) -> None:
    case = _make_case(tmp_path, surface_body_count=2, canonical_body_count=1)

    plan = case.sync_control_files(dry_run=True)

    assert not plan.has_errors
    assert any(change.field == "canonical.header_counts" for change in plan.changes)
    assert any(change.field == "body[2].record" for change in plan.changes)

    applied = case.sync_control_files()

    assert not applied.has_errors
    canonical = read_canonical_body(case.canonical_path)
    assert canonical.nbody == 2
    assert canonical.nbody_solid == 2
    assert len(canonical.bodies) == 2
    assert (canonical.bodies[1].nodes, canonical.bodies[1].elems) == (
        case.scan_data().surface_bodies[1].node_count,
        case.scan_data().surface_bodies[1].element_count,
    )
    assert canonical.bodies[1].motion_type == canonical.bodies[0].motion_type
    assert canonical.bodies[1].zone_max == canonical.bodies[0].zone_max


def test_incomplete_canonical_header_records_are_repaired(tmp_path: Path) -> None:
    case = _make_case(tmp_path, surface_body_count=2, canonical_body_count=1)
    lines = case.canonical_path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("1   1   0", "2   2   0", 1)
    case.canonical_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    plan = case.sync_control_files(dry_run=True)

    assert not plan.has_errors
    assert any("incomplete" in issue.message for issue in plan.issues)
    assert any(change.field == "body[2].record" for change in plan.changes)

    applied = case.sync_control_files()

    assert not applied.has_errors
    canonical = read_canonical_body(case.canonical_path)
    assert canonical.nbody == 2
    assert len(canonical.bodies) == 2


def test_canonical_reader_ignores_trailing_example_blocks(tmp_path: Path) -> None:
    case = _make_case(tmp_path, surface_body_count=2, canonical_body_count=1)
    lines = case.canonical_path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("1   1   0", "2   2   0", 1)
    lines.extend(
        [
            "",
            "",
            "example for FBI wings",
            "_" * 124,
            "14      1",
            "2393    4608                    ! nPtsBodyMarker, totNumTriElem",
        ]
    )
    case.canonical_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    try:
        read_canonical_body(case.canonical_path)
    except ValueError as exc:
        assert "Expected 2 body records, found 1" in str(exc)
    else:
        raise AssertionError("Incomplete canonical should not parse as complete")


def test_incomplete_canonical_with_fort_for_missing_record_does_not_crash(tmp_path: Path) -> None:
    case = _make_case(tmp_path, surface_body_count=2, canonical_body_count=1)
    lines = case.canonical_path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("1   1   0", "2   2   0", 1)
    case.canonical_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    second_body = case.scan_data().surface_bodies[1]
    _write_fort(case.case_dir / "fort.42", node_count=second_body.node_count)

    plan = case.sync_control_files(dry_run=True)

    assert not plan.has_errors
    assert any(change.field == "body[2].record" for change in plan.changes)


def test_extra_canonical_body_records_still_block_writes(tmp_path: Path) -> None:
    case = _make_case(tmp_path, surface_body_count=1, canonical_body_count=2)
    original_input = case.input_path.read_text(encoding="utf-8")
    original_canonical = case.canonical_path.read_text(encoding="utf-8")

    plan = case.sync_control_files()

    assert plan.has_errors
    assert any("Surface has 1 bodies" in issue.message for issue in plan.issues)
    assert plan.written_files == []
    assert case.input_path.read_text(encoding="utf-8") == original_input
    assert case.canonical_path.read_text(encoding="utf-8") == original_canonical


def test_fort_node_mismatch_is_validate_only_and_blocks_writes(tmp_path: Path) -> None:
    case = _make_case(tmp_path)
    canonical = CanonicalBodyConfig(
        bodies=[CanonicalBody(motion_type=3, zone_max=1, nodes=8, elems=0)],
        nbody_solid=1,
    )
    write_canonical_body(case.canonical_path, canonical)
    _write_fort(case.case_dir / "fort.41", node_count=7)
    original_input = case.input_path.read_text(encoding="utf-8")

    plan = case.sync_control_files()

    assert plan.has_errors
    assert any("fort.41 has 7 nodes" in issue.message for issue in plan.issues)
    assert plan.written_files == []
    assert case.input_path.read_text(encoding="utf-8") == original_input


def test_single_row_indexed_grid_reads_one_coordinate(tmp_path: Path) -> None:
    path = tmp_path / "zgrid.dat"
    write_grid_axis(path, MeshAxis("z", np.array([0.0])))

    axis = read_grid_axis(path, "z")

    assert axis.count == 1
    assert np.allclose(axis.values, [0.0])
