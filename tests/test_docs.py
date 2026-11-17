"""Документація API доступна і відповідає реалізації."""

import pytest

pytestmark = pytest.mark.django_db


def test_openapi_schema(anon_client):
    response = anon_client.get("/api/schema?format=json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "SmachnoBook API"
    assert {"/api/v1/recipes", "/api/v1/recipes/{id}", "/api/v1/auth/login"} <= set(
        schema["paths"]
    )
    recipe_detail = schema["paths"]["/api/v1/recipes/{id}"]
    assert set(recipe_detail) >= {"get", "put", "delete"}
    assert {"401", "403", "404"} <= set(recipe_detail["delete"]["responses"])


@pytest.mark.parametrize("url", ["/api/docs", "/api/redoc"])
def test_documentation_pages(anon_client, url):
    assert anon_client.get(url).status_code == 200
