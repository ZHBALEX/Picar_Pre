from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from case_editor.case_project import CaseProject  # noqa: E402
from case_editor.probe import read_probe_payload  # noqa: E402
from geometry.unstructure_surface.project import SurfaceProject  # noqa: E402
from geometry.unstructure_surface.surface import read_surface, summarize_surface, validate_surface, write_surface  # noqa: E402
from mesh.generation import generate_mesh  # noqa: E402
from mesh.io import format_mesh_input, read_mesh, read_mesh_input, summarize_mesh, validate_mesh, write_mesh, write_mesh_input  # noqa: E402
from motion.fort import fort_motion_info  # noqa: E402
from motion.visualize import motion_points_for_frames  # noqa: E402


STATIC_DIR = Path(__file__).resolve().parent / "console"
CONSOLE_API_VERSION = "setup26"
DENSE_UNIFORM_RATIO = 1.05
DEFAULT_MESH_INPUT_NAME = "mesh_input_twolayers.dat"
MESH_INPUT_CANDIDATES = (
    "mesh_input_twolayers.dat",
    "input_mesh_twolayers.dat",
    "mesh_input.dat",
    "input.dat",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the local Picar preprocessing console.")
    parser.add_argument("case", nargs="?", type=Path, help="Initial case directory. Defaults to example/run_case.")
    parser.add_argument("--case-dir", type=Path, default=None, help="Initial case directory. Overrides the positional case path.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Default: 127.0.0.1.")
    parser.add_argument("--port", type=int, default=8765, help="Preferred bind port. If busy, the console uses the next free port. Default: 8765.")
    parser.add_argument("--strict-port", action="store_true", help="Fail instead of auto-selecting another port when --port is busy.")
    return parser.parse_args()


def make_handler(default_case_dir: Path):
    class PicarConsoleHandler(BaseHTTPRequestHandler):
        server_version = "PicarConsole/1.0"

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                self._handle_api(parsed.path, parse_qs(parsed.query))
                return
            self._serve_static(parsed.path)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if not parsed.path.startswith("/api/"):
                self.send_error(404, "Unknown route")
                return
            try:
                payload = self._read_json_body()
                result = _handle_post_api(parsed.path, payload, default_case_dir)
                self._send_json(result)
            except Exception as exc:  # pragma: no cover - terminal server guard
                self._send_json({"ok": False, "error": str(exc)}, status=400)

        def log_message(self, fmt: str, *args) -> None:
            return None

        def _handle_api(self, path: str, query: dict[str, list[str]]) -> None:
            try:
                if path == "/api/health":
                    self._send_json({
                        "app": "Picar Console",
                        "ok": True,
                        "api_version": CONSOLE_API_VERSION,
                        "origin_shift": True,
                        "geometry_transform": True,
                        "fort_preview": True,
                        "fort_remove": True,
                        "control_sync": True,
                        "input_sync": True,
                        "setup_sync": True,
                    })
                elif path == "/api/report":
                    self._send_json(_case_report(_case_dir_from_query(query, default_case_dir)))
                elif path == "/api/mesh-input":
                    case_dir = _case_dir_from_query(query, default_case_dir)
                    self._send_json(_mesh_input_payload(case_dir))
                elif path == "/api/amr":
                    case_dir = _case_dir_from_query(query, default_case_dir)
                    self._send_json(_amr_payload(case_dir))
                elif path == "/api/probes":
                    case_dir = _case_dir_from_query(query, default_case_dir)
                    self._send_json(_probe_payload(case_dir))
                elif path == "/api/fort/report":
                    case_dir = _case_dir_from_query(query, default_case_dir)
                    self._send_json(_fort_report(case_dir))
                elif path == "/api/surface":
                    case_dir = _case_dir_from_query(query, default_case_dir)
                    self._send_file_text(case_dir / "unstruc_surface_in.dat")
                elif path == "/api/grid":
                    case_dir = _case_dir_from_query(query, default_case_dir)
                    axis = query.get("axis", ["x"])[0].lower()
                    if axis not in {"x", "y", "z"}:
                        raise ValueError("axis must be x, y, or z")
                    self._send_file_text(case_dir / f"{axis}grid.dat")
                else:
                    self.send_error(404, "Unknown API route")
            except Exception as exc:  # pragma: no cover - terminal server guard
                self._send_json({"error": str(exc)}, status=400)

        def _serve_static(self, request_path: str) -> None:
            rel = unquote(request_path).lstrip("/") or "index.html"
            target = (STATIC_DIR / rel).resolve()
            if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.exists() or target.is_dir():
                self.send_error(404, "Not found")
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _read_json_body(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))

        def _send_file_text(self, path: Path) -> None:
            if not path.exists():
                raise FileNotFoundError(f"Missing file: {path}")
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

    return PicarConsoleHandler


