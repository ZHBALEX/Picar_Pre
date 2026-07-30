from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from case_editor.canonical_body_editor import CanonicalBody
from case_editor.canonical_body_editor import read_canonical_body
from case_editor.data_facts import CaseFacts, GridAxisFacts
from case_editor.input_editor import InputDatEditor

from .base import ControlProfile, SyncChange, SyncIssue, SyncPlan


class PicarCurrentProfile(ControlProfile):
    """Control-file mapping for the input/canonical format used by this repository."""

    name = "picar-current"

    def plan(self, case_dir: str | Path, facts: CaseFacts) -> SyncPlan:
        case_dir = Path(case_dir).resolve()
        plan = SyncPlan(case_dir=case_dir, profile=self.name, facts=facts)
        plan.issues.extend(SyncIssue(issue.severity, issue.message) for issue in facts.issues)

        input_path = case_dir / "input.dat"
        editor = None
        if input_path.exists():
            try:
                editor = InputDatEditor.load(input_path)
                self._plan_input(plan, editor)
            except Exception as exc:
                plan.issues.append(SyncIssue("error", f"Cannot inspect input.dat: {exc}"))
        else:
            plan.issues.append(SyncIssue("error", f"Missing control file: {input_path}"))

        canonical = None
        canonical_path = case_dir / "canonical_body_in.dat"
        if canonical_path.exists():
            try:
                canonical = read_canonical_body(canonical_path)
                self._plan_canonical(plan, canonical)
            except Exception as exc:
                try:
                    canonical = _read_canonical_partial(canonical_path)
                    self._plan_canonical(plan, canonical)
                    plan.issues.append(
                        SyncIssue(
                            "warning",
                            f"canonical_body_in.dat is incomplete ({exc}); Setup Sync can append missing body records.",
                        )
                    )
                except Exception as partial_exc:
                    plan.issues.append(SyncIssue("error", f"Cannot inspect canonical_body_in.dat: {partial_exc}"))
        elif facts.surface_present:
            plan.issues.append(
                SyncIssue(
                    "error",
                    "Surface data exists but canonical_body_in.dat is missing; body type and motion intent cannot be inferred safely.",
                )
            )

        self._plan_motion_checks(plan, editor, canonical)
        return plan

    def apply(self, plan: SyncPlan) -> list[Path]:
        if plan.profile != self.name:
            raise ValueError(f"Plan profile {plan.profile!r} does not match {self.name!r}")
        if plan.has_errors:
            raise ValueError("Setup sync is blocked by errors; inspect the sync plan before writing")

        input_changes = [change for change in plan.changes if change.control_file == "input.dat"]
        canonical_changes = [change for change in plan.changes if change.control_file == "canonical_body_in.dat"]
        pending: dict[Path, str] = {}

        if input_changes:
            input_path = plan.case_dir / "input.dat"
            editor = InputDatEditor.load(input_path)
            for change in input_changes:
                if change.field == "domain.grid_counts":
                    editor.set_grid_counts(*change.desired)
                elif change.field == "domain.x_grid":
                    editor.set_values_after("xgrid_unif", change.desired)
                elif change.field == "domain.y_grid":
                    editor.set_values_after("ygrid_unif", change.desired)
                elif change.field == "domain.z_grid":
                    editor.set_values_after("zgrid_unif", change.desired)
                elif change.field == "internal_boundary.present":
                    values = editor.get_values_after("internal_boundary_present")
                    values[0] = change.desired
                    editor.set_values_after("internal_boundary_present", values)
                else:
                    raise ValueError(f"Unsupported input sync field: {change.field}")
            pending[input_path] = "\n".join(editor.lines) + "\n"

        if canonical_changes:
            canonical_path = plan.case_dir / "canonical_body_in.dat"
            lines = canonical_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            blocks = _canonical_record_blocks(lines)
            for change in canonical_changes:
                if change.field == "canonical.header_counts":
                    nbody, nbody_solid, nbody_membrane = change.desired
                    lines[0] = _replace_header_counts(lines[0], nbody, nbody_solid, nbody_membrane)
                    continue
                body_id = int(change.field.split("[", 1)[1].split("]", 1)[0])
                if change.field.endswith(".record"):
                    motion_type, zone_max, nodes, elements = change.desired
                    insert_at = blocks[-1].count_line + 1 if blocks else _canonical_insert_index(lines)
                    new_lines = [
                        _canonical_separator(lines, blocks),
                        _format_motion_values(motion_type, zone_max),
                        _format_count_values(nodes, elements),
                    ]
                    lines[insert_at:insert_at] = new_lines
                    blocks = _canonical_record_blocks(lines)
                    continue
                if body_id > len(blocks):
                    raise ValueError(f"Cannot locate canonical body {body_id} count record")
                nodes, elements = change.desired
                count_line = blocks[body_id - 1].count_line
                lines[count_line] = _replace_count_values(
                    lines[count_line], nodes, elements
                )
            pending[canonical_path] = "\n".join(lines) + "\n"

        written = _atomic_write_many(pending)
        plan.written_files[:] = written
        return written

    def _plan_input(self, plan: SyncPlan, editor: InputDatEditor) -> None:
        facts = plan.facts
        current_counts = tuple(int(float(value)) for value in editor.get_values_after("nx")[:3])
        desired_counts = list(current_counts)
        for index, axis_name in enumerate("xyz"):
            axis = facts.grids.get(axis_name)
            if axis is not None:
                desired_counts[index] = axis.count
        desired_counts_tuple = tuple(desired_counts)
        self._add_change(
            plan,
            "input.dat",
            "domain.grid_counts",
            current_counts,
            desired_counts_tuple,
            "x/y/zgrid.dat node counts",
        )

        for axis_name in "xyz":
            axis = facts.grids.get(axis_name)
            if axis is None:
                continue
            marker = f"{axis_name}grid_unif"
            current_values = editor.get_values_after(marker)
            current = (int(float(current_values[0])), float(current_values[1]))
            desired = (_grid_flag(axis), axis.maximum)
            self._add_change(
                plan,
                "input.dat",
                f"domain.{axis_name}_grid",
                current,
                desired,
                f"{axis_name}grid.dat spacing and range",
            )
            if not np.isclose(axis.minimum, 0.0, rtol=0.0, atol=1e-12):
                plan.issues.append(
                    SyncIssue(
                        "warning",
                        f"{axis_name}grid.dat starts at {axis.minimum:.16g}; current input format exposes only {axis_name}out.",
                    )
                )

        if facts.surface_present:
            current_values = editor.get_values_after("internal_boundary_present")
            current_present = int(float(current_values[0]))
            desired_present = 1 if facts.surface_bodies else 0
            self._add_change(
                plan,
                "input.dat",
                "internal_boundary.present",
                current_present,
                desired_present,
                "unstruc_surface_in.dat body presence",
            )

    def _plan_canonical(self, plan: SyncPlan, canonical: Any) -> None:
        facts = plan.facts
        if not facts.surface_present:
            return
        surface_count = len(facts.surface_bodies)
        record_count = len(canonical.bodies)
        if record_count > surface_count:
            plan.issues.append(
                SyncIssue(
                    "error",
                    f"Surface has {surface_count} bodies but canonical has {record_count} body records; "
                    "removing canonical body records is not automatic.",
                )
            )
            return

        for body_fact, body_control in zip(facts.surface_bodies, canonical.bodies):
            self._add_change(
                plan,
                "canonical_body_in.dat",
                f"body[{body_fact.body_id}].counts",
                (body_control.nodes, body_control.elems),
                (body_fact.node_count, body_fact.element_count),
                f"unstruc_surface_in.dat body {body_fact.body_id}",
            )

        header_current = (int(canonical.nbody), int(canonical.nbody_solid), int(canonical.nbody_membrane))
        desired_membrane = int(canonical.nbody_membrane)
        desired_solid = max(0, surface_count - desired_membrane)
        header_desired = (surface_count, desired_solid, desired_membrane)
        self._add_change(
            plan,
            "canonical_body_in.dat",
            "canonical.header_counts",
            header_current,
            header_desired,
            "unstruc_surface_in.dat body count",
        )

        if record_count < surface_count:
            if not canonical.bodies:
                plan.issues.append(
                    SyncIssue(
                        "error",
                        "canonical_body_in.dat has no body records to copy motion_type and zoneMax from.",
                    )
                )
                return
            template = canonical.bodies[-1]
            for body_fact in facts.surface_bodies[record_count:]:
                self._add_change(
                    plan,
                    "canonical_body_in.dat",
                    f"body[{body_fact.body_id}].record",
                    "<missing>",
                    (template.motion_type, template.zone_max, body_fact.node_count, body_fact.element_count),
                    f"copy canonical body {record_count} motion/zone; counts from surface body {body_fact.body_id}",
                )
            plan.issues.append(
                SyncIssue(
                    "warning",
                    f"canonical_body_in.dat has {record_count} body records; Setup Sync will append bodies "
                    f"{record_count + 1}..{surface_count} using body {record_count} motion_type/zoneMax.",
                )
            )

    def _plan_motion_checks(self, plan: SyncPlan, editor: InputDatEditor | None, canonical: Any) -> None:
        facts = plan.facts
        surface_by_id = {body.body_id: body for body in facts.surface_bodies}
        fort_by_id = {fort.body_id: fort for fort in facts.fort_files}

        input_dt = None
        if editor is not None:
            try:
                input_dt = float(editor.get_values_after("re,")[1])
            except (IndexError, TypeError, ValueError):
                pass

        for fort in facts.fort_files:
            surface = surface_by_id.get(fort.body_id)
            if surface is None:
                plan.issues.append(
                    SyncIssue("error", f"{fort.path.name} maps to body {fort.body_id}, which is absent from the surface file.")
                )
                continue
            if fort.node_count != surface.node_count:
                plan.issues.append(
                    SyncIssue(
                        "error",
                        f"{fort.path.name} has {fort.node_count} nodes but surface body {fort.body_id} has {surface.node_count}.",
                    )
                )
            if canonical is not None and fort.body_id <= len(canonical.bodies):
                motion_type = canonical.bodies[fort.body_id - 1].motion_type
                if motion_type != 3:
                    plan.issues.append(
                        SyncIssue(
                            "warning",
                            f"{fort.path.name} exists but canonical body {fort.body_id} motion_type is {motion_type}, not prescribed (3).",
                        )
                    )
            if input_dt is not None and not np.isclose(fort.dt, input_dt, rtol=1e-9, atol=1e-15):
                plan.issues.append(
                    SyncIssue(
                        "warning",
                        f"{fort.path.name} dt={fort.dt:.16g} differs from input.dat dt={input_dt:.16g}; dt is validate-only.",
                    )
                )

        if canonical is not None:
            for body_id, body in enumerate(canonical.bodies, start=1):
                if body.motion_type == 3 and body_id not in fort_by_id:
                    plan.issues.append(
                        SyncIssue("warning", f"Canonical body {body_id} is prescribed motion but no mapped fort file was found.")
                    )

    @staticmethod
    def _add_change(
        plan: SyncPlan,
        control_file: str,
        field: str,
        current: Any,
        desired: Any,
        source: str,
    ) -> None:
        if _values_equal(current, desired):
            return
        plan.changes.append(
            SyncChange(
                control_file=control_file,
                field=field,
                current=current,
                desired=desired,
                source=source,
            )
        )


