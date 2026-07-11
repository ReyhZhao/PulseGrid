from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Social-login callbacks (Authentik) are served by regular allauth URLs;
    # HEADLESS_ONLY=True disables the HTML pages.
    path("accounts/", include("allauth.urls")),
    path("_allauth/", include("allauth.headless.urls")),
    path("api/v1/", include("pulsegrid.api_urls")),
    # OpenAPI schema + interactive docs.
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("healthz", views.healthz),
    path("readyz", views.readyz),
]