def _handle_post_api(path: str, payload: dict[str, object], default_case_dir: Path) -> dict[str, object]:
    case_dir = _payload_case_dir(payload, default_case_dir)
    if path == "/api/mesh/preview":
        params = _payload_mesh_params(payload)
        mesh = generate_mesh(params, repair_degenerate=True)
        _shift_mesh(mesh, _payload_mesh_origin(payload))
        return {"ok": True, "mesh": _mesh_payload(mesh), "input_text": format_mesh_input(params)}
    if path == "/api/mesh/save":
        params = _payload_mesh_params(payload)
        out = write_mesh_input(case_dir / str(payload.get("input_name") or DEFAULT_MESH_INPUT_NAME), params)
        return {"ok": True, "path": str(out), "input_text": format_mesh_input(params)}
    if path == "/api/mesh/generate":
        params = _payload_mesh_params(payload)
        out = write_mesh_input(case_dir / str(payload.get("input_name") or DEFAULT_MESH_INPUT_NAME), params)
        mesh = generate_mesh(params)
        _shift_mesh(mesh, _payload_mesh_origin(payload))
        write_mesh(case_dir, mesh, include_index=True)
        return {"ok": True, "input_path": str(out), "mesh": _mesh_payload(mesh), "report": _case_report(case_dir)}
    if path == "/api/amr/save":
        amr = payload.get("amr")
        if not isinstance(amr, dict):
            raise ValueError("Missing AMR payload")
        case_dir.mkdir(parents=True, exist_ok=True)
        out = case_dir / "amr_in.dat"
        out.write_text(_format_amr_payload(amr), encoding="utf-8")
        return {"ok": True, "path": str(out), "amr": _amr_payload(case_dir)}
    if path in {"/api/setup-sync/plan", "/api/input-sync/plan", "/api/control-sync/plan"}:
        return _setup_sync_payload(case_dir, payload, apply=False)
    if path in {"/api/setup-sync/apply", "/api/input-sync/apply", "/api/control-sync/apply"}:
        return _setup_sync_payload(case_dir, payload, apply=True)
    if path == "/api/geometry/save-surface":
        content = str(payload.get("content") or "")
        out = case_dir / str(payload.get("surface_name") or "unstruc_surface_in.dat")
        out.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(out), "report": _case_report(case_dir)}
    if path == "/api/geometry/import-stl":
        filename = Path(str(payload.get("filename") or "uploaded.stl")).name
        data_b64 = str(payload.get("content_base64") or "")
        if not data_b64:
            raise ValueError("Missing STL content")
        case_dir.mkdir(parents=True, exist_ok=True)
        stl_path = case_dir / filename
        stl_path.write_bytes(base64.b64decode(data_b64))
        project = SurfaceProject(case_dir)
        out, bodies = project.convert_stl([stl_path], append=bool(payload.get("append")))
        return {"ok": True, "stl_path": str(stl_path), "surface_path": str(out), "bodies": len(bodies), "report": _case_report(case_dir)}
    if path == "/api/geometry/export-stl":
        output = str(payload.get("output") or "surface_export.stl")
        out, bodies = SurfaceProject(case_dir).export_stl(output=output, body_ids=_payload_body_ids(payload))
        return {"ok": True, "path": str(out), "bodies": len(bodies)}
    if path == "/api/geometry/transform":
        body_ids = _payload_body_ids(payload)
        translate = _payload_vec3(payload, "translate")
        rotation = _payload_vec3(payload, "rotation")
        scale = payload.get("scale", 1.0)
        out, bodies = SurfaceProject(case_dir).transform(
            body_ids=body_ids,
            translate=translate,
            rotation=rotation,
            scale=float(scale),
        )
        return {"ok": True, "path": str(out), "bodies": _json_ready(summarize_surface(bodies)), "report": _case_report(case_dir)}
    if path == "/api/geometry/remove-bodies":
        body_ids = set(_payload_body_ids(payload) or [])
        if not body_ids:
            raise ValueError("Select at least one body to remove")
        project = SurfaceProject(case_dir)
        bodies = project.load(required=True)
        kept = [body for idx, body in enumerate(bodies, start=1) if idx not in body_ids]
        write_surface(project.surface_path, kept)
        return {"ok": True, "path": str(project.surface_path), "bodies": _json_ready(summarize_surface(kept)), "report": _case_report(case_dir)}
    if path == "/api/fort/preview":
        return _fort_preview_payload(case_dir, payload)
    if path == "/api/fort/remove":
        return _remove_fort_payload(case_dir, payload)
    raise ValueError(f"Unknown API route: {path}")


