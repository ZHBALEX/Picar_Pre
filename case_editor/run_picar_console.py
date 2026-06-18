from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from case_editor.case_project import CaseProject  # noqa: E402
from geometry.unstructure_surface.surface import read_surface, summarize_surface, validate_surface  # noqa: E402
from mesh.io import read_mesh, read_mesh_input, summarize_mesh, validate_mesh  # noqa: E402


STATIC_DIR = Path(__file__).resolve().parent / "console"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the local Picar preprocessing console.")
    parser.add_argument("--case-dir", type=Path, default=REPO_ROOT / "example" / "run_case", help="Initial case directory.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Default: 127.0.0.1.")
    parser.add_argument("--port", type=int, default=8765, help="Bind port. Default: 8765.")
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

        def log_message(self, fmt: str, *args) -> None:
            return None

        def _handle_api(self, path: str, query: dict[str, list[str]]) -> None:
            try:
                if path == "/api/health":
                    self._send_json({"app": "Picar Console", "ok": True})
                elif path == "/api/report":
                    self._send_json(_case_report(_case_dir_from_query(query, default_case_dir)))
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
            self.end_headers()
            self.wfile.write(data)

        def _send_file_text(self, path: Path) -> None:
            if not path.exists():
                raise FileNotFoundError(f"Missing file: {path}")
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return PicarConsoleHandler


def _case_dir_from_query(query: dict[str, list[str]], default_case_dir: Path) -> Path:
    raw = query.get("case_dir", [str(default_case_dir)])[0]
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


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
    case_dir = args.case_dir.resolve()
    handler = make_handler(case_dir)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/"
    print("Picar Console")
    print("=============")
    print(f"Case dir : {case_dir}")
    print(f"URL      : {url}")
    print("Note     : If this URL shows a directory listing, another server is using that browser tab/port; stop it or choose another --port.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
