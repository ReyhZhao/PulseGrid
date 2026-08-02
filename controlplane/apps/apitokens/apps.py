from django.apps import AppConfig


class ApiTokensConfig(AppConfig):
    name = "apps.apitokens"
    label = "apitokens"

    def ready(self):
        # Register the read-token OpenAPI security scheme with spectacular.
        from . import schema  # noqa: F401
