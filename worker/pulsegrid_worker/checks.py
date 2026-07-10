"""
Check execution: HTTP(S) availability/latency/SSL and TCP connect checks.

Each check returns a result dict in the shape the control plane's
/api/v1/worker/results endpoint expects. All failures are captured as
`ok: False` results — a check never raises.
"""

import asyncio
import socket
import ssl
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from cryptography import x509


def parse_expected_status(spec: str) -> list[tuple[int, int]]:
    """'200-299,301' -> [(200, 299), (301, 301)]"""
    ranges = []
    for part in (spec or "200-299").replace(" ", "").split(","):
        if not part:
            continue
        low, _, high = part.partition("-")
        ranges.append((int(low), int(high or low)))
    return ranges


def status_matches(spec: str, code: int) -> bool:
    return any(low <= code <= high for low, high in parse_expected_status(spec))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _base_result(task: dict) -> dict:
    return {
        "task_id": task.get("task_id"),
        "monitor_id": task.get("monitor_id"),
        "region": task.get("region"),
        "checked_at": _now_iso(),
        "ok": False,
        "latency_ms": None,
        "status_code": None,
        "error": "",
    }


async def get_ssl_info(host: str, port: int = 443, timeout: float = 10.0) -> dict | None:
    """Fetch the peer certificate and compute days until expiry.

    Runs a dedicated TLS handshake with verification disabled so we can still
    report expiry for already-expired or self-signed certificates.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    def handshake() -> bytes | None:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls:
                return tls.getpeercert(binary_form=True)

    try:
        der = await asyncio.get_running_loop().run_in_executor(None, handshake)
        if der is None:
            return None
        cert = x509.load_der_x509_certificate(der)
        expires_at = cert.not_valid_after_utc
    except Exception:
        return None
    days_left = (expires_at - datetime.now(UTC)).days
    return {"ssl_expires_at": expires_at.isoformat(), "ssl_days_left": days_left}


async def check_http(task: dict) -> dict:
    result = _base_result(task)
    url = task.get("url", "")
    timeout = float(task.get("timeout", 30))
    verify = bool(task.get("verify_ssl", True))

    parts = urlsplit(url)
    host = parts.hostname or ""

    # DNS phase, timed separately so operators can tell resolution problems
    # from slow origins.
    dns_started = time.perf_counter()
    try:
        await asyncio.get_running_loop().getaddrinfo(
            host, parts.port or (443 if parts.scheme == "https" else 80)
        )
        result["dns_ms"] = round((time.perf_counter() - dns_started) * 1000, 2)
    except OSError as exc:
        result["error"] = f"DNS resolution failed: {exc}"
        return result

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            verify=verify, timeout=timeout, follow_redirects=False, http2=False
        ) as client:
            response = await client.request(task.get("method", "GET"), url)
    except httpx.TimeoutException:
        result["error"] = f"timed out after {timeout}s"
        return result
    except httpx.HTTPError as exc:
        result["error"] = str(exc) or exc.__class__.__name__
        return result

    result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    result["status_code"] = response.status_code

    if not status_matches(task.get("expected_status", "200-299"), response.status_code):
        result["error"] = f"unexpected status {response.status_code}"
        return result

    keyword = task.get("keyword")
    if keyword and keyword not in response.text:
        result["error"] = f"keyword {keyword!r} not found in response"
        return result

    result["ok"] = True

    if parts.scheme == "https":
        ssl_info = await get_ssl_info(host, parts.port or 443, timeout=min(timeout, 10))
        if ssl_info:
            result.update(ssl_info)

    return result


async def check_tcp(task: dict) -> dict:
    result = _base_result(task)
    host = task.get("host", "")
    port = int(task.get("port") or 0)
    timeout = float(task.get("timeout", 30))

    started = time.perf_counter()
    try:
        _reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
    except TimeoutError:
        result["error"] = f"timed out after {timeout}s"
        return result
    except OSError as exc:
        result["error"] = str(exc)
        return result

    result["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    result["ok"] = True
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass
    return result


async def run_check(task: dict) -> dict:
    try:
        if task.get("type") == "tcp":
            return await check_tcp(task)
        return await check_http(task)
    except Exception as exc:  # last-resort guard: a check must never raise
        result = _base_result(task)
        result["error"] = f"internal check error: {exc}"
        return result
