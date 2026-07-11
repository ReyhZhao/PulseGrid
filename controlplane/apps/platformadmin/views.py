"""
Platform administration API (staff/superusers only, `/api/v1/admin/`).

Everything a platform operator needs that is out of reach for regular
organization owners: worker fleet management, region CRUD, cross-tenant
organization and user management, platform-wide statistics and the
platform-wide audit trail. Every mutation is written to the audit log.
"""

import secrets
import uuid

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Organization
from apps.alerts.models import AlertEvent
from apps.audit.models import AuditEvent, Severity
from apps.audit.serializers import AuditEventSerializer
from apps.audit.services import record as audit
from apps.monitors.models import CheckResult, Monitor, MonitorStatus, Region
from apps.workerapi.models import Worker

from .permissions import IsPlatformAdmin
from .serializers import (
    AdminOrganizationSerializer,
    AdminRegionSerializer,
    AdminUserCreateSerializer,
    AdminUserSerializer,
    AdminWorkerCreatedSerializer,
    AdminWorkerSerializer,
    AuditSummarySerializer,
    OrgActiveStateSerializer,
    PlatformStatsSerializer,
    SetPasswordSerializer,
)


@extend_schema(tags=["platform-admin"])
class AdminRegionViewSet(viewsets.ModelViewSet):
    """Full region CRUD. Deactivating a region removes it from every
    monitor's effective region set; deleting requires it to have no workers."""

    serializer_class = AdminRegionSerializer
    permission_classes = [IsPlatformAdmin]
    pagination_class = None
    queryset = Region.objects.all()

    def get_queryset(self):
        return Region.objects.annotate(worker_count=Count("workers")).order_by("code")

    def perform_create(self, serializer):
        region = serializer.save()
        audit(
            "admin.region_created",
            f"Region '{region.code}' ({region.name}) created",
            severity=Severity.MEDIUM,
            request=self.request,
        )

    def perform_update(self, serializer):
        region = serializer.save()
        audit(
            "admin.region_updated",
            f"Region '{region.code}' updated",
            severity=Severity.MEDIUM,
            request=self.request,
            changes=sorted(serializer.validated_data.keys()),
        )

    def perform_destroy(self, instance):
        if instance.workers.exists():
            raise ValidationError(
                {"detail": "This region still has workers. Delete or reassign them first."}
            )
        audit(
            "admin.region_deleted",
            f"Region '{instance.code}' ({instance.name}) deleted",
            severity=Severity.HIGH,
            request=self.request,
        )
        instance.delete()


