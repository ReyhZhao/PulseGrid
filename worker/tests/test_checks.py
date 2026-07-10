import asyncio
import socket
import ssl
import threading

import pytest
import trustme

from pulsegrid_worker.checks import (
    check_tcp,
    get_ssl_info,
    parse_expected_status,
    run_check,
    status_matches,
)

from .conftest import make_http_task


def test_parse_expected_status():
    assert parse_expected_status("200-299") == [(200, 299)]
    assert parse_expected_status("200-299,301") == [(200, 299), (301, 301)]
    assert parse_expected_status("418") == [(418, 418)]


def test_status_matches():
    assert status_matches("200-299", 204)
    assert not status_matches("200-299", 301)
    assert status_matches("200-299,301", 301)


async def test_http_check_success_with_latency(http_server):
    result = await run_check(make_http_task(f"{http_server}/ok"))
    assert result["ok"] is True
    assert result["status_code"] == 200
    assert result["latency_ms"] > 0
    assert result["dns_ms"] is not None
    assert result["error"] == ""


async def test_http_check_unexpected_status(http_server):
    result = await run_check(make_http_task(f"{http_server}/broken"))
    assert result["ok"] is False
    assert result["status_code"] == 500
    assert "unexpected status" in result["error"]


async def test_http_check_custom_expected_status(http_server):
    result = await run_check(make_http_task(f"{http_server}/redirect-me", expected_status="301"))
    assert result["ok"] is True


async def test_http_check_keyword_match(http_server):
    ok = await run_check(make_http_task(f"{http_server}/ok", keyword="magic-keyword"))
    assert ok["ok"] is True

    missing = await run_check(make_http_task(f"{http_server}/ok", keyword="not-in-body"))
    assert missing["ok"] is False
    assert "keyword" in missing["error"]


async def test_http_check_connection_refused():
    result = await run_check(make_http_task("http://127.0.0.1:1/nope", timeout=2))
    assert result["ok"] is False
    assert result["error"]


async def test_http_check_dns_failure():
    result = await run_check(make_http_task("http://definitely-not-a-real-host.invalid/", timeout=2))
    assert result["ok"] is False
    assert "DNS" in result["error"]


async def test_tcp_check_open_and_closed_port():
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    up = await check_tcp({"host": "127.0.0.1", "port": port, "timeout": 2})
    assert up["ok"] is True
    assert up["latency_ms"] >= 0

    server.close()
    await server.wait_closed()

    down = await check_tcp({"host": "127.0.0.1", "port": port, "timeout": 2})
    assert down["ok"] is False


@pytest.fixture
def tls_server():
    """A raw TLS endpoint with a certificate valid for ~1 year."""
    from datetime import UTC, datetime, timedelta

    ca = trustme.CA()
    cert = ca.issue_cert(
        "localhost", "127.0.0.1", not_after=datetime.now(UTC) + timedelta(days=365)
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    cert.configure_cert(context)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(5)
    port = sock.getsockname()[1]
    stop = threading.Event()

    def serve():
        sock.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = sock.accept()
            except TimeoutError:
                continue
            try:
                with context.wrap_socket(conn, server_side=True):
                    pass
            except Exception:
                pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    yield port
    stop.set()
    thread.join(timeout=2)
    sock.close()


async def test_get_ssl_info_reports_expiry(tls_server):
    info = await get_ssl_info("127.0.0.1", tls_server, timeout=5)
    assert info is not None
    assert 360 <= info["ssl_days_left"] <= 366
    assert "ssl_expires_at" in info


async def test_get_ssl_info_unreachable_returns_none():
    assert await get_ssl_info("127.0.0.1", 1, timeout=1) is None
