from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.core.exceptions import MiddlewareNotUsed


class DevAutoLoginMiddleware:
    """Local-dev convenience: authenticate every request as the first
    superuser so no login is needed. Enabled only when both DJANGO_DEBUG and
    DEV_AUTO_LOGIN are set — never enable this in a deployed environment."""

    def __init__(self, get_response):
        if not (settings.DEBUG and settings.DEV_AUTO_LOGIN):
            raise MiddlewareNotUsed
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            user = get_user_model().objects.filter(is_superuser=True, is_active=True).first()
            if user is not None:
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return self.get_response(request)
