"""drf-spectacular integration for read-only API tokens.

Registers `ReadTokenAuthentication` as an OpenAPI security scheme so
tenant-scoped endpoints advertise their `Authorization: Bearer pgr_...`
alternative. Imported from ``ApiTokensConfig.ready`` so spectacular
discovers it.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ReadTokenScheme(OpenApiAuthenticationExtension):
    target_class = "apps.apitokens.auth.ReadTokenAuthentication"
    name = "readToken"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "description": (
                "Read-only, organization-scoped API token. Send as "
                "`Authorization: Bearer pgr_...`. Valid on safe (GET/HEAD/OPTIONS) "
                "requests only, and scoped to the one organization it was issued for."
            ),
        }
