from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsOrganizationMember, user_organization_ids
from apps.audit.models import Severity
from apps.audit.services import record as audit

from .models import Monitor, Region
from .serializers import (
    CheckResultSerializer,
    MonitorSerializer,
    MonitorStatsSerializer,
    PauseStateSerializer,
    RegionSerializer,
)
from .services import monitor_stats

MAX_RESULT_POINTS = 500


@extend_schema(tags=["regions"])
class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Region.objects.filter(is_active=True)
    serializer_class = RegionSerializer
    pagination_class = None


@extend_schema(tags=["monitors"])
@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                "organization",
                OpenApiTypes.UUID,
                description="Filter to a single organization the caller belongs to.",
            )
        ]
    ),
)
class MonitorViewSet(viewsets.ModelViewSet):
    serializer_class = MonitorSerializer
    permission_classes = [IsOrganizationMember]
    # Sentinel so drf-spectacular can derive the pk type; get_queryset governs
    # what is actually returned per request.
    queryset = Monitor.objects.none()

    def get_queryset(self):
        qs = Monitor.objects.filter(organization_id__in=user_organization_ids(self.request.user))
        org = self.request.query_params.get("organization")
        if org:
            qs = qs.filter(organization_id=org)
        return qs

    def perform_create(self, serializer):
        monitor = serializer.save(next_check_at=timezone.now())
        audit(
            "monitor.created",
            f"Monitor '{monitor.name}' created ({monitor.target})",
            request=self.request,
            organization=monitor.organization,
            monitor_id=monitor.id,
        )

    def perform_update(self, serializer):
        monitor = serializer.save()
        audit(
            "monitor.updated",
            f"Monitor '{monitor.name}' updated",
            request=self.request,
            organization=monitor.organization,
            monitor_id=monitor.id,
            changes=sorted(serializer.validated_data.keys()),
        )

    def perform_destroy(self, instance):
        audit(
            "monitor.deleted",
            f"Monitor '{instance.name}' deleted ({instance.target})",
            severity=Severity.MEDIUM,
            request=self.request,
            organization=instance.organization,
            monitor_id=instance.id,
        )
        instance.delete()

    @extend_schema(summary="Pause a monitor", request=None, responses=PauseStateSerializer)
    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        monitor = self.get_object()
        monitor.is_paused = True
        monitor.save(update_fields=["is_paused"])
        audit(
            "monitor.paused",
            f"Monitor '{monitor.name}' paused",
            request=request,
            organization=monitor.organization,
            monitor_id=monitor.id,
        )
        return Response({"is_paused": True})

    @extend_schema(summary="Resume a paused monitor", request=None, responses=PauseStateSerializer)
    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        monitor = self.get_object()
        monitor.is_paused = False
        monitor.next_check_at = timezone.now()
        monitor.save(update_fields=["is_paused", "next_check_at"])
        audit(
            "monitor.resumed",
            f"Monitor '{monitor.name}' resumed",
            request=request,
            organization=monitor.organization,
            monitor_id=monitor.id,
        )
        return Response({"is_paused": False})

    @extend_schema(
        summary="Recent check results",
        parameters=[
            OpenApiParameter(
                "hours", OpenApiTypes.INT, description="Look-back window in hours (max 720). Default 24."
            ),
            OpenApiParameter("region", OpenApiTypes.STR, description="Filter to a single region code."),
        ],
        responses=CheckResultSerializer(many=True),
    )
    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        monitor = self.get_object()
        try:
            hours = min(int(request.query_params.get("hours", 24)), 24 * 30)
        except ValueError:
            hours = 24
        since = timezone.now() - timezone.timedelta(hours=hours)
        qs = monitor.results.filter(checked_at__gte=since)
        region = request.query_params.get("region")
        if region:
            qs = qs.filter(region_code=region)
        results = qs.order_by("-checked_at")[:MAX_RESULT_POINTS]
        return Response(CheckResultSerializer(results, many=True).data)

    @extend_schema(summary="Uptime and latency statistics", responses=MonitorStatsSerializer)
    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        return Response(monitor_stats(self.get_object()))
