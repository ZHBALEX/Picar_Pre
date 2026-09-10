from __future__ import annotations

import argparse
import json
import mimetypes
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from case_editor.batch_case_setup import create_grouped_cases, flatten_amr_blocks, grouped_preview_payload, parse_body_groups
from case_editor.run_picar_console import _amr_payload, _mesh_dense_box, _mesh_payload
from geometry.unstructure_surface.surface import read_surface
from mesh.io import read_mesh

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = Path(__file__).resolve().parent / "batch_console"
BATCH_API_VERSION = "mesh-amr-v7"


def source_mesh(source: Path) -> dict[str, object] | None:
    mesh_payload = None
    if (source / "xgrid.dat").is_file() and (source / "ygrid.dat").is_file():
        mesh_payload = _mesh_payload(read_mesh(source, require_z=False))
        mesh_payload["dense_box"] = _mesh_dense_box(source)
    return mesh_payload


def source_amr(source: Path) -> dict[str, object] | None:
    return _amr_payload(source) if (source / "amr_in.dat").is_file() else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the isolated Picar batch-case setup workspace.")
    parser.add_argument("case", nargs="?", type=Path, help="Source case directory")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8775)
    parser.add_argument("--strict-port", action="store_true")
    return parser.parse_args()


def make_handler(default_case: Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args) -> None:
            return None

        def do_GET(self) -> None:  # noqa: N802
            request_path = urlparse(self.path).path
            if request_path == "/api/health":
                self._json({"ok": True, "app": "Picar Batch Case Setup", "api_version": BATCH_API_VERSION})
                return
            path = unquote(request_path).lstrip("/") or "index.html"
            if path == "shared/viewport_core.js":
                target = Path(__file__).resolve().parent / "console" / "viewport_core.js"
            else:
                target = (STATIC_DIR / path).resolve()
            allowed = target == (Path(__file__).resolve().parent / "console" / "viewport_core.js") or STATIC_DIR.resolve() in target.parents
            if not allowed or not target.is_file():
                self.send_error(404)
                return
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:  # noqa: N802
            try:
                size = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(size) or b"{}")
                self._json({"ok": True, **handle_api(urlparse(self.path).path, payload, default_case)})
            except Exception as exc:
                self._json({"ok": False, "error": str(exc)}, 400)

        def _json(self, value: dict[str, object], status: int = 200) -> None:
            data = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    return Handler


def handle_api(path: str, payload: dict[str, object], default_case: Path) -> dict[str, object]:
    source = Path(str(payload.get("source_case") or default_case)).expanduser().resolve()
    output = Path(str(payload.get("output_root") or source.parent / f"{source.name}_batch")).expanduser().resolve()
    bodies = read_surface(source / "unstruc_surface_in.dat")
    fort_start = int(payload.get("fort_start") or 41)
    component_order = str(payload.get("component_order") or "xyz").lower()
    amr = source_amr(source)
    mesh = source_mesh(source) if path in {"/api/source", "/api/preview"} else None
    amr_blocks = flatten_amr_blocks(amr)
    available_amr_ids = {int(block["id"]) for block in amr_blocks}
    moving_amr_ids = {int(block["id"]) for block in amr_blocks if int(block.get("moving") or 0) != 0}
    if path == "/api/source":
        return {
            "source_case": str(source),
            "output_root": str(output),
            "bodies": [
                {"body_id": index, "node_count": body.node_count, "fort": f"fort.{fort_start + index - 1}", "has_fort": (source / f"fort.{fort_start + index - 1}").is_file(), "bounds": {"min": body.points.min(axis=0).tolist(), "max": body.points.max(axis=0).tolist()}}
                for index, body in enumerate(bodies, 1)
            ],
            "mesh": mesh,
            "amr": amr,
        }
    groups = parse_body_groups(
        payload.get("groups"), len(bodies),
        available_amr_ids=available_amr_ids, moving_amr_ids=moving_amr_ids,
    )
    prefix = str(payload.get("case_prefix") or "case")
    if path == "/api/preview":
        geometry = grouped_preview_payload(
            source, groups, prefix, output, fort_start=fort_start,
            component_order=component_order, amr=amr,
        )
        return {"source_case": str(source), "output_root": str(output), "mesh": mesh, "amr": amr, **geometry}
    if path == "/api/create":
        return {"created": [str(v.case_dir) for v in create_grouped_cases(source, output, groups, prefix, fort_start=fort_start, component_order=component_order)]}
    raise ValueError(f"Unknown API route: {path}")


def _free_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + 50):
        with socket.socket() as sock:
            if sock.connect_ex((host, port)) != 0:
                return port
    raise OSError("No free port found")


def main() -> None:
    args = parse_args()
    source = (args.case or REPO_ROOT / "example" / "run_case").resolve()
    port = args.port if args.strict_port else _free_port(args.host, args.port)
    server = ThreadingHTTPServer((args.host, port), make_handler(source))
    print(f"Picar Batch Case Setup\nSource : {source}\nURL    : http://{args.host}:{port}/\nPress Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