def _grid_flag(axis: GridAxisFacts) -> int:
    return 1 if axis.uniform and np.isclose(axis.minimum, 0.0, rtol=0.0, atol=1e-12) else 2


def _values_equal(current: Any, desired: Any) -> bool:
    if isinstance(current, (tuple, list)) and isinstance(desired, (tuple, list)):
        return len(current) == len(desired) and all(_values_equal(a, b) for a, b in zip(current, desired))
    if isinstance(current, (int, float)) and isinstance(desired, (int, float)):
        return bool(np.isclose(current, desired, rtol=1e-12, atol=1e-14))
    return current == desired


@dataclass(frozen=True)
class _CanonicalBlock:
    separator_line: int
    motion_line: int
    count_line: int


@dataclass
class _PartialCanonical:
    bodies: list[CanonicalBody]
    nbody_header: int
    nbody_solid: int
    nbody_membrane: int
    nsection: int

    @property
    def nbody(self) -> int:
        return self.nbody_header


def _read_canonical_partial(path: str | Path) -> _PartialCanonical:
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    if len(lines) < 3:
        raise ValueError(f"Invalid canonical body file: {path}")
    header = lines[0].split()
    if len(header) < 4:
        raise ValueError(f"Invalid canonical body header: {path}")
    blocks = _canonical_record_blocks(lines)
    bodies: list[CanonicalBody] = []
    for block in blocks:
        motion = lines[block.motion_line].split()
        counts = lines[block.count_line].split()
        bodies.append(
            CanonicalBody(
                motion_type=int(float(motion[0])),
                zone_max=int(float(motion[1])),
                nodes=int(float(counts[0])),
                elems=int(float(counts[1])),
            )
        )
    return _PartialCanonical(
        bodies=bodies,
        nbody_header=int(float(header[0])),
        nbody_solid=int(float(header[1])),
        nbody_membrane=int(float(header[2])),
        nsection=int(float(header[3])),
    )


