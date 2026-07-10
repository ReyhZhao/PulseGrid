import logging

from django.conf import settings
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.monitors.services import ingest_result
from pulsegrid import queues

from .auth import IsWorker, WorkerTokenAuthentication

logger = logging.getLogger(__name__)


class WorkerAPIView(APIView):
    authentication_classes = [WorkerTokenAuthentication]
    permission_classes = [IsWorker]

    def touch(self, request):
        worker = request.auth
        worker.last_seen_at = timezone.now()
        update = ["last_seen_at"]
        version = request.data.get("version") if isinstance(request.data, dict) else None
        if version and version != worker.version:
            worker.version = str(version)[:50]
            update.append("version")
        worker.save(update_fields=update)
        return worker


class ClaimTasksView(WorkerAPIView):
    """Workers poll this endpoint to claim a batch of due checks for their
    region. Payloads are self-contained so this is the only round trip."""

    def post(self, request):
        worker = self.touch(request)
        max_batch = settings.PULSEGRID["MAX_CLAIM_BATCH"]
        try:
            requested = int(request.data.get("max_tasks", max_batch))
        except (TypeError, ValueError):
            requested = max_batch
        tasks = queues.pop_check_tasks(worker.region.code, max(1, min(requested, max_batch)))
        return Response({"region": worker.region.code, "tasks": tasks})


class SubmitResultsView(WorkerAPIView):
    def post(self, request):
        worker = self.touch(request)
        results = request.data.get("results")
        if not isinstance(results, list):
            return Response({"detail": "results must be a list"}, status=400)
        accepted = 0
        for payload in results[: settings.PULSEGRID["MAX_CLAIM_BATCH"]]:
            if not isinstance(payload, dict):
                continue
            if ingest_result(payload, region_code=worker.region.code) is not None:
                accepted += 1
        return Response({"accepted": accepted})


class HeartbeatView(WorkerAPIView):
    def post(self, request):
        worker = self.touch(request)
        return Response(
            {
                "worker": worker.name,
                "region": worker.region.code,
                "queue_depth": queues.check_queue_depth(worker.region.code),
                "server_time": timezone.now().isoformat(),
            }
        )