def _case_dir_from_query(query: dict[str, list[str]], default_case_dir: Path) -> Path:
    raw = query.get("case_dir", [str(default_case_dir)])[0]
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _payload_case_dir(payload: dict[str, object], default_case_dir: Path) -> Path:
    raw = str(payload.get("case_dir") or default_case_dir)
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _payload_mesh_params(payload: dict[str, object]) -> dict[str, object]:
    params = payload.get("params")
    if not isinstance(params, dict):
        raise ValueError("Missing mesh params")
    return params


def _payload_mesh_origin(payload: dict[str, object]) -> dict[str, float]:
    origin = payload.get("origin")
    if not isinstance(origin, dict):
        return {"x": 0.0, "y": 0.0, "z": 0.0}
    return {
        "x": float(origin.get("x") or 0.0),
        "y": float(origin.get("y") or 0.0),
        "z": float(origin.get("z") or 0.0),
    }


def _shift_mesh(mesh, origin: dict[str, float]) -> None:
    if origin["x"]:
        mesh.x.values = mesh.x.values + origin["x"]
    if origin["y"]:
        mesh.y.values = mesh.y.values + origin["y"]
    if mesh.z is not None and origin["z"]:
        mesh.z.values = mesh.z.values + origin["z"]


def _payload_body_ids(payload: dict[str, object]) -> list[int] | None:
    raw = payload.get("body_ids")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ValueError("body_ids must be a list")
    return [int(item) for item in raw]


def _payload_vec3(payload: dict[str, object], key: str):
    raw = payload.get(key)
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != 3:
        raise ValueError(f"{key} must be a 3-value list")
    return tuple(float(item) for item in raw)


def _case_report(case_dir: Path) -> dict[str, object]:
    project = CaseProject(case_dir)
    try:
        validation = project.validate()
    except Exception as exc:
        validation = [str(exc)]
    payload: dict[str, object] = {
        "case_dir": str(case_dir),
        "validation": validation,
        "surface": None,
        "mesh": None,
        "amr": None,
        "probes": None,
    }

    surface_bodies = []
    surface_path = case_dir / "unstruc_surface_in.dat"
    if surface_path.exists():
        surface_bodies = read_surface(surface_path)
        payload["surface"] = {
            "path": str(surface_path),
            "bodies": _json_ready(summarize_surface(surface_bodies)),
            "errors": validate_surface(surface_bodies),
        }

    if (case_dir / "xgrid.dat").exists() and (case_dir / "ygrid.dat").exists():
        mesh = read_mesh(case_dir, require_z=False)
        payload["mesh"] = {
            "path": str(case_dir),
            "axes": _json_ready(summarize_mesh(mesh)),
            "dense_box": _mesh_dense_box(case_dir),
            "errors": validate_mesh(mesh),
        }

    amr_path = case_dir / "amr_in.dat"
    if amr_path.exists():
        try:
            payload["amr"] = _amr_payload(case_dir)
        except Exception as exc:
            payload["amr"] = {"ok": False, "path": str(amr_path), "error": str(exc), "layers": [], "block_count": 0}

    probe_path = case_dir / "probe_in.dat"
    if probe_path.exists():
        try:
            probe_payload = read_probe_payload(probe_path, surface_bodies)
            payload["probes"] = {
                "exists": True,
                "ok": probe_payload.get("ok", False),
                "path": str(probe_path),
                "marker_count": probe_payload.get("marker_count", 0),
                "fluid_count": probe_payload.get("fluid_count", 0),
                "plotted_marker_count": probe_payload.get("plotted_marker_count", 0),
                "unmatched_marker_count": probe_payload.get("unmatched_marker_count", 0),
                "errors": probe_payload.get("errors", []),
            }
        except Exception as exc:
            payload["probes"] = {"exists": True, "ok": False, "path": str(probe_path), "error": str(exc)}

    payload["fort"] = _fort_report(case_dir)
    return payload


