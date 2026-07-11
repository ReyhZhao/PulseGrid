from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import Severity
from .services import record


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    record(
        "auth.login",
        f"User '{user.get_username()}' signed in",
        request=request,
        actor=user.get_username(),
        severity=Severity.INFO,
    )


@receiver(user_login_failed)
def audit_login_failed(sender, credentials, request=None, **kwargs):
    username = (credentials or {}).get("username", "")
    record(
        "auth.login_failed",
        f"Failed login attempt for '{username or 'unknown'}'",
        request=request,
        actor=username,
        severity=Severity.MEDIUM,
    )


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    if user is None:
        return
    record(
        "auth.logout",
        f"User '{user.get_username()}' signed out",
        request=request,
        actor=user.get_username(),
        severity=Severity.INFO,
    )
