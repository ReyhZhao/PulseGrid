from django.apps import AppConfig


class WorkerApiConfig(AppConfig):
    name = "apps.workerapi"
    label = "workerapi"

    def ready(self):
        # Register the worker-token OpenAPI security scheme with spectacular.
        from . import schema  # noqa: F401
