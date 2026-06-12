from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from geometry.unstructure_surface.surface import DEFAULT_CASE_SURFACE, read_surface

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
from .visualize import plot_midline_motion, plot_motion_2d, plot_motion_3d


DEFAULT_FORT_START = 41


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

    def _resolve_output_path(self, output: str | Path) -> Path:
        out = Path(output)
        return out if out.is_absolute() else self.case_dir / out