@extend_schema(tags=["platform-admin"])
@extend_schema_view(
    create=extend_schema(
        summary="Create a worker",
        description="Returns the worker plus its API token. The token is shown exactly once.",
        responses={201: AdminWorkerCreatedSerializer},
    ),
)
class AdminWorkerViewSet(viewsets.ModelViewSet):
    """Worker fleet management. Tokens are stored hashed; creation and
    rotation are the only moments the plaintext token is returned."""

    serializer_class = AdminWorkerSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = Worker.objects.none()

    def get_queryset(self):
        return Worker.objects.select_related("region").order_by("name")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        worker, token = Worker.issue(data["name"], data["region"])
        if data.get("is_active") is False:
            worker.is_active = False
            worker.save(update_fields=["is_active"])
        audit(
            "admin.worker_created",
            f"Worker '{worker.name}' created in region '{worker.region.code}'",
            severity=Severity.MEDIUM,
            request=request,
            worker_id=worker.id,
            region=worker.region.code,
        )
        payload = AdminWorkerSerializer(worker).data
        payload["token"] = token
        return Response(payload, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        worker = serializer.save()
        audit(
            "admin.worker_updated",
            f"Worker '{worker.name}' updated",
            severity=Severity.MEDIUM,
            request=self.request,
            worker_id=worker.id,
            changes=sorted(serializer.validated_data.keys()),
        )

    def perform_destroy(self, instance):
        audit(
            "admin.worker_deleted",
            f"Worker '{instance.name}' ({instance.region.code}) deleted",
            severity=Severity.HIGH,
            request=self.request,
            worker_id=instance.id,
        )
        instance.delete()

    @extend_schema(
        summary="Rotate a worker's token",
        description="Invalidates the current token and returns a new one. Shown exactly once.",
        request=None,
        responses=AdminWorkerCreatedSerializer,
    )
    @action(detail=True, methods=["post"], url_path="rotate-token")
    def rotate_token(self, request, pk=None):
        worker = self.get_object()
        token = f"pgw_{secrets.token_urlsafe(32)}"
        worker.token_hash = Worker.hash_token(token)
        worker.save(update_fields=["token_hash"])
        audit(
            "admin.worker_token_rotated",
            f"Token rotated for worker '{worker.name}'",
            severity=Severity.HIGH,
            request=request,
            worker_id=worker.id,
        )
        payload = AdminWorkerSerializer(worker).data
        payload["token"] = token
        return Response(payload)


@extend_schema(tags=["platform-admin"])
class AdminOrganizationViewSet(viewsets.ModelViewSet):
    """Cross-tenant organization management. Disabling an organization stops
    all of its monitors from being scheduled without touching any data."""

    serializer_class = AdminOrganizationSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = Organization.objects.none()

    def get_queryset(self):
        qs = Organization.objects.annotate(
            member_count=Count("memberships", distinct=True),
            monitor_count=Count("monitors", distinct=True),
        ).order_by("name")
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    def perform_create(self, serializer):
        org = serializer.save()
        owner = serializer.validated_data.get("owner_username")
        audit(
            "admin.org_created",
            f"Organization '{org.name}' created by an administrator",
            severity=Severity.MEDIUM,
            request=self.request,
            organization=org,
            owner=owner.get_username() if owner else None,
        )

    def perform_update(self, serializer):
        old_name = serializer.instance.name
        org = serializer.save()
        audit(
            "admin.org_updated",
            f"Organization '{old_name}' updated"
            + (f" (renamed to '{org.name}')" if org.name != old_name else ""),
            severity=Severity.MEDIUM,
            request=self.request,
            organization=org,
        )

    def perform_destroy(self, instance):
        audit(
            "admin.org_deleted",
            f"Organization '{instance.name}' and all of its data deleted",
            severity=Severity.HIGH,
            request=self.request,
            org_slug=instance.slug,
        )
        instance.delete()

    @extend_schema(
        summary="Disable an organization",
        description="Monitors of a disabled organization are no longer scheduled.",
        request=None,
        responses=OrgActiveStateSerializer,
    )
    @action(detail=True, methods=["post"])
    def disable(self, request, pk=None):
        org = self.get_object()
        if org.is_active:
            org.is_active = False
            org.save(update_fields=["is_active"])
            audit(
                "admin.org_disabled",
                f"Organization '{org.name}' disabled — monitoring suspended",
                severity=Severity.HIGH,
                request=request,
                organization=org,
            )
        return Response({"is_active": False})

    @extend_schema(summary="Re-enable an organization", request=None, responses=OrgActiveStateSerializer)
    @action(detail=True, methods=["post"])
    def enable(self, request, pk=None):
        org = self.get_object()
        if not org.is_active:
            org.is_active = True
            org.save(update_fields=["is_active"])
            # Re-anchor so a long suspension doesn't cause a thundering herd
            # of "overdue" checks with stale scheduled_at timestamps.
            Monitor.objects.filter(organization=org).update(next_check_at=timezone.now())
            audit(
                "admin.org_enabled",
                f"Organization '{org.name}' re-enabled — monitoring resumed",
                severity=Severity.MEDIUM,
                request=request,
                organization=org,
            )
        return Response({"is_active": True})


@extend_schema(tags=["platform-admin"])
@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("q", OpenApiTypes.STR, description="Search username or email."),
            OpenApiParameter("is_active", OpenApiTypes.BOOL, description="Filter by active state."),
        ]
    ),
)
class AdminUserViewSet(viewsets.ModelViewSet):
    """Platform-wide user management. Staff can manage regular users;
    only superusers can touch staff/superuser accounts, and nobody can
    lock themselves out."""

    permission_classes = [IsPlatformAdmin]
    queryset = get_user_model().objects.none()

    def get_serializer_class(self):
        return AdminUserCreateSerializer if self.action == "create" else AdminUserSerializer

    def get_queryset(self):
        qs = (
            get_user_model()
            .objects.prefetch_related("memberships__organization")
            .order_by("username")
        )
        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q))
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ("1", "true", "yes"))
        return qs

    def _guard_target(self, target):
        """Staff may not manage privileged accounts; nobody manages themselves."""
        request_user = self.request.user
        if target.pk == request_user.pk:
            raise PermissionDenied("You cannot modify or delete your own account here.")
        if (target.is_superuser or target.is_staff) and not request_user.is_superuser:
            raise PermissionDenied("Only superusers can manage staff or superuser accounts.")

    def perform_create(self, serializer):
        user = serializer.save()
        audit(
            "admin.user_created",
            f"User '{user.get_username()}' created by an administrator",
            severity=Severity.MEDIUM,
            request=self.request,
            user_id=user.id,
            is_staff=user.is_staff,
        )

    def perform_update(self, serializer):
        self._guard_target(serializer.instance)
        old_active = serializer.instance.is_active
        user = serializer.save()
        audit(
            "admin.user_updated",
            f"User '{user.get_username()}' updated",
            severity=Severity.HIGH if old_active != user.is_active else Severity.MEDIUM,
            request=self.request,
            user_id=user.id,
            changes=sorted(serializer.validated_data.keys()),
        )

    def perform_destroy(self, instance):
        self._guard_target(instance)
        audit(
            "admin.user_deleted",
            f"User '{instance.get_username()}' deleted",
            severity=Severity.HIGH,
            request=self.request,
            deleted_username=instance.get_username(),
        )
        instance.delete()

    @extend_schema(
        summary="Set a user's password",
        request=SetPasswordSerializer,
        responses={204: None},
    )
    @action(detail=True, methods=["post"], url_path="set-password")
    def set_password(self, request, pk=None):
        user = self.get_object()
        self._guard_target(user)
        serializer = SetPasswordSerializer(data=request.data, context={"user": user})
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])
        audit(
            "admin.user_password_set",
            f"Password reset for user '{user.get_username()}' by an administrator",
            severity=Severity.HIGH,
            request=request,
            user_id=user.id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    summary="Platform statistics",
    tags=["platform-admin"],
    responses=PlatformStatsSerializer,
)
class PlatformStatsView(APIView):
    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        now = timezone.now()
        day_ago = now - timezone.timedelta(hours=24)
        month_ago = now - timezone.timedelta(days=30)
        online_cutoff = now - timezone.timedelta(minutes=5)
        User = get_user_model()

        def by_status(qs):
            return {row["status"]: row["n"] for row in qs.values("status").annotate(n=Count("id"))}

        monitor_counts = by_status(Monitor.objects.all())
        return Response(
            {
                "users": {
                    "total": User.objects.count(),
                    "active": User.objects.filter(is_active=True).count(),
                    "staff": User.objects.filter(is_staff=True).count(),
                    "new_30d": User.objects.filter(date_joined__gte=month_ago).count(),
                },
                "organizations": {
                    "total": Organization.objects.count(),
                    "active": Organization.objects.filter(is_active=True).count(),
                    "disabled": Organization.objects.filter(is_active=False).count(),
                },
                "monitors": {
                    "total": Monitor.objects.count(),
                    "up": monitor_counts.get(MonitorStatus.UP, 0),
                    "down": monitor_counts.get(MonitorStatus.DOWN, 0),
                    "unknown": monitor_counts.get(MonitorStatus.UNKNOWN, 0),
                    "paused": Monitor.objects.filter(is_paused=True).count(),
                },
                "workers": {
                    "total": Worker.objects.count(),
                    "active": Worker.objects.filter(is_active=True).count(),
                    "online": Worker.objects.filter(
                        is_active=True, last_seen_at__gte=online_cutoff
                    ).count(),
                },
                "regions": {
                    "total": Region.objects.count(),
                    "active": Region.objects.filter(is_active=True).count(),
                },
                "checks_24h": {
                    "total": CheckResult.objects.filter(checked_at__gte=day_ago).count(),
                    "failed": CheckResult.objects.filter(checked_at__gte=day_ago, ok=False).count(),
                },
                "alerts": {
                    "open": AlertEvent.objects.filter(status=AlertEvent.Status.OPEN).count(),
                    "opened_24h": AlertEvent.objects.filter(opened_at__gte=day_ago).count(),
                },
                "audit_24h": {
                    "total": AuditEvent.objects.filter(created_at__gte=day_ago).count(),
                    "high_or_critical": AuditEvent.objects.filter(
                        created_at__gte=day_ago,
                        severity__in=[Severity.HIGH, Severity.CRITICAL],
                    ).count(),
                },
            }
        )


