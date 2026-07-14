"""Worker-side SSRF guard (#2, defense in depth)."""

import asyncio

from pulsegrid_worker import netguard
from pulsegrid_worker.checks import check_tcp, run_check

from .conftest import make_http_task


def test_ip_is_public():
    assert netguard.ip_is_public("8.8.8.8") is True
    assert netguard.ip_is_public("169.254.169.254") is False
    assert netguard.ip_is_public("127.0.0.1") is False
    assert netguard.ip_is_public("10.0.0.1") is False


def test_blocked_reason_respects_env(monkeypatch):
    monkeypatch.setenv("WORKER_BLOCK_PRIVATE_TARGETS", "false")
    assert netguard.blocked_reason("169.254.169.254") is None
    monkeypatch.setenv("WORKER_BLOCK_PRIVATE_TARGETS", "true")
    assert netguard.blocked_reason("169.254.169.254") is not None



async def test_check_http_blocks_metadata_ip(monkeypatch):
    monkeypatch.setenv("WORKER_BLOCK_PRIVATE_TARGETS", "true")
    result = await run_check(make_http_task("http://169.254.169.254/latest/meta-data/"))
    assert result["ok"] is False
    assert "blocked target" in result["error"]



async def test_check_tcp_blocks_loopback(monkeypatch):
    monkeypatch.setenv("WORKER_BLOCK_PRIVATE_TARGETS", "true")
    result = await check_tcp({"host": "127.0.0.1", "port": 22, "timeout": 2})
    assert result["ok"] is False
    assert "blocked target" in result["error"]


def test_check_tcp_still_reachable_when_disabled():
    # The autouse conftest fixture disables the guard, so loopback works.
    async def server_and_check():
        server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        result = await check_tcp({"host": "127.0.0.1", "port": port, "timeout": 2})
        server.close()
        return result

    result = asyncio.run(server_and_check())
    assert result["ok"] is True
