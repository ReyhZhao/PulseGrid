"""SSRF guard for check execution (defense in depth).

The control plane validates monitor targets at creation time, but a worker is
the component that actually connects out, so it re-screens every target here.
A worker that legitimately monitors internal endpoints sets
``WORKER_BLOCK_PRIVATE_TARGETS=false`` to opt specific deployments back in.
"""

import ipaddress
import os
import socket


def guard_enabled() -> bool:
    raw = os.environ.get("WORKER_BLOCK_PRIVATE_TARGETS", "true")
    return raw.strip().lower() in ("1", "true", "yes", "on")


def ip_is_public(ip_str: str) -> bool:
    addr = ipaddress.ip_address(ip_str)
    mapped = getattr(addr, "ipv4_mapped", None)
    if mapped is not None:
        addr = mapped
    return addr.is_global


def blocked_reason(host: str, port: int | None = None) -> str | None:
    """Return a reason string if ``host`` must not be checked, else None.

    Resolves DNS and rejects if the host is (or resolves to) any non-public
    address — loopback, link-local (incl. ``169.254.169.254``), RFC1918,
    unique-local IPv6, etc. A resolution failure is left to the check itself
    to report as a normal DNS error.
    """
    if not guard_enabled():
        return None
    if not host:
        return None
    try:
        ipaddress.ip_address(host)
        ips = [host]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        except OSError:
            return None  # DNS failure surfaces via the normal check path
        ips = [info[4][0] for info in infos]
    for ip in ips:
        if not ip_is_public(ip):
            return f"target {host!r} resolves to non-public address {ip}"
    return None
