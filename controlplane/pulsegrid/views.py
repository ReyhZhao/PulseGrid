import logging

from django.db import connection
from django.http import JsonResponse

from . import queues

logger = logging.getLogger(__name__)


def healthz(request):
    return JsonResponse({"status": "ok"})


def readyz(request):
    problems = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:  # pragma: no cover - depends on infra
        problems.append(f"database: {exc}")
    try:
        queues.get_redis().ping()
    except Exception as exc:  # pragma: no cover - depends on infra
        problems.append(f"redis: {exc}")
    if problems:
        # The probe only records the status code; make the cause visible in
        # the pod logs too.
        logger.warning("readiness check failed: %s", "; ".join(problems))
        return JsonResponse({"status": "unavailable", "problems": problems}, status=503)
    return JsonResponse({"status": "ready"})