def _probe_payload(case_dir: Path) -> dict[str, object]:
    surface_path = case_dir / "unstruc_surface_in.dat"
    bodies = read_surface(surface_path) if surface_path.exists() else []
    return read_probe_payload(case_dir / "probe_in.dat", bodies)


def _amr_payload(case_dir: Path) -> dict[str, object]:
    path = case_dir / "amr_in.dat"
    if not path.exists():
        return {"ok": False, "path": str(path), "layers": [], "block_count": 0, "error": "Missing amr_in.dat"}
    payload = _parse_amr_text(path.read_text(encoding="utf-8", errors="replace"))
    payload["ok"] = True
    payload["path"] = str(path)
    payload["block_count"] = sum(len(layer["blocks"]) for layer in payload["layers"])
    return payload


def _setup_sync_payload(case_dir: Path, payload: dict[str, object], apply: bool) -> dict[str, object]:
    profile = str(payload.get("profile") or "picar-current")
    fort_start = int(payload.get("fort_start") or 41)
    project = CaseProject(case_dir)
    plan = project.sync_control_files(profile=profile, fort_start=fort_start, dry_run=not apply)
    return {
        "ok": True,
        "applied": bool(apply and not plan.has_errors),
        "blocked": plan.has_errors,
        "plan": _sync_plan_payload(plan),
        "report": plan.format_report(),
    }


def _sync_plan_payload(plan) -> dict[str, object]:
    return {
        "case_dir": str(plan.case_dir),
        "profile": plan.profile,
        "changes": [
            {
                "control_file": change.control_file,
                "field": change.field,
                "current": _json_ready(change.current),
                "desired": _json_ready(change.desired),
                "source": change.source,
                "mode": change.mode,
            }
            for change in plan.changes
        ],
        "issues": [
            {
                "severity": issue.severity,
                "message": issue.message,
            }
            for issue in plan.issues
        ],
        "written_files": [str(path) for path in plan.written_files],
        "has_errors": plan.has_errors,
    }


def _parse_amr_text(text: str) -> dict[str, object]:
    lines = text.splitlines()
    resize = 0
    layers: list[dict[str, object]] = []
    current_layer: dict[str, object] | None = None
    expected_blocks: int | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        numbers = _amr_numbers(line)
        if "AMR_RESIZE" in line and numbers:
            resize = int(numbers[0])
            continue
        if "AMR Layer" in line:
            layer_number = int(numbers[-1]) if numbers else len(layers) + 1
            current_layer = {"layer": layer_number, "blocks": []}
            layers.append(current_layer)
            expected_blocks = None
            continue
        if current_layer is None:
            continue
        if expected_blocks is None and len(numbers) == 1:
            expected_blocks = int(numbers[0])
            continue
        if len(numbers) < 9:
            continue
        block = {
            "id": int(numbers[0]),
            "parent": int(numbers[1]),
            "start": [float(numbers[2]), float(numbers[3]), float(numbers[4])],
            "end": [float(numbers[5]), float(numbers[6]), float(numbers[7])],
            "moving": int(numbers[8]),
        }
        current_layer["blocks"].append(block)
        if expected_blocks is not None and len(current_layer["blocks"]) >= expected_blocks:
            expected_blocks = None

    return {"resize": resize, "layers": layers}


def _amr_numbers(text: str) -> list[float]:
    import re

    return [float(item.replace("D", "E").replace("d", "e")) for item in re.findall(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eEdD][+-]?\d+)?", text)]