def _canonical_record_blocks(lines: list[str]) -> list[_CanonicalBlock]:
    blocks: list[_CanonicalBlock] = []
    index = 3
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            if blocks:
                break
            index += 1
            continue
        if not stripped.startswith("_"):
            if blocks:
                break
            index += 1
            continue
        if index + 2 >= len(lines):
            break
        if not (_line_starts_with_numbers(lines[index + 1], 2) and _line_starts_with_numbers(lines[index + 2], 2)):
            break
        blocks.append(_CanonicalBlock(index, index + 1, index + 2))
        index += 3
    return blocks


def _line_starts_with_numbers(line: str, count: int) -> bool:
    tokens = line.split("!", 1)[0].split()
    if len(tokens) < count:
        return False
    try:
        for token in tokens[:count]:
            float(token.replace("D", "E").replace("d", "e"))
    except ValueError:
        return False
    return True


def _canonical_insert_index(lines: list[str]) -> int:
    index = 3
    while index < len(lines) and lines[index].strip():
        index += 1
    return index


def _canonical_separator(lines: list[str], blocks: list[_CanonicalBlock]) -> str:
    if blocks:
        return lines[blocks[-1].separator_line]
    return "_" * 124


def _replace_header_counts(line: str, nbody: int, nbody_solid: int, nbody_membrane: int) -> str:
    comment_index = line.find("!")
    comment = line[comment_index:].rstrip() if comment_index >= 0 else ""
    content = line[:comment_index] if comment_index >= 0 else line
    tokens = content.split()
    if len(tokens) < 4:
        raise ValueError("Cannot update canonical header counts")
    tokens[0] = str(int(nbody))
    tokens[1] = str(int(nbody_solid))
    tokens[2] = str(int(nbody_membrane))
    prefix = "   ".join(tokens)
    return f"{prefix}       {comment}".rstrip()


def _format_motion_values(motion_type: int, zone_max: int) -> str:
    return f"{int(motion_type):<9d} {int(zone_max):<9d}              ! motion_type, zoneMax"


def _format_count_values(nodes: int, elements: int) -> str:
    return f"{int(nodes):<9d} {int(elements):<9d}              ! nPtsBodyMarker, totNumTriElem"


def _replace_count_values(line: str, nodes: int, elements: int) -> str:
    comment_index = line.find("!")
    comment = line[comment_index:].rstrip() if comment_index >= 0 else ""
    prefix = f"{int(nodes):<9d} {int(elements):<9d}"
    return f"{prefix}              {comment}".rstrip()


def _atomic_write_many(contents: dict[Path, str]) -> list[Path]:
    if not contents:
        return []
    temporary: dict[Path, Path] = {}
    try:
        for path, text in contents.items():
            temp = path.with_name(f".{path.name}.picar-sync.tmp")
            temp.write_text(text, encoding="utf-8")
            temporary[path] = temp
        for path, temp in temporary.items():
            os.replace(temp, path)
    finally:
        for temp in temporary.values():
            if temp.exists():
                temp.unlink()
    return list(contents)
