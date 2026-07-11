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
from apps.alerts.views import AlertEventViewSet, NotificationChannelViewSet
from apps.audit.views import AuditEventViewSet
from apps.monitors.views import MonitorViewSet, RegionViewSet

router = DefaultRouter()
router.register("monitors", MonitorViewSet, basename="monitor")
router.register("regions", RegionViewSet, basename="region")
router.register("channels", NotificationChannelViewSet, basename="channel")
router.register("alerts", AlertEventViewSet, basename="alert")
router.register("audit", AuditEventViewSet, basename="audit")
router.register("orgs", OrganizationViewSet, basename="org")

urlpatterns = [
    path("me", MeView.as_view()),
    path("onboarding/complete", OnboardingCompleteView.as_view()),
    path("invitations/accept", AcceptInvitationView.as_view()),
    path("auth/csrf", CsrfView.as_view()),
    path("auth/config", AuthConfigView.as_view()),
    path("worker/", include("apps.workerapi.urls")),
    path("", include(router.urls)),
]