def _format_amr_payload(payload: dict[str, object]) -> str:
    resize = int(payload.get("resize") or 0)
    raw_layers = payload.get("layers") or []
    if not isinstance(raw_layers, list):
        raise ValueError("AMR layers must be a list")
    lines = [
        f"{resize}               AMR_RESIZE (0 do not resize, 1 use the closest multigrid-able size, 2 use a larger multigrid-able size)",
        "",
        "Block ID | Parent Block\t| Point_start \tPoint_end|AMR_moving",
    ]
    for layer_index, raw_layer in enumerate(raw_layers, start=1):
        if not isinstance(raw_layer, dict):
            raise ValueError("Each AMR layer must be an object")
        layer_number = int(raw_layer.get("layer") or layer_index)
        raw_blocks = raw_layer.get("blocks") or []
        if not isinstance(raw_blocks, list):
            raise ValueError("AMR layer blocks must be a list")
        lines.append(f"======================== AMR Layer {layer_number} ===========================================")
        lines.append(str(len(raw_blocks)))
        for raw_block in raw_blocks:
            if not isinstance(raw_block, dict):
                raise ValueError("Each AMR block must be an object")
            start = raw_block.get("start")
            end = raw_block.get("end")
            if not isinstance(start, list) or not isinstance(end, list) or len(start) != 3 or len(end) != 3:
                raise ValueError("AMR block start/end must be 3-value lists")
            block_id = int(raw_block.get("id") or 0)
            parent = int(raw_block.get("parent") or 0)
            moving = int(raw_block.get("moving") or 0)
            values = [float(item) for item in start + end]
            lines.append(
                f"{block_id}\t{parent}\t"
                f"{_format_amr_number(values[0])} {_format_amr_number(values[1])} {_format_amr_number(values[2])}\t\t"
                f"{_format_amr_number(values[3])} {_format_amr_number(values[4])} {_format_amr_number(values[5])}\t\t"
                f"{moving}"
            )
    return "\n".join(lines) + "\n"


def _format_amr_number(value: float) -> str:
    return f"{float(value):.10g}"


def _fort_report(case_dir: Path, fort_start: int = 41) -> dict[str, object]:
    surface_bodies = read_surface(case_dir / "unstruc_surface_in.dat") if (case_dir / "unstruc_surface_in.dat").exists() else []
    files = []
    for path in sorted(case_dir.glob("fort.*")):
        suffix = path.name.split(".", 1)[1]
        if not suffix.isdigit():
            continue
        body_id = int(suffix) - int(fort_start) + 1
        if body_id <= 0:
            continue
        surface_nodes = surface_bodies[body_id - 1].node_count if body_id <= len(surface_bodies) else None
        item: dict[str, object] = {
            "body": body_id,
            "path": str(path),
            "name": path.name,
            "surface_nodes": surface_nodes,
            "ok": False,
        }
        try:
            info = fort_motion_info(path)
            item.update({
                "ok": True,
                "nodes": info.node_count,
                "frames": info.frame_count,
                "dt": info.dt,
                "first_time": info.first_time,
                "last_time": info.last_time,
                "node_match": surface_nodes is None or surface_nodes == info.node_count,
            })
        except Exception as exc:
            item["error"] = str(exc)
        files.append(item)
    return {
        "ok": True,
        "fort_start": fort_start,
        "body_count": len(surface_bodies),
        "files": files,
    }


def _fort_preview_payload(case_dir: Path, payload: dict[str, object]) -> dict[str, object]:
    body_id = int(payload.get("body_id") or 1)
    frame = int(payload.get("frame") if payload.get("frame") is not None else -1)
    samples = max(1, min(int(payload.get("samples") or 24), 96))
    component_order = str(payload.get("component_order") or "xyz")
    motion_mode = str(payload.get("motion_mode") or "velocity")

    bodies = read_surface(case_dir / "unstruc_surface_in.dat")
    if body_id < 1 or body_id > len(bodies):
        raise ValueError(f"body_id must be in 1..{len(bodies)}, got {body_id}")
    body = bodies[body_id - 1]
    fort_path = case_dir / f"fort.{41 + body_id - 1}"
    if not fort_path.exists():
        raise FileNotFoundError(f"Motion file not found for body {body_id}: {fort_path}")

    info = fort_motion_info(fort_path)
    if info.node_count != body.node_count:
        raise ValueError(f"fort node count {info.node_count} does not match body {body_id} surface nodes {body.node_count}")
    if frame < 0:
        frame = info.frame_count + frame
    if frame < 0 or frame >= info.frame_count:
        raise ValueError(f"frame must be in [-{info.frame_count}, {info.frame_count - 1}], got {payload.get('frame')}")

    frame_indices = _fort_preview_frame_indices(info.frame_count, samples, frame)
    point_frames, times = motion_points_for_frames(
        body,
        fort_path,
        frame_indices,
        component_order=component_order,
        motion_mode=motion_mode,
    )
    frames = [
        {
            "frame": frame_index,
            "time": times[frame_index],
            "highlight": frame_index == frame,
            "points": _json_ready(point_frames[frame_index].reshape(-1)),
        }
        for frame_index in frame_indices
    ]
    return {
        "ok": True,
        "body_id": body_id,
        "node_count": body.node_count,
        "frame": frame,
        "frames": frames,
        "info": {
            "nodes": info.node_count,
            "frames": info.frame_count,
            "dt": info.dt,
            "first_time": info.first_time,
            "last_time": info.last_time,
        },
    }


