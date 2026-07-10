from django.urls import path

from .views import ClaimTasksView, HeartbeatView, SubmitResultsView

urlpatterns = [
    path("claim", ClaimTasksView.as_view()),
    path("results", SubmitResultsView.as_view()),
    path("heartbeat", HeartbeatView.as_view()),
]
