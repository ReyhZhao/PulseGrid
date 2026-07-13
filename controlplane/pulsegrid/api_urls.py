from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.views import (
    AcceptInvitationView,
    AuthConfigView,
    CsrfView,
    MeView,
    OnboardingCompleteView,
    OrganizationViewSet,
)
from apps.alerts.views import (
    AlertEventViewSet,
    NotificationChannelViewSet,
    PushStatsView,
    PushSubscriptionView,
    SendTestPushView,
    VapidPublicKeyView,
)
from apps.audit.views import AuditEventViewSet
from apps.monitors.views import MonitorViewSet, RegionViewSet
from apps.platformadmin.views import (
    AdminAuditViewSet,
    AdminOrganizationViewSet,
    AdminRegionViewSet,
    AdminUserViewSet,
    AdminWorkerViewSet,
    PlatformStatsView,
)

router = DefaultRouter()
router.register("monitors", MonitorViewSet, basename="monitor")
router.register("regions", RegionViewSet, basename="region")
router.register("channels", NotificationChannelViewSet, basename="channel")
router.register("alerts", AlertEventViewSet, basename="alert")
router.register("audit", AuditEventViewSet, basename="audit")
router.register("orgs", OrganizationViewSet, basename="org")

# Staff/superuser-only platform administration (see apps.platformadmin).
admin_router = DefaultRouter()
admin_router.register("workers", AdminWorkerViewSet, basename="admin-worker")
admin_router.register("regions", AdminRegionViewSet, basename="admin-region")
admin_router.register("orgs", AdminOrganizationViewSet, basename="admin-org")
admin_router.register("users", AdminUserViewSet, basename="admin-user")
admin_router.register("audit", AdminAuditViewSet, basename="admin-audit")

urlpatterns = [
    path("admin/stats", PlatformStatsView.as_view()),
    path("admin/", include(admin_router.urls)),
    path("me", MeView.as_view()),
    path("onboarding/complete", OnboardingCompleteView.as_view()),
    path("invitations/accept", AcceptInvitationView.as_view()),
    path("push/vapid-public-key", VapidPublicKeyView.as_view()),
    path("push/subscriptions", PushSubscriptionView.as_view()),
    path("push/test", SendTestPushView.as_view()),
    path("push/stats", PushStatsView.as_view()),
    path("auth/csrf", CsrfView.as_view()),
    path("auth/config", AuthConfigView.as_view()),
    path("worker/", include("apps.workerapi.urls")),
    path("", include(router.urls)),
]
