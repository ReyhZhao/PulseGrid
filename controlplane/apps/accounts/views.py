from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import me_payload


class MeView(APIView):
    def get(self, request):
        return Response(me_payload(request.user))


@method_decorator(ensure_csrf_cookie, name="get")
class CsrfView(APIView):
    """Sets the CSRF cookie so the SPA can make unsafe requests."""

    permission_classes = [AllowAny]

    def get(self, request):
        return JsonResponse({"detail": "CSRF cookie set"})
