import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@pytest.fixture(autouse=True)
def _disable_ssrf_guard(monkeypatch):
    """Most check tests target 127.0.0.1; keep the SSRF guard off by default so
    they can. The guard's own tests re-enable it explicitly."""
    monkeypatch.setenv("WORKER_BLOCK_PRIVATE_TARGETS", "false")


class _Handler(BaseHTTPRequestHandler):
    """Tiny configurable origin for check tests."""

    routes = {}

    def do_GET(self):
        status, body = self.routes.get(self.path, (404, b"not found"))
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep test output clean
        pass


@pytest.fixture
def http_server():
    _Handler.routes = {
        "/ok": (200, b"all good with magic-keyword inside"),
        "/broken": (500, b"boom"),
        "/redirect-me": (301, b"moved"),
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def make_http_task(url, **overrides):
    task = {
        "task_id": "t-1",
        "monitor_id": "m-1",
        "region": "eu-west",
        "type": "http",
        "url": url,
        "method": "GET",
        "timeout": 5,
        "expected_status": "200-299",
        "keyword": "",
        "verify_ssl": True,
    }
    task.update(overrides)
    return task