def _remove_fort_payload(case_dir: Path, payload: dict[str, object]) -> dict[str, object]:
    body_ids = _payload_body_ids(payload) or []
    if not body_ids:
        raise ValueError("Select at least one fort file to remove")
    fort_start = int(payload.get("fort_start") or 41)
    remove_body_ids = sorted(set(body_ids))
    removed: list[dict[str, object]] = []
    missing: list[dict[str, object]] = []
    moved: list[dict[str, object]] = []
    fort_files = _indexed_fort_files(case_dir, fort_start)

    for body_id in remove_body_ids:
        if body_id <= 0:
            raise ValueError(f"body_id must be positive, got {body_id}")
        fort_number = fort_start + body_id - 1
        path = case_dir / f"fort.{fort_number}"
        item = {"body": body_id, "name": path.name, "path": str(path)}
        if path.exists():
            if not path.is_file():
                raise ValueError(f"Not a file: {path}")
            path.unlink()
            removed.append(item)
        else:
            missing.append(item)

    for item in fort_files:
        old_body_id = item["body"]
        old_path = item["path"]
        if old_body_id in remove_body_ids or not old_path.exists():
            continue
        shift = sum(1 for removed_body_id in remove_body_ids if removed_body_id < old_body_id)
        if shift <= 0:
            continue
        new_body_id = old_body_id - shift
        new_path = case_dir / f"fort.{fort_start + new_body_id - 1}"
        if new_path.exists():
            raise FileExistsError(f"Cannot shift {old_path.name} to {new_path.name}; target already exists")
        old_path.replace(new_path)
        moved.append(
            {
                "from_body": old_body_id,
                "to_body": new_body_id,
                "from_name": old_path.name,
                "to_name": new_path.name,
                "from_path": str(old_path),
                "to_path": str(new_path),
            }
        )

    return {"ok": True, "removed": removed, "missing": missing, "moved": moved, "report": _case_report(case_dir)}


def _indexed_fort_files(case_dir: Path, fort_start: int) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
    for path in sorted(case_dir.glob("fort.*")):
        suffix = path.name.split(".", 1)[1]
        if not suffix.isdigit() or not path.is_file():
            continue
        fort_number = int(suffix)
        body_id = fort_number - fort_start + 1
        if body_id <= 0:
            continue
        files.append({"body": body_id, "fort_number": fort_number, "path": path})
    return sorted(files, key=lambda item: int(item["body"]))


def _fort_preview_frame_indices(frame_count: int, samples: int, highlight_frame: int) -> list[int]:
    if frame_count <= 0:
        return []
    samples = max(1, min(int(samples), int(frame_count)))
    indices = np.linspace(0, frame_count - 1, samples, dtype=int).tolist()
    if highlight_frame not in indices:
        nearest = min(range(len(indices)), key=lambda idx: abs(indices[idx] - highlight_frame))
        indices[nearest] = int(highlight_frame)
    return sorted(set(indices))


def _mesh_input_payload(case_dir: Path) -> dict[str, object]:
    input_path = case_dir / DEFAULT_MESH_INPUT_NAME
    if (case_dir / "xgrid.dat").exists() and (case_dir / "ygrid.dat").exists():
        mesh = read_mesh(case_dir, require_z=False)
        params = _params_from_existing_mesh(mesh)
        return {"ok": True, "path": str(input_path), "params": _json_ready(params), "source": "inferred-grid"}
    for candidate in _mesh_input_paths(case_dir):
        if not candidate.exists():
            continue
        try:
            params = read_mesh_input(candidate)
            return {"ok": True, "path": str(candidate), "params": _json_ready(params), "source": candidate.name}
        except Exception:
            continue
    return {"ok": False, "path": str(input_path), "params": _json_ready(_default_mesh_params()), "source": "default"}


