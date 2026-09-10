from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from geometry.unstructure_surface.surface import (
    DEFAULT_CASE_SURFACE,
    SurfaceBody,
    read_surface,
    surface_area,
    write_surface,
)

from .analysis import (
    analyze_centerline_motion,
    analyze_centroid_motion,
    format_centerline_report,
    format_centroid_report,
    write_centerline_csv,
    write_centroid_equation_csv,
    write_centroid_kinematics_csv,
    write_midline_kinematics_csv,
)
from .fort import FortMotionInfo, fort_motion_info, format_motion_info, rotate_fort_motion
from .fort import read_frame
from .visualize import plot_midline_motion, plot_motion_2d, plot_motion_3d


DEFAULT_FORT_START = 41


@dataclass(frozen=True)
class UndeformedBodyStats:
    """Diagnostics for one cycle-averaged undeformed body export."""

    body_id: int
    fort_path: Path
    nodes: int
    frames: int
    first_time: float
    last_time: float
    max_cycle_drift: float
    mean_cycle_drift: float
    max_surface_offset: float
    mean_surface_offset: float


@dataclass
class MotionProject:
    """Target-directory context for prescribed fort.* motion files."""

    case_dir: Path
    surface_name: str = "unstruc_surface_in.dat"
    fort_start: int = DEFAULT_FORT_START

    def __init__(
        self,
        case_dir: str | Path | None = None,
        surface_name: str = "unstruc_surface_in.dat",
        fort_start: int = DEFAULT_FORT_START,
    ):
        if case_dir is None:
            case_dir = DEFAULT_CASE_SURFACE.parent
        self.case_dir = Path(case_dir).resolve()
        self.surface_name = surface_name
        self.fort_start = int(fort_start)

    @property
    def surface_path(self) -> Path:
        return self.case_dir / self.surface_name

    def fort_path_for_body(self, body_id: int) -> Path:
        return self.case_dir / f"fort.{self.fort_start + int(body_id) - 1}"

    def fort_files(self, body_ids: list[int] | None = None) -> list[tuple[int, Path]]:
        if body_ids:
            return [(body_id, self.fort_path_for_body(body_id)) for body_id in body_ids]

        paths = []
        for path in sorted(self.case_dir.glob("fort.*")):
            suffix = path.name.split(".", 1)[1]
            if suffix.isdigit():
                body_id = int(suffix) - self.fort_start + 1
                if body_id > 0:
                    paths.append((body_id, path))
        return paths

    def inspect(self, body_ids: list[int] | None = None, validate_surface_counts: bool = True) -> str:
        lines = [
            "Motion Project",
            "==============",
            f"Case dir : {self.case_dir}",
            "",
            "Motion Files",
            "============",
        ]

        infos = []
        for body_id, path in self.fort_files(body_ids):
            if not path.exists():
                lines.extend([f"Body {body_id}", "-" * (5 + len(str(body_id))), f"Missing : {path}", ""])
                continue
            info = fort_motion_info(path)
            infos.append((body_id, info))
            lines.extend([f"Body {body_id}", "-" * (5 + len(str(body_id))), format_motion_info(info), ""])

        if validate_surface_counts and self.surface_path.exists():
            lines.extend(["Surface Count Check", "==================="])
            bodies = read_surface(self.surface_path)
            for body_id, info in infos:
                expected = bodies[body_id - 1].node_count if body_id <= len(bodies) else None
                status = "PASS" if expected == info.node_count else "FAIL"
                lines.append(f"Body {body_id}: fort nodes={info.node_count}, surface nodes={expected} [{status}]")

        return "\n".join(lines).rstrip()

    def rotate(
        self,
        rotation: tuple[float, float, float],
        body_ids: list[int] | None = None,
        output_dir: str | Path | None = None,
        suffix: str = "_rotated",
        component_order: str = "xyz",
    ) -> list[tuple[int, Path, FortMotionInfo]]:
        output_base = self.case_dir if output_dir is None else Path(output_dir)
        if not output_base.is_absolute():
            output_base = self.case_dir / output_base

        results = []
        for body_id, input_path in self.fort_files(body_ids):
            if not input_path.exists():
                raise FileNotFoundError(f"Motion file not found for body {body_id}: {input_path}")
            output_path = output_base / f"{input_path.name}{suffix}"
            info = rotate_fort_motion(input_path, output_path, rotation=rotation, component_order=component_order)
            results.append((body_id, output_path, info))
        return results

    def export_undeformed_surface(
        self,
        *,
        body_ids: list[int] | None = None,
        output: str | Path = "unstruc_surface_undeformed.dat",
        component_order: str = "xyz",
        motion_mode: str = "velocity",
    ) -> tuple[Path, list[SurfaceBody], list[UndeformedBodyStats]]:
        """Export a surface whose selected bodies are averaged over one fort period.

        For velocity-mode fort files, positions are recovered by integrating the
        stored marker velocities from the current surface through the full file.
        The undeformed coordinates are the per-node cycle average of those
        recovered positions. Topology, body order, node ids, and unselected
        bodies are preserved.
        """
        out = Path(output)
        if not out.is_absolute():
            out = self.case_dir / out
        if out.resolve() == self.surface_path.resolve():
            raise ValueError("undeformed output must be different from the input surface file")

        bodies = read_surface(self.surface_path)
        target_ids = self._target_body_ids(body_ids, len(bodies))
        exported: list[SurfaceBody] = []
        stats: list[UndeformedBodyStats] = []

        for body_id, body in enumerate(bodies, start=1):
            if body_id not in target_ids:
                exported.append(body)
                continue
            fort_path = self.fort_path_for_body(body_id)
            if not fort_path.exists():
                raise FileNotFoundError(f"Motion file not found for body {body_id}: {fort_path}")
            points, body_stats = self._cycle_average_body_points(
                body_id,
                body,
                fort_path,
                component_order=component_order,
                motion_mode=motion_mode,
            )
            nodes = body.nodes.copy()
            nodes[:, 1:4] = points
            exported.append(SurfaceBody(nodes=nodes, elems=body.elems.copy(), bbox=body.bbox))
            stats.append(body_stats)

        out.parent.mkdir(parents=True, exist_ok=True)
        write_surface(out, exported)
        return out, exported, stats

    def cycle_average_group_center(
        self,
        body_ids: list[int],
        *,
        component_order: str = "xyz",
        motion_mode: str = "velocity",
    ) -> tuple[np.ndarray, list[UndeformedBodyStats]]:
        """Return the node-weighted center of selected bodies over their fort cycle."""
        bodies = read_surface(self.surface_path)
        target_ids = sorted(self._target_body_ids(body_ids, len(bodies)))
        point_sum = np.zeros(3, dtype=float)
        point_count = 0
        stats: list[UndeformedBodyStats] = []
        for body_id in target_ids:
            body = bodies[body_id - 1]
            average, body_stats = self._cycle_average_body_points(
                body_id,
                body,
                self.fort_path_for_body(body_id),
                component_order=component_order,
                motion_mode=motion_mode,
            )
            point_sum += average.sum(axis=0)
            point_count += body.node_count
            stats.append(body_stats)
        if point_count <= 0:
            raise ValueError("Cannot compute a motion center for an empty body group")
        return point_sum / float(point_count), stats

    def geometry_metrics(
        self,
        body_ids: list[int] | None = None,
        *,
        front_axis: str = "x",
        front_side: str = "min",
        component_order: str = "xyz",
        motion_mode: str = "velocity",
    ) -> dict[str, object]:
        """Return reference and full-fort spatial metrics for selected bodies.

        Front nodes are selected once from the reference geometry at the global
        extreme of ``front_axis``. Their cycle-average position therefore tracks
        the same material point(s) throughout the fort motion.
        """
        bodies = read_surface(self.surface_path)
        if not bodies:
            raise ValueError(f"No surface bodies found in {self.surface_path}")

        if body_ids:
            target_ids = sorted({int(body_id) for body_id in body_ids})
        else:
            target_ids = list(range(1, len(bodies) + 1))
        for body_id in target_ids:
            if body_id < 1 or body_id > len(bodies):
                raise ValueError(f"body_id must be in 1..{len(bodies)}, got {body_id}")

        axis_names = {"x": 0, "y": 1, "z": 2}
        axis_name = str(front_axis).lower()
        if axis_name not in axis_names:
            raise ValueError("front_axis must be 'x', 'y', or 'z'")
        side = str(front_side).lower()
        if side not in {"min", "max"}:
            raise ValueError("front_side must be 'min' or 'max'")
        if motion_mode not in {"velocity", "relative", "displacement"}:
            raise ValueError("motion_mode must be 'velocity', 'relative', or 'displacement'")

        selected = [(body_id, bodies[body_id - 1]) for body_id in target_ids]
        xyz_min = np.minimum.reduce([body.points.min(axis=0) for _, body in selected])
        xyz_max = np.maximum.reduce([body.points.max(axis=0) for _, body in selected])
        node_count = sum(body.node_count for _, body in selected)
        point_center = sum((body.points.sum(axis=0) for _, body in selected), np.zeros(3)) / float(node_count)

        axis = axis_names[axis_name]
        front_value = xyz_min[axis] if side == "min" else xyz_max[axis]
        front_tolerance = max(1.0e-12, float(xyz_max[axis] - xyz_min[axis]) * 1.0e-9)
        front_masks: dict[int, np.ndarray] = {}
        for body_id, body in selected:
            front_masks[body_id] = np.isclose(body.points[:, axis], front_value, rtol=0.0, atol=front_tolerance)
        front_node_count = sum(int(mask.sum()) for mask in front_masks.values())
        front_point_sum = sum(
            (body.points[front_masks[body_id]].sum(axis=0) for body_id, body in selected if front_masks[body_id].any()),
            np.zeros(3),
        )

        result: dict[str, object] = {
            "body_ids": target_ids,
            "node_count": node_count,
            "reference": {
                "min": xyz_min,
                "max": xyz_max,
                "span": xyz_max - xyz_min,
                "point_center": point_center,
                "box_center": 0.5 * (xyz_min + xyz_max),
                "front_axis": axis_name,
                "front_side": side,
                "front_value": float(front_value),
                "front_node_count": front_node_count,
                "front_point_center": front_point_sum / float(front_node_count),
                "surface_area": sum(surface_area(body) for _, body in selected),
            },
            "motion": None,
            "issues": [],
        }

        infos: dict[int, FortMotionInfo] = {}
        issues: list[str] = []
        for body_id, body in selected:
            fort_path = self.fort_path_for_body(body_id)
            if not fort_path.exists():
                issues.append(f"Body {body_id}: missing {fort_path.name}")
                continue
            try:
                info = fort_motion_info(fort_path)
            except Exception as exc:
                issues.append(f"Body {body_id}: {fort_path.name} is invalid ({exc})")
                continue
            if info.node_count != body.node_count:
                issues.append(
                    f"Body {body_id}: {fort_path.name} has {info.node_count} nodes; surface has {body.node_count}"
                )
                continue
            infos[body_id] = info

        if issues:
            result["issues"] = issues
            return result

        motion_min = np.full(3, np.inf)
        motion_max = np.full(3, -np.inf)
        average_point_sum = np.zeros(3)
        average_front_sum = np.zeros(3)
        motion_bodies: list[dict[str, object]] = []
        for body_id, body in selected:
            body_metrics = self._body_geometry_metrics(
                body,
                self.fort_path_for_body(body_id),
                infos[body_id],
                front_masks[body_id],
                component_order=component_order,
                motion_mode=motion_mode,
            )
            motion_min = np.minimum(motion_min, body_metrics["min"])
            motion_max = np.maximum(motion_max, body_metrics["max"])
            average_point_sum += body_metrics["point_center"] * body.node_count
            average_front_sum += body_metrics["front_point_sum"]
            motion_bodies.append({
                "body": body_id,
                "frames": infos[body_id].frame_count,
                "min": body_metrics["min"],
                "max": body_metrics["max"],
                "box_center": 0.5 * (body_metrics["min"] + body_metrics["max"]),
                "point_center": body_metrics["point_center"],
            })

        result["motion"] = {
            "component_order": component_order,
            "motion_mode": motion_mode,
            "min": motion_min,
            "max": motion_max,
            "span": motion_max - motion_min,
            "box_center": 0.5 * (motion_min + motion_max),
            "point_center": average_point_sum / float(node_count),
            "front_point_center": average_front_sum / float(front_node_count),
            "bodies": motion_bodies,
        }
        return result

    def view(
        self,
        body_id: int,
        *,
        mode: str = "2d",
        frame: int = -1,
        samples: int = 24,
        plane: str = "xy",
        component_order: str = "xyz",
        motion_mode: str = "velocity",
        axis: str = "x",
        value_axis: str = "y",
        bins: int = 80,
        stride: int = 80,
        centerline_method: str = "bounds",
        normalize_station: bool = True,
        center_midline: bool = True,
        save_path: str | Path | None = None,
        show: bool = True,
    ):
        bodies = read_surface(self.surface_path)
        if body_id < 1 or body_id > len(bodies):
            raise ValueError(f"body_id must be in 1..{len(bodies)}, got {body_id}")

        body = bodies[body_id - 1]
        fort_path = self.fort_path_for_body(body_id)
        if not fort_path.exists():
            raise FileNotFoundError(f"Motion file not found for body {body_id}: {fort_path}")

        if mode == "2d":
            return plot_motion_2d(
                body,
                fort_path,
                frame=frame,
                samples=samples,
                plane=plane,
                component_order=component_order,
                motion_mode=motion_mode,
                save_path=save_path,
                show=show,
            )
        if mode == "3d":
            return plot_motion_3d(
                body,
                fort_path,
                frame=frame,
                samples=samples,
                component_order=component_order,
                motion_mode=motion_mode,
                save_path=save_path,
                show=show,
            )
        if mode == "midline":
            analysis = analyze_centerline_motion(
                body,
                fort_path,
                axis=axis,
                value_axes=(value_axis,),
                bins=bins,
                stride=stride,
                component_order=component_order,
                motion_mode=motion_mode,
                centerline_method=centerline_method,
            )
            return plot_midline_motion(
                analysis,
                station_axis=axis,
                value_axis=value_axis,
                normalize_station=normalize_station,
                center=center_midline,
                save_path=save_path,
                show=show,
            )
        raise ValueError("mode must be '2d', '3d', or 'midline'")

    def analyze_centroid(
        self,
        body_id: int,
        *,
        stride: int = 1,
        period: float = 1.0,
        component_order: str = "xyz",
        motion_mode: str = "velocity",
        centerline_method: str = "bounds",
        output: str | Path | None = None,
        kinematics_output: str | Path | None = None,
    ) -> str:
        bodies = read_surface(self.surface_path)
        body = self._body_by_id(bodies, body_id)
        analysis = analyze_centroid_motion(
            body,
            self.fort_path_for_body(body_id),
            stride=stride,
            period=period,
            component_order=component_order,
            motion_mode=motion_mode,
            centerline_method=centerline_method,
        )
        lines = [
            "Motion Analysis",
            "===============",
            f"Case dir : {self.case_dir}",
            f"Body     : {body_id}",
            f"Fort file: {self.fort_path_for_body(body_id)}",
        ]
        if output is not None:
            out = self._resolve_output_path(output)
            write_centroid_equation_csv(out, analysis)
            lines.append(f"Equation CSV  : {out}")
        if kinematics_output is not None:
            out = self._resolve_output_path(kinematics_output)
            write_centroid_kinematics_csv(out, analysis)
            lines.append(f"Kinematics CSV: {out}")
        lines.extend(["", format_centroid_report(analysis, period=period)])
        return "\n".join(lines)

    def analyze_centerline(
        self,
        body_id: int,
        *,
        axis: str = "x",
        value_axes: tuple[str, ...] = ("y", "z"),
        bins: int = 80,
        stride: int = 1,
        period: float = 1.0,
        component_order: str = "xyz",
        motion_mode: str = "velocity",
        output: str | Path | None = None,
        kinematics_output: str | Path | None = None,
    ) -> str:
        bodies = read_surface(self.surface_path)
        body = self._body_by_id(bodies, body_id)
        analysis = analyze_centerline_motion(
            body,
            self.fort_path_for_body(body_id),
            axis=axis,
            value_axes=value_axes,
            bins=bins,
            stride=stride,
            period=period,
            component_order=component_order,
            motion_mode=motion_mode,
        )

        lines = [
            "Motion Analysis",
            "===============",
            f"Case dir : {self.case_dir}",
            f"Body     : {body_id}",
            f"Fort file: {self.fort_path_for_body(body_id)}",
        ]
        if output is not None:
            out = self._resolve_output_path(output)
            write_centerline_csv(out, analysis, axis=axis)
            lines.append(f"Equation CSV  : {out}")
        if kinematics_output is not None:
            out = self._resolve_output_path(kinematics_output)
            write_midline_kinematics_csv(out, analysis, axis=axis)
            lines.append(f"Kinematics CSV: {out}")

        lines.extend(["", format_centerline_report(analysis, axis=axis, period=period)])
        return "\n".join(lines)

    def _body_by_id(self, bodies, body_id: int):
        if body_id < 1 or body_id > len(bodies):
            raise ValueError(f"body_id must be in 1..{len(bodies)}, got {body_id}")
        return bodies[body_id - 1]

    def _target_body_ids(self, body_ids: list[int] | None, body_count: int) -> set[int]:
        if body_ids:
            target_ids = {int(body_id) for body_id in body_ids}
        else:
            target_ids = {body_id for body_id, path in self.fort_files() if path.exists()}
        if not target_ids:
            raise FileNotFoundError(f"No fort.* files found in {self.case_dir}")
        for body_id in target_ids:
            if body_id < 1 or body_id > body_count:
                raise ValueError(f"body_id must be in 1..{body_count}, got {body_id}")
        return target_ids

    def _cycle_average_body_points(
        self,
        body_id: int,
        body: SurfaceBody,
        fort_path: Path,
        *,
        component_order: str,
        motion_mode: str,
    ) -> tuple[np.ndarray, UndeformedBodyStats]:
        info = fort_motion_info(fort_path)
        if info.node_count != body.node_count:
            raise ValueError(f"fort node count {info.node_count} does not match body {body_id} surface nodes {body.node_count}")

        if motion_mode == "velocity":
            average, cycle_drift = self._cycle_average_velocity(body, fort_path, component_order=component_order, info=info)
        elif motion_mode in {"displacement", "relative"}:
            average, cycle_drift = self._cycle_average_direct(body, fort_path, component_order=component_order, mode=motion_mode, info=info)
        else:
            raise ValueError("motion_mode must be 'velocity', 'relative', or 'displacement'")

        offset = average - body.points
        return average, UndeformedBodyStats(
            body_id=body_id,
            fort_path=fort_path,
            nodes=info.node_count,
            frames=info.frame_count,
            first_time=info.first_time,
            last_time=info.last_time,
            max_cycle_drift=float(np.linalg.norm(cycle_drift, axis=1).max()),
            mean_cycle_drift=float(np.linalg.norm(cycle_drift, axis=1).mean()),
            max_surface_offset=float(np.linalg.norm(offset, axis=1).max()),
            mean_surface_offset=float(np.linalg.norm(offset, axis=1).mean()),
        )

    def _body_geometry_metrics(
        self,
        body: SurfaceBody,
        fort_path: Path,
        info: FortMotionInfo,
        front_mask: np.ndarray,
        *,
        component_order: str,
        motion_mode: str,
    ) -> dict[str, np.ndarray]:
        points = body.points.copy()
        point_sum = np.zeros(3)
        front_sum = np.zeros(3)
        xyz_min = np.full(3, np.inf)
        xyz_max = np.full(3, -np.inf)
        center = body.points.mean(axis=0).reshape(1, 3)
        for frame_index in range(info.frame_count):
            header, motion = read_frame(
                fort_path,
                frame_index,
                node_count=body.node_count,
                component_order=component_order,
            )
            if motion_mode == "velocity":
                points = points + motion * header.dt
                deformed = points
            elif motion_mode == "relative":
                deformed = center + motion
            else:
                deformed = body.points + motion

            xyz_min = np.minimum(xyz_min, deformed.min(axis=0))
            xyz_max = np.maximum(xyz_max, deformed.max(axis=0))
            point_sum += deformed.sum(axis=0)
            if front_mask.any():
                front_sum += deformed[front_mask].sum(axis=0)

        return {
            "min": xyz_min,
            "max": xyz_max,
            "point_center": point_sum / float(info.frame_count * body.node_count),
            "front_point_sum": front_sum / float(info.frame_count),
        }

    def _cycle_average_velocity(
        self,
        body: SurfaceBody,
        fort_path: Path,
        *,
        component_order: str,
        info: FortMotionInfo,
    ) -> tuple[np.ndarray, np.ndarray]:
        points = body.points.copy()
        accumulated = np.zeros_like(points)
        for frame_index in range(info.frame_count):
            header, velocity = read_frame(fort_path, frame_index, node_count=body.node_count, component_order=component_order)
            points = points + velocity * header.dt
            accumulated += points
        return accumulated / float(info.frame_count), points - body.points

    def _cycle_average_direct(
        self,
        body: SurfaceBody,
        fort_path: Path,
        *,
        component_order: str,
        mode: str,
        info: FortMotionInfo,
    ) -> tuple[np.ndarray, np.ndarray]:
        accumulated = np.zeros_like(body.points)
        first_points: np.ndarray | None = None
        last_points: np.ndarray | None = None
        center = body.points.mean(axis=0).reshape(1, 3)
        for frame_index in range(info.frame_count):
            _header, motion = read_frame(fort_path, frame_index, node_count=body.node_count, component_order=component_order)
            if mode == "relative":
                points = center + motion
            else:
                points = body.points + motion
            if first_points is None:
                first_points = points.copy()
            last_points = points
            accumulated += points
        if first_points is None or last_points is None:
            raise ValueError(f"No frames found in {fort_path}")
        return accumulated / float(info.frame_count), last_points - first_points

    def _resolve_output_path(self, output: str | Path) -> Path:
        out = Path(output)
        return out if out.is_absolute() else self.case_dir / out
