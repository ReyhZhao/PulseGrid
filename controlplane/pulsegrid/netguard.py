"""SSRF guard: reject targets that resolve to non-public (internal) addresses.

Used to screen operator-supplied destinations before the control plane (or a
worker) issues a request to them — webhook notification URLs and monitor
targets — so an authenticated user can't turn the platform into a probe of
cloud-metadata endpoints (``169.254.169.254``), loopback, or RFC1918/internal
services.

A single knob, ``settings.PULSEGRID_BLOCK_PRIVATE_TARGETS`` (default on),
gates enforcement so a deployment that legitimately monitors internal
endpoints can opt out. DNS is resolved and *every* returned address checked,
so a hostname that resolves to a mix of public and private IPs is rejected.
"""

import ipaddress
import socket

from django.conf import settings


class BlockedTargetError(ValueError):
    """A target host resolves to (or is) a non-public address."""


class UnresolvableTargetError(BlockedTargetError):
    """A target host could not be resolved at all."""


def guard_enabled() -> bool:
    return getattr(settings, "PULSEGRID_BLOCK_PRIVATE_TARGETS", True)


def ip_is_public(ip_str: str) -> bool:
    """True only for globally-routable addresses.

    ``is_global`` is False for loopback, link-local (incl. the
    ``169.254.169.254`` metadata IP), RFC1918, unique-local IPv6
    (``fc00::/7``, covering ``fd00:ec2::254``), carrier-grade NAT and other
    reserved ranges, so this is the conservative allow-list we want.
    """
    addr = ipaddress.ip_address(ip_str)
    mapped = getattr(addr, "ipv4_mapped", None)
    if mapped is not None:  # normalise ::ffff:169.254.169.254 → 169.254.169.254
        addr = mapped
    return addr.is_global


def resolve_ips(host: str, port: int | None = None) -> list[str]:
    """Resolve ``host`` to the list of literal IPs it maps to. Patchable in tests."""
    infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    return [info[4][0] for info in infos]


def blocked_reason(host: str, port: int | None = None, *, block_unresolvable: bool = True) -> str | None:
    """Return a human-readable reason if ``host`` is not allowed, else None.

    No-op (returns None) when the guard is disabled. ``block_unresolvable``
    controls whether a DNS failure is treated as a block: request-time callers
    (webhook delivery) want to block, whereas creation-time validation prefers
    to allow a not-yet-resolvable host and rely on the request-time guard.
    """
    if not guard_enabled():
        return None
    if not host:
        return "empty host"
    try:
        ipaddress.ip_address(host)
        ips = [host]
    except ValueError:
        try:
            ips = resolve_ips(host, port)
        except OSError:
            return f"host {host!r} could not be resolved" if block_unresolvable else None
    if not ips:
        return f"host {host!r} could not be resolved" if block_unresolvable else None
    for ip in ips:
        if not ip_is_public(ip):
            return f"host {host!r} resolves to non-public address {ip}"
    return None


def assert_public_host(host: str, port: int | None = None) -> None:
    """Raise ``BlockedTargetError`` unless ``host`` resolves only to public IPs."""
    reason = blocked_reason(host, port, block_unresolvable=True)
    if reason is not None:
        if "could not be resolved" in reason:
            raise UnresolvableTargetError(reason)
        raise BlockedTargetError(reason)
