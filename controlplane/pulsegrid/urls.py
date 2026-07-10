from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    # Social-login callbacks (Authentik) are served by regular allauth URLs;
    # HEADLESS_ONLY=True disables the HTML pages.
    path("accounts/", include("allauth.urls")),
    path("_allauth/", include("allauth.headless.urls")),
    path("api/v1/", include("pulsegrid.api_urls")),
    path("healthz", views.healthz),
    path("readyz", views.readyz),
]
