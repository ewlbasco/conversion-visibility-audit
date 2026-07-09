"""Local Website Audit MVP server."""

from __future__ import annotations

from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit

from audit_engine import AuditEngine, UnsafeUrlError
from report_renderer import OUTPUT_DIR, render_report_bundle, slugify


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_REQUEST_BYTES = 32_000


class AuditRequestHandler(SimpleHTTPRequestHandler):
    server_version = "EdgewiseWebsiteAuditMVP/0.1"

    def log_message(self, format_string: str, *args: object) -> None:
        sys.stdout.write(f"[audit-mvp] {self.address_string()} {format_string % args}\n")

    def send_json(self, payload: dict, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path, content_type: str, *, attachment: bool = False) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if attachment:
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = unquote(urlsplit(self.path).path)
        if path == "/":
            self.send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            relative = Path(path.removeprefix("/static/"))
            candidate = (STATIC_DIR / relative).resolve()
            if STATIC_DIR.resolve() not in candidate.parents:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            content_types = {
                ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
            }
            self.send_file(candidate, content_types.get(candidate.suffix.lower(), "application/octet-stream"))
            return
        if path.startswith("/reports/") and path.endswith(".html"):
            report_name = Path(path).name
            self.send_file(OUTPUT_DIR / report_name, "text/html; charset=utf-8")
            return
        if path.startswith("/reports/") and path.endswith(".pptx"):
            report_name = Path(path).name
            self.send_file(
                OUTPUT_DIR / report_name,
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                attachment=True,
            )
            return
        if path.startswith("/api/report/") and path.endswith("/pptx"):
            report_id = path.removeprefix("/api/report/").removesuffix("/pptx").strip("/")
            if not report_id or slugify(report_id) != report_id:
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            self.send_file(
                OUTPUT_DIR / f"{report_id}.pptx",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                attachment=True,
            )
            return
        if path.startswith("/api/report/") and path.endswith("/download"):
            report_id = path.removeprefix("/api/report/").removesuffix("/download").strip("/")
            if not report_id or slugify(report_id) != report_id:
                self.send_error(HTTPStatus.BAD_REQUEST)
                return
            self.send_file(OUTPUT_DIR / f"{report_id}.html", "text/html; charset=utf-8", attachment=True)
            return
        if path == "/api/health":
            self.send_json({"status": "ok", "service": "website-audit-mvp"})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/audit":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json({"error": "Invalid request length."}, HTTPStatus.BAD_REQUEST)
            return
        if length <= 0 or length > MAX_REQUEST_BYTES:
            self.send_json({"error": "Request is empty or too large."}, HTTPStatus.BAD_REQUEST)
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_json({"error": "Request body must be valid JSON."}, HTTPStatus.BAD_REQUEST)
            return

        url = str(payload.get("url", ""))
        mode = str(payload.get("mode", "full"))
        intent = str(payload.get("intent", payload.get("context", "")))[:4_000]
        try:
            audit = AuditEngine().audit(url=url, mode=mode, context=intent)
            report_id = f"{slugify(audit['url'])}-{audit['audit_id']}"
            render_report_bundle(audit, report_id=report_id)
        except UnsafeUrlError as exc:
            self.send_json({"error": str(exc), "code": "unsafe_url"}, HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:
            self.send_json(
                {
                    "error": str(exc),
                    "code": "audit_failed",
                    "detail": "The site may block automated requests or return unsupported content.",
                },
                HTTPStatus.BAD_GATEWAY,
            )
            return

        slug = slugify(audit["url"])
        self.send_json(
            {
                "report_id": report_id,
                "report_url": f"/reports/{report_id}.html",
                "download_url": f"/api/report/{report_id}/download",
                "pptx_url": f"/api/report/{report_id}/pptx",
                "specialist_url": f"/reports/{report_id}-specialist.html",
                "index_url": f"/reports/{slug}-index.html",
                "brand": audit["brand"]["name"],
                "mode": audit["mode"],
                "url": audit["url"],
                "conversion_score": audit["conversion"]["score"],
                "visibility_score": audit["visibility"]["normalized_score"],
                "visibility_basis": f"{audit['visibility']['measured_score']}/{audit['visibility']['measured_max']}",
                "root_layer": audit["conversion"]["root_layer"],
                "priority_count": len(audit["priorities"]),
                "rewrite_eligible": audit["conversion"]["rewrite_eligible"],
            },
            HTTPStatus.CREATED,
        )


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, port), AuditRequestHandler)
    print(f"Website Audit MVP running at http://{HOST}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
