from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsOrganizationMember, user_organization_ids
from apps.audit.models import Severity
from apps.audit.services import record as audit

from . import push
from .models import AlertEvent, NotificationChannel, PushDelivery, PushSubscription
from .serializers import (
    AlertEventSerializer,
    NotificationChannelSerializer,
    PushSubscriptionSerializer,
)


@extend_schema(tags=["alerts"])
class NotificationChannelViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationChannelSerializer
    permission_classes = [IsOrganizationMember]
    queryset = NotificationChannel.objects.none()

    def get_queryset(self):
        return NotificationChannel.objects.filter(
            organization_id__in=user_organization_ids(self.request.user)
        )

    # Notification channels are an exfiltration vector (alert contents get
    # sent to them), so every change is audited at medium severity.
    def perform_create(self, serializer):
        channel = serializer.save()
        audit(
            "channel.created",
            f"Notification channel '{channel.name}' ({channel.channel_type}) created",
            severity=Severity.MEDIUM,
            request=self.request,
            organization=channel.organization,
            channel_id=channel.id,
            channel_type=channel.channel_type,
        )

    def perform_update(self, serializer):
        channel = serializer.save()
        audit(
            "channel.updated",
            f"Notification channel '{channel.name}' updated",
            severity=Severity.MEDIUM,
            request=self.request,
            organization=channel.organization,
            channel_id=channel.id,
        )

    def perform_destroy(self, instance):
        audit(
            "channel.deleted",
            f"Notification channel '{instance.name}' deleted",
            severity=Severity.MEDIUM,
            request=self.request,
            organization=instance.organization,
            channel_id=instance.id,
        )
        instance.delete()


@extend_schema(tags=["alerts"])
@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter("monitor", OpenApiTypes.INT, description="Filter to a single monitor id."),
            OpenApiParameter("status", OpenApiTypes.STR, description="Filter by alert status."),
        ]
    ),
)
class AlertEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AlertEventSerializer
    permission_classes = [IsOrganizationMember]
    queryset = AlertEvent.objects.none()

    def get_queryset(self):
        qs = AlertEvent.objects.filter(
            monitor__organization_id__in=user_organization_ids(self.request.user)
        ).select_related("monitor")
        monitor = self.request.query_params.get("monitor")
        if monitor:
            qs = qs.filter(monitor_id=monitor)
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs


@extend_schema(
    summary="VAPID public key for web push subscriptions",
    tags=["alerts"],
    responses={200: OpenApiTypes.OBJECT},
)
class VapidPublicKeyView(APIView):
    """The application server key the browser needs to create a push
    subscription. Empty string when the deployment has no VAPID keys."""

    def get(self, request):
        return Response({"public_key": settings.VAPID_PUBLIC_KEY})


@extend_schema_view(
    post=extend_schema(
        summary="Register this browser for web push",
        tags=["alerts"],
        request=PushSubscriptionSerializer,
        responses={201: None, 200: None},
    ),
    delete=extend_schema(
        summary="Remove a web push subscription",
        tags=["alerts"],
        request=PushSubscriptionSerializer,
        responses={204: None},
    ),
)
class PushSubscriptionView(APIView):
    """Register/deregister the calling user's browser push subscription."""

    def post(self, request):
        serializer = PushSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # Never reassign an endpoint owned by someone else: keying the upsert on
        # endpoint alone let any user rebind (hijack) another user's push
        # subscription to their account. Scope it to the caller, and refuse an
        # endpoint already registered to a different user.
        if (
            PushSubscription.objects.filter(endpoint=data["endpoint"])
            .exclude(user=request.user)
            .exists()
        ):
            return Response(
                {"detail": "This push endpoint is already registered to another account."},
                status=409,
            )
        _, created = PushSubscription.objects.update_or_create(
            user=request.user,
            endpoint=data["endpoint"],
            defaults={"p256dh": data["p256dh"], "auth": data["auth"]},
        )
        return Response(status=201 if created else 200)

    def delete(self, request):
        endpoint = str(request.data.get("endpoint", ""))
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return Response(status=204)


@extend_schema(
    summary="Send a test push notification to your own devices",
    tags=["alerts"],
    request=None,
    responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
)
class SendTestPushView(APIView):
    """Lets a user verify their push setup end-to-end from the profile page."""

    def post(self, request):
        if not (settings.VAPID_PRIVATE_KEY and settings.VAPID_PUBLIC_KEY):
            return Response(
                {"detail": "Push notifications are not configured on this server."}, status=400
            )
        if not PushSubscription.objects.filter(user=request.user).exists():
            return Response(
                {"detail": "This account has no registered devices. Enable push first."},
                status=400,
            )
        delivered = push.send_to_user(
            request.user.id,
            {
                "title": "🔔 PulseGrid test notification",
                "body": "Push notifications are set up correctly on this device.",
                "url": "/profile",
            },
        )
        return Response({"delivered": delivered})


@extend_schema(
    summary="Alerts pushed to you per day",
    tags=["alerts"],
    parameters=[
        OpenApiParameter(
            "days", OpenApiTypes.INT, description="Lookback window in days (1-90, default 30)."
        )
    ],
    responses={200: OpenApiTypes.OBJECT},
)
class PushStatsView(APIView):
    """Daily counts of push notifications delivered to the calling user,
    zero-filled so charts can consume the series directly."""

    DEFAULT_DAYS = 30
    MAX_DAYS = 90

    def get(self, request):
        try:
            days = int(request.query_params.get("days", self.DEFAULT_DAYS))
        except (TypeError, ValueError):
            days = self.DEFAULT_DAYS
        days = max(1, min(days, self.MAX_DAYS))

        today = timezone.now().date()
        start = today - timedelta(days=days - 1)
        rows = (
            PushDelivery.objects.filter(user=request.user, created_at__date__gte=start)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("id"))
        )
        counts = {row["day"]: row["count"] for row in rows}
        by_day = [
            {
                "date": (start + timedelta(days=offset)).isoformat(),
                "count": counts.get(start + timedelta(days=offset), 0),
            }
            for offset in range(days)
        ]
        return Response({"days": days, "total": sum(counts.values()), "by_day": by_day})
