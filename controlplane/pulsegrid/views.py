import logging

from django.db import connection
from django.http import JsonResponse

from . import queues

logger = logging.getLogger(__name__)


def healthz(request):
    return JsonResponse({"status": "ok"})


def readyz(request):
    # (component name, detail) pairs. Only the name is safe to hand back over
    # HTTP — /readyz is unauthenticated, and driver exceptions routinely carry
    # hostnames, ports and DSN fragments. The detail goes to the log instead.
    failures: list[tuple[str, str]] = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:  # pragma: no cover - depends on infra
        failures.append(("database", f"{type(exc).__name__}: {exc}"))
    try:
        queues.get_redis().ping()
    except Exception as exc:  # pragma: no cover - depends on infra
        failures.append(("redis", f"{type(exc).__name__}: {exc}"))
    if failures:
        # The probe only records the status code; make the full cause visible
        # in the pod logs, which is where operators diagnose this.
        logger.warning(
            "readiness check failed: %s",
            "; ".join(f"{name}: {detail}" for name, detail in failures),
        )
        return JsonResponse(
            {"status": "unavailable", "problems": [name for name, _ in failures]},
            status=503,
        )
    return JsonResponse({"status": "ready"})
