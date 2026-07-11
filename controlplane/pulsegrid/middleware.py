from . import views


class HealthCheckMiddleware:
    """Answers liveness/readiness probes before any other middleware runs.

    kube-probe addresses the pod by IP, so its Host header can never be in
    ALLOWED_HOSTS; CommonMiddleware would reject the request with a 400
    (DisallowedHost) before it reached the URL router. This middleware sits
    at the very top of the stack and short-circuits the health endpoints,
    which never need host validation, sessions or CSRF.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ("GET", "HEAD"):
            if request.path == "/healthz":
                return views.healthz(request)
            if request.path == "/readyz":
                return views.readyz(request)
        return self.get_response(request)
