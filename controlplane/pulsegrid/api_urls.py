from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts.views import CsrfView, MeView
from apps.alerts.views import AlertEventViewSet, NotificationChannelViewSet
from apps.monitors.views import MonitorViewSet, RegionViewSet

router = DefaultRouter()
router.register("monitors", MonitorViewSet, basename="monitor")
router.register("regions", RegionViewSet, basename="region")
router.register("channels", NotificationChannelViewSet, basename="channel")
router.register("alerts", AlertEventViewSet, basename="alert")

urlpatterns = [
    path("me", MeView.as_view()),
    path("auth/csrf", CsrfView.as_view()),
    path("worker/", include("apps.workerapi.urls")),
    path("", include(router.urls)),
]
