"""drf-spectacular integration for the worker API.

Registers the custom `WorkerTokenAuthentication` as an OpenAPI security scheme
so `/api/v1/worker/*` endpoints advertise their `Authorization: Bearer pgw_...`
requirement. Imported from ``WorkerApiConfig.ready`` so spectacular discovers it.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class WorkerTokenScheme(OpenApiAuthenticationExtension):
    target_class = "apps.workerapi.auth.WorkerTokenAuthentication"
    name = "workerToken"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "description": (
                "Check-runner worker token. Send as "
                "`Authorization: Bearer pgw_...`."
            ),
        }
