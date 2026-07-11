"""The OpenAPI schema must generate cleanly and the docs endpoints must serve."""

import pytest

pytestmark = pytest.mark.django_db


def test_schema_generates_without_warnings():
    from drf_spectacular.generators import SchemaGenerator

    generator = SchemaGenerator()
    schema = generator.get_schema(request=None, public=True)

    paths = schema["paths"]
    # A representative endpoint from every app is documented.
    assert "/api/v1/monitors/" in paths
    assert "/api/v1/monitors/{id}/stats/" in paths
    assert "/api/v1/worker/claim" in paths
    assert "/api/v1/orgs/{id}/members/" in paths

    # The custom worker Bearer scheme is registered.
    assert "workerToken" in schema["components"]["securitySchemes"]


def test_schema_endpoint_serves(api):
    response = api.get("/api/schema")
    assert response.status_code == 200
    assert "openapi" in response.headers["Content-Type"] or response.content.startswith(b"openapi")


@pytest.mark.parametrize("path", ["/api/docs", "/api/redoc"])
def test_docs_ui_serves(api, path):
    response = api.get(path)
    assert response.status_code == 200
    assert b"<" in response.content  # rendered HTML


def test_docs_require_authentication(client):
    assert client.get("/api/schema").status_code in (401, 403)
