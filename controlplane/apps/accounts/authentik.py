"""
On-demand user provisioning in Authentik.

When an organization owner invites an email address that has no Authentik
account, we create a single-use invitation for Authentik's enrollment flow
(pre-filled with the email) and put the enrollment link in the invite mail.
After the user finishes enrollment, Authentik's ?next= sends them straight
to PulseGrid's own /invite/<token> page to join the organization.

Everything here is best-effort: any Authentik API problem falls back to the
plain invite email, so SSO-side outages never block team management.

Requirements on the Authentik side (see README):
- an enrollment flow (slug in AUTHENTIK_ENROLLMENT_FLOW) with an
  Invitation stage bound to it,
- a service-account API token (AUTHENTIK_API_TOKEN) that may look up
  users/flows and create invitations.
"""

import logging
from urllib.parse import quote

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10


def is_enabled() -> bool:
    cfg = settings.PULSEGRID_AUTHENTIK
    return bool(cfg["PUBLIC_URL"] and cfg["TOKEN"] and cfg["ENROLLMENT_FLOW"])


def _api(method: str, path: str, **kwargs) -> dict:
    cfg = settings.PULSEGRID_AUTHENTIK
    response = requests.request(
        method,
        f"{cfg['PUBLIC_URL']}/api/v3{path}",
        headers={"Authorization": f"Bearer {cfg['TOKEN']}"},
        timeout=TIMEOUT_SECONDS,
        **kwargs,
    )
    response.raise_for_status()
    return response.json() if response.content else {}


def user_exists(email: str) -> bool:
    data = _api("GET", "/core/users/", params={"email": email})
    return bool(data.get("results"))


def _enrollment_flow_pk(slug: str) -> str | None:
    data = _api("GET", "/flows/instances/", params={"slug": slug})
    results = data.get("results") or []
    return results[0]["pk"] if results else None


def create_enrollment_link(email: str, invitation) -> str | None:
    """Returns an Authentik enrollment URL for `email`, or None when the
    user already exists (they can just sign in and accept the invite)."""
    cfg = settings.PULSEGRID_AUTHENTIK
    if user_exists(email):
        return None

    flow_pk = _enrollment_flow_pk(cfg["ENROLLMENT_FLOW"])
    if flow_pk is None:
        logger.error(
            "Authentik enrollment flow '%s' not found — cannot provision '%s'",
            cfg["ENROLLMENT_FLOW"],
            email,
        )
        return None

    created = _api(
        "POST",
        "/stages/invitation/invitations/",
        json={
            "name": f"pulsegrid-invite-{invitation.pk}",
            "flow": flow_pk,
            "expires": invitation.expires_at.isoformat(),
            "single_use": True,
            # Prefills the enrollment prompt(s); the email must match the
            # PulseGrid invitation so the right person joins.
            "fixed_data": {"email": email},
        },
    )
    itoken = created.get("pk")
    if not itoken:
        return None

    # After enrollment, continue to PulseGrid's own invite acceptance.
    next_url = f"{settings.PULSEGRID_FRONTEND_URL}/invite/{invitation.token}"
    return (
        f"{cfg['PUBLIC_URL']}/if/flow/{cfg['ENROLLMENT_FLOW']}/"
        f"?itoken={itoken}&next={quote(next_url, safe='')}"
    )
