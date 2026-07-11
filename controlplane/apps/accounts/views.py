from django.middleware.csrf import get_token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import me_payload


class MeView(APIView):
    def get(self, request):
        return Response(me_payload(request.user))


class CsrfView(APIView):
    """Hands the SPA a CSRF token. get_token() both marks the csrftoken
    cookie for (re)setting and returns the value, so clients that cannot
    read the cookie (races, exotic cookie policies) can fall back to the
    response body."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrftoken": get_token(request)})