@extend_schema(tags=["platform-admin"])
@extend_schema_view(
    list=extend_schema(
        summary="Platform-wide audit trail",
        parameters=[
            OpenApiParameter("event_type", OpenApiTypes.STR, description="Filter by event type."),
            OpenApiParameter("severity", OpenApiTypes.STR, description="Filter by severity."),
            OpenApiParameter("organization", OpenApiTypes.UUID, description="Filter by organization."),
            OpenApiParameter("actor", OpenApiTypes.STR, description="Filter by actor (contains)."),
            OpenApiParameter("q", OpenApiTypes.STR, description="Search in the event message."),
        ],
    ),
)
class AdminAuditViewSet(viewsets.ReadOnlyModelViewSet):
    """Unlike the org-scoped `/api/v1/audit/`, this includes platform-level
    events (organization = null, e.g. worker auth failures) and events from
    every tenant."""

    serializer_class = AuditEventSerializer
    permission_classes = [IsPlatformAdmin]
    queryset = AuditEvent.objects.none()

    def get_queryset(self):
        qs = AuditEvent.objects.all()
        params = self.request.query_params
        if event_type := params.get("event_type"):
            qs = qs.filter(event_type=event_type)
        if severity := params.get("severity"):
            qs = qs.filter(severity=severity)
        if organization := params.get("organization"):
            try:
                qs = qs.filter(organization_id=uuid.UUID(organization))
            except ValueError:
                qs = qs.none()
        if actor := params.get("actor"):
            qs = qs.filter(actor__icontains=actor)
        if q := params.get("q"):
            qs = qs.filter(message__icontains=q)
        return qs

    @extend_schema(
        summary="Audit activity summary",
        parameters=[
            OpenApiParameter(
                "days", OpenApiTypes.INT, description="Look-back window in days (1-90, default 7)."
            ),
        ],
        responses=AuditSummarySerializer,
    )
    @action(detail=False, methods=["get"])
    def summary(self, request):
        try:
            days = int(request.query_params.get("days", 7))
        except ValueError:
            days = 7
        days = max(1, min(days, 90))
        since = timezone.now() - timezone.timedelta(days=days)
        qs = AuditEvent.objects.filter(created_at__gte=since)

        by_severity = {row["severity"]: row["n"] for row in qs.values("severity").annotate(n=Count("id"))}
        by_event_type = {
            row["event_type"]: row["n"]
            for row in qs.values("event_type").annotate(n=Count("id")).order_by("-n")[:10]
        }
        by_day = [
            {"date": row["day"].isoformat(), "count": row["n"]}
            for row in qs.annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(n=Count("id"))
            .order_by("day")
        ]
        return Response(
            {
                "days": days,
                "total": qs.count(),
                "by_severity": by_severity,
                "by_event_type": by_event_type,
                "by_day": by_day,
            }
        )