def _mesh_payload(mesh) -> dict[str, object]:
    return {
        "x": mesh.x.values.tolist(),
        "y": mesh.y.values.tolist(),
        "z": mesh.z.values.tolist() if mesh.z is not None else [],
        "summary": _json_ready(summarize_mesh(mesh)),
    }


def _params_from_existing_mesh(mesh) -> dict[str, object]:
    x0, x1 = float(mesh.x.values[0]), float(mesh.x.values[-1])
    y0, y1 = float(mesh.y.values[0]), float(mesh.y.values[-1])
    if mesh.z is not None and mesh.z.count > 1:
        z0, z1 = float(mesh.z.values[0]), float(mesh.z.values[-1])
    else:
        z0, z1 = 0.0, 0.0
    x_axis = _axis_params_from_grid(mesh.x.values)
    y_axis = _axis_params_from_grid(mesh.y.values)
    z_axis = _axis_params_from_grid(mesh.z.values) if mesh.z is not None and mesh.z.count > 1 else None
    params = _default_mesh_params()
    params.update(
        {
            "Lx": x1 - x0,
            "Ly": y1 - y0,
            "Lz": max(0.0, z1 - z0),
            "x_center_dense": x_axis["center"],
            "y_center_dense": y_axis["center"],
            "z_center_dense": z_axis["center"] if z_axis is not None else 0.0,
            "Lx_dense": x_axis["dense_length"],
            "Ly_dense": y_axis["dense_length"],
            "Lz_dense": z_axis["dense_length"] if z_axis is not None else 0.0,
            "Nx_dense": x_axis["dense_count"],
            "Ny_dense": y_axis["dense_count"],
            "Nz_dense": z_axis["dense_count"] if z_axis is not None else 0,
            "n_left_stretch": x_axis["left_stretch"],
            "n_left_uniform": 0,
            "n_right_uniform": 0,
            "n_right_stretch": x_axis["right_stretch"],
            "n_bottom_stretch": y_axis["left_stretch"],
            "n_bottom_uniform": 0,
            "n_top_uniform": 0,
            "n_top_stretch": y_axis["right_stretch"],
            "n_front_stretch": z_axis["left_stretch"] if z_axis is not None else 0,
            "n_front_uniform": 0,
            "n_back_uniform": 0,
            "n_back_stretch": z_axis["right_stretch"] if z_axis is not None else 0,
            "len_left": 0.0,
            "len_right": 0.0,
            "len_bottom": 0.0,
            "len_top": 0.0,
            "len_front": 0.0,
            "len_back": 0.0,
        }
    )
    return params


def _axis_params_from_grid(values) -> dict[str, float | int]:
    start = float(values[0])
    end = float(values[-1])
    spacing: list[float] = []
    for i in range(len(values) - 1):
        delta = float(values[i + 1] - values[i])
        if delta > 0.0:
            spacing.append(delta)
    if not spacing:
        return {"center": 0.0, "dense_length": 0.0, "dense_count": 0, "left_stretch": 0, "right_stretch": 0}

    min_spacing = min(spacing)
    max_spacing = max(spacing)
    if max_spacing / min_spacing <= DENSE_UNIFORM_RATIO:
        return {
            "center": 0.5 * (end - start),
            "dense_length": max(0.0, end - start),
            "dense_count": len(spacing),
            "left_stretch": 0,
            "right_stretch": 0,
        }

    threshold = min_spacing + max(abs(min_spacing) * 1e-6, 1e-12)
    best_start = 0
    best_end = 0
    run_start = -1
    for i, delta in enumerate(spacing):
        is_dense = delta <= threshold
        if is_dense and run_start < 0:
            run_start = i
        if (not is_dense or i == len(spacing) - 1) and run_start >= 0:
            run_end = i if is_dense and i == len(spacing) - 1 else i - 1
            if run_end - run_start > best_end - best_start:
                best_start = run_start
                best_end = run_end
            run_start = -1

    dense_start = float(values[best_start])
    dense_end = float(values[min(best_end + 1, len(values) - 1)])
    return {
        "center": 0.5 * (dense_start + dense_end) - start,
        "dense_length": max(0.0, dense_end - dense_start),
        "dense_count": max(1, best_end - best_start + 1),
        "left_stretch": best_start,
        "right_stretch": max(0, len(spacing) - best_end - 1),
    }


