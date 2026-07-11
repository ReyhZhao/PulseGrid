"""
Check execution: HTTP(S) availability/latency/SSL, TCP connect and
traceroute path checks.

Each check returns a result dict in the shape the control plane's
/api/v1/worker/results endpoint expects. All failures are captured as
`ok: False` results — a check never raises.
"""

import asyncio
import re
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


TRACEROUTE_MAX_HOPS = 30
TRACEROUTE_TARGET_RE = re.compile(r"^traceroute to \S+ \((?P<ip>[0-9a-fA-F.:]+)\)")
TRACEROUTE_HOP_RE = re.compile(
    r"^\s*(?P<ttl>\d+)\s+(?:\*|(?P<ip>[0-9a-fA-F.:]+)(?:\s+\((?P=ip)\))?\s+(?P<rtt>[\d.]+)\s*ms)"
)

ASN_WHOIS_HOST = "whois.cymru.com"
ASN_WHOIS_PORT = 43


def parse_traceroute_output(output: str) -> tuple[str | None, list[dict]]:
    """Parse `traceroute -n -q 1` output into (destination_ip, hops).

    Hops are `{"ttl": int, "ip": str | None, "rtt_ms": float | None}`;
    unanswered probes keep their TTL slot with ip/rtt of None.
    """
    dest_ip = None
    hops = []
    for line in output.splitlines():
        target = TRACEROUTE_TARGET_RE.match(line)
        if target:
            dest_ip = target.group("ip")
            continue
        hop = TRACEROUTE_HOP_RE.match(line)
        if hop:
            rtt = hop.group("rtt")
            hops.append(
                {
                    "ttl": int(hop.group("ttl")),
                    "ip": hop.group("ip"),
                    "rtt_ms": float(rtt) if rtt else None,
                }
            )
    return dest_ip, hops


async def lookup_asns(ips: list[str], timeout: float = 10.0) -> dict[str, int]:
    """Map IPs to origin AS numbers via Team Cymru's bulk whois service.

    Best-effort: unknown/private IPs and lookup failures simply leave the IP
    out of the mapping — path checks must not fail because whois is down.
    """
    if not ips:
        return {}
    query = "begin\nnoheader\n" + "\n".join(dict.fromkeys(ips)) + "\nend\n"

    async def talk() -> bytes:
        reader, writer = await asyncio.open_connection(ASN_WHOIS_HOST, ASN_WHOIS_PORT)
        try:
            writer.write(query.encode())
            await writer.drain()
            return await reader.read()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    try:
        response = await asyncio.wait_for(talk(), timeout=timeout)
    except (OSError, TimeoutError):
        return {}

    asn_by_ip: dict[str, int] = {}
    # Response lines: "13335   | 1.1.1.1          | CLOUDFLARENET, US"
    for line in response.decode(errors="replace").splitlines():
        fields = [field.strip() for field in line.split("|")]
        if len(fields) >= 2 and fields[0].isdigit():
            asn_by_ip[fields[1]] = int(fields[0])
    return asn_by_ip


async def run_traceroute(host: str, max_hops: int, timeout: float) -> str:
    """Run the system traceroute binary and return its stdout."""
    process = await asyncio.create_subprocess_exec(
        "traceroute",
        "-n",  # numeric output; we never need reverse DNS
        "-q", "1",  # one probe per hop keeps the parse and the runtime small
        "-w", "2",
        "-m", str(max_hops),
        host,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    # traceroute exits non-zero on resolution errors; unreachable paths still
    # exit 0, so treat stderr-only failures (no hop lines) as errors below.
    if process.returncode != 0 and not stdout:
        raise RuntimeError(stderr.decode(errors="replace").strip() or "traceroute failed")
    # BSD traceroute prints the "traceroute to host (ip)" header on stderr,
    # Linux on stdout — hand the parser both.
    return stderr.decode(errors="replace") + "\n" + stdout.decode(errors="replace")


async def check_traceroute(task: dict) -> dict:
    result = _base_result(task)
    result["hop_count"] = None
    result["hops"] = []
    host = task.get("host", "")
    timeout = float(task.get("timeout", 30))
    hop_min = task.get("hop_threshold_min")
    hop_max = task.get("hop_threshold_max")
    required_asn = task.get("required_asn")
    max_hops = max(TRACEROUTE_MAX_HOPS, int(hop_max or 0) + 1)

    try:
        output = await run_traceroute(host, max_hops, timeout)
    except TimeoutError:
        result["error"] = f"traceroute timed out after {timeout}s"
        return result
    except (OSError, RuntimeError) as exc:
        result["error"] = str(exc) or exc.__class__.__name__
        return result

    dest_ip, hops = parse_traceroute_output(output)

    if required_asn is not None:
        responding = [hop["ip"] for hop in hops if hop["ip"]]
        asn_by_ip = await lookup_asns(responding, timeout=min(timeout, 10))
        for hop in hops:
            hop["asn"] = asn_by_ip.get(hop["ip"]) if hop["ip"] else None
    result["hops"] = hops

    final = next((hop for hop in hops if hop["ip"] and hop["ip"] == dest_ip), None)
    if final is None:
        result["error"] = f"destination not reached within {max_hops} hops"
        return result

    result["hop_count"] = final["ttl"]
    result["latency_ms"] = final["rtt_ms"]

    if hop_min is not None and final["ttl"] < int(hop_min):
        result["error"] = f"path is {final['ttl']} hop(s), below the minimum of {hop_min}"
        return result
    if hop_max is not None and final["ttl"] > int(hop_max):
        result["error"] = f"path is {final['ttl']} hop(s), above the maximum of {hop_max}"
        return result
    if required_asn is not None:
        path_asns = {hop.get("asn") for hop in hops}
        if int(required_asn) not in path_asns:
            result["error"] = f"AS{required_asn} is missing from the path"
            return result

    result["ok"] = True
    return result


async def run_check(task: dict) -> dict:
    try:
        if task.get("type") == "tcp":
            return await check_tcp(task)
        if task.get("type") == "traceroute":
            return await check_traceroute(task)
        return await check_http(task)
    except Exception as exc:  # last-resort guard: a check must never raise
        result = _base_result(task)
        result["error"] = f"internal check error: {exc}"
        return result
