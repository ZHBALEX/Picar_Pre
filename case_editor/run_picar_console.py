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


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from case_editor.case_project import CaseProject  # noqa: E402
from geometry.unstructure_surface.project import SurfaceProject  # noqa: E402
from geometry.unstructure_surface.surface import read_surface, summarize_surface, validate_surface  # noqa: E402
from mesh.generation import generate_mesh  # noqa: E402
from mesh.io import format_mesh_input, read_mesh, read_mesh_input, summarize_mesh, validate_mesh, write_mesh, write_mesh_input  # noqa: E402


STATIC_DIR = Path(__file__).resolve().parent / "console"


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
                    self._send_json({"app": "Picar Console", "ok": True})
                elif path == "/api/report":
                    self._send_json(_case_report(_case_dir_from_query(query, default_case_dir)))
                elif path == "/api/mesh-input":
                    case_dir = _case_dir_from_query(query, default_case_dir)
                    self._send_json(_mesh_input_payload(case_dir))
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
        return {"ok": True, "mesh": _mesh_payload(mesh), "input_text": format_mesh_input(params)}
    if path == "/api/mesh/save":
        params = _payload_mesh_params(payload)
        out = write_mesh_input(case_dir / str(payload.get("input_name") or "input.dat"), params)
        return {"ok": True, "path": str(out), "input_text": format_mesh_input(params)}
    if path == "/api/mesh/generate":
        params = _payload_mesh_params(payload)
        out = write_mesh_input(case_dir / str(payload.get("input_name") or "input.dat"), params)
        mesh = generate_mesh(params)
        write_mesh(case_dir, mesh, include_index=True)
        return {"ok": True, "input_path": str(out), "mesh": _mesh_payload(mesh), "report": _case_report(case_dir)}
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
        out, bodies = SurfaceProject(case_dir).export_stl(output=output)
        return {"ok": True, "path": str(out), "bodies": len(bodies)}
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
    }

    surface_path = case_dir / "unstruc_surface_in.dat"
    if surface_path.exists():
        bodies = read_surface(surface_path)
        payload["surface"] = {
            "path": str(surface_path),
            "bodies": _json_ready(summarize_surface(bodies)),
            "errors": validate_surface(bodies),
        }

    if (case_dir / "xgrid.dat").exists() and (case_dir / "ygrid.dat").exists():
        mesh = read_mesh(case_dir, require_z=False)
        payload["mesh"] = {
            "path": str(case_dir),
            "axes": _json_ready(summarize_mesh(mesh)),
            "dense_box": _mesh_dense_box(case_dir),
            "errors": validate_mesh(mesh),
        }

    return payload


def _mesh_input_payload(case_dir: Path) -> dict[str, object]:
    input_path = case_dir / "input.dat"
    if input_path.exists():
        try:
            params = read_mesh_input(input_path)
            return {"ok": True, "path": str(input_path), "params": _json_ready(params), "source": "input"}
        except Exception:
            pass
    if (case_dir / "xgrid.dat").exists() and (case_dir / "ygrid.dat").exists():
        mesh = read_mesh(case_dir, require_z=False)
        params = _params_from_existing_mesh(mesh)
        return {"ok": True, "path": str(input_path), "params": _json_ready(params), "source": "inferred-grid"}
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
    params = _default_mesh_params()
    params.update(
        {
            "Lx": x1 - x0,
            "Ly": y1 - y0,
            "Lz": max(0.0, z1 - z0),
            "x_center_dense": 0.5 * (x0 + x1),
            "y_center_dense": 0.5 * (y0 + y1),
            "z_center_dense": 0.5 * (z0 + z1),
            "Lx_dense": max((x1 - x0) * 0.4, 1e-6),
            "Ly_dense": max((y1 - y0) * 0.4, 1e-6),
            "Lz_dense": max((z1 - z0) * 0.4, 0.0),
            "Nx_dense": max(1, min(mesh.x.count - 1, max(8, (mesh.x.count - 1) // 2))),
            "Ny_dense": max(1, min(mesh.y.count - 1, max(8, (mesh.y.count - 1) // 2))),
            "Nz_dense": max(0, min((mesh.z.count - 1 if mesh.z is not None else 0), max(1, ((mesh.z.count - 1) // 2 if mesh.z is not None else 0)))),
        }
    )
    return params


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
    input_path = case_dir / "input.dat"
    if not input_path.exists():
        return None
    try:
        params = read_mesh_input(input_path)
    except Exception:
        return None
    x0 = float(params["x_center_dense"]) - 0.5 * float(params["Lx_dense"])
    x1 = float(params["x_center_dense"]) + 0.5 * float(params["Lx_dense"])
    y0 = float(params["y_center_dense"]) - 0.5 * float(params["Ly_dense"])
    y1 = float(params["y_center_dense"]) + 0.5 * float(params["Ly_dense"])
    if "z_center_dense" in params and float(params.get("Lz_dense", 0.0)) > 0.0:
        z0 = float(params["z_center_dense"]) - 0.5 * float(params["Lz_dense"])
        z1 = float(params["z_center_dense"]) + 0.5 * float(params["Lz_dense"])
    else:
        z0 = 0.0
        z1 = 0.0
    return {"x0": x0, "x1": x1, "y0": y0, "y1": y1, "z0": z0, "z1": z1}


def _json_ready(value):
    if hasattr(value, "tolist"):
        return value.tolist()
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