def _default_mesh_params() -> dict[str, object]:
    return {
        "scale_ref": 1.0,
        "Lx": 24.0,
        "Ly": 20.0,
        "Lz": 0.0,
        "x_center_dense": 12.0,
        "y_center_dense": 10.0,
        "z_center_dense": 0.0,
        "Lx_dense": 8.0,
        "Ly_dense": 6.0,
        "Lz_dense": 0.0,
        "Nx_dense": 64,
        "Ny_dense": 48,
        "Nz_dense": 0,
        "len_left": 1.0,
        "len_right": 1.0,
        "len_bottom": 1.0,
        "len_top": 1.0,
        "len_front": 0.0,
        "len_back": 0.0,
        "n_left_stretch": 16,
        "n_left_uniform": 8,
        "n_right_uniform": 8,
        "n_right_stretch": 16,
        "n_bottom_stretch": 16,
        "n_bottom_uniform": 8,
        "n_top_uniform": 8,
        "n_top_stretch": 16,
        "n_front_stretch": 0,
        "n_front_uniform": 0,
        "n_back_uniform": 0,
        "n_back_stretch": 0,
        "r_left": 1.08,
        "r_right": 1.08,
        "r_bottom": 1.06,
        "r_top": 1.06,
        "r_front": 1.0,
        "r_back": 1.0,
        "relax": 0.001,
        "flag_plot": False,
        "flag_preplot": False,
    }


def _mesh_dense_box(case_dir: Path) -> dict[str, float] | None:
    mesh = None
    if (case_dir / "xgrid.dat").exists() and (case_dir / "ygrid.dat").exists():
        try:
            mesh = read_mesh(case_dir, require_z=False)
            params = _params_from_existing_mesh(mesh)
        except Exception:
            params = None
    else:
        params = None
    if params is None:
        for input_path in _mesh_input_paths(case_dir):
            if not input_path.exists():
                continue
            try:
                params = read_mesh_input(input_path)
                break
            except Exception:
                continue
    if params is None:
        return None
    x_start = float(mesh.x.values[0]) if mesh is not None else 0.0
    y_start = float(mesh.y.values[0]) if mesh is not None else 0.0
    z_start = float(mesh.z.values[0]) if mesh is not None and mesh.z is not None and mesh.z.count > 1 else 0.0
    x0 = x_start + float(params["x_center_dense"]) - 0.5 * float(params["Lx_dense"])
    x1 = x_start + float(params["x_center_dense"]) + 0.5 * float(params["Lx_dense"])
    y0 = y_start + float(params["y_center_dense"]) - 0.5 * float(params["Ly_dense"])
    y1 = y_start + float(params["y_center_dense"]) + 0.5 * float(params["Ly_dense"])
    if "z_center_dense" in params and float(params.get("Lz_dense", 0.0)) > 0.0:
        z0 = z_start + float(params["z_center_dense"]) - 0.5 * float(params["Lz_dense"])
        z1 = z_start + float(params["z_center_dense"]) + 0.5 * float(params["Lz_dense"])
    else:
        z0 = 0.0
        z1 = 0.0
    return {"x0": x0, "x1": x1, "y0": y0, "y1": y1, "z0": z0, "z1": z1}


def _mesh_input_paths(case_dir: Path) -> list[Path]:
    return [case_dir / name for name in MESH_INPUT_CANDIDATES]


def _json_ready(value):
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def main() -> None:
    args = parse_args()
    case_dir = (args.case_dir or args.case or (REPO_ROOT / "example" / "run_case")).resolve()
    handler = make_handler(case_dir)
    port = args.port if args.strict_port else _first_free_port(args.host, args.port)
    server = ThreadingHTTPServer((args.host, port), handler)
    url = f"http://{args.host}:{port}/"
    print("Picar Console")
    print("=============")
    print(f"Case dir : {case_dir}")
    if port != args.port:
        print(f"Port     : {args.port} was busy; using {port}")
    print(f"URL      : {url}")
    print("Note     : Open this exact URL. If 8765 shows a directory listing, it is another server.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


def _first_free_port(host: str, preferred: int, attempts: int = 50) -> int:
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex((host, port)) != 0:
                return port
    raise OSError(f"No free port found from {preferred} to {preferred + attempts - 1}")


if __name__ == "__main__":
    main()
