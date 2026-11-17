"""Логування: потрібні події потрапляють у лог, паролі й токени — ні.

Фікстура caplog (вбудована в pytest) перехоплює записи логів під час тесту.
"""

import logging

import pytest

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_registration_is_logged_without_password(anon_client, caplog):
    caplog.set_level(logging.INFO)

    anon_client.post(
        "/api/v1/auth/register",
        {
            "username": "ivan",
            "email": "ivan@example.com",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        },
        format="json",
    )

    assert "Зареєстровано користувача" in caplog.text
    assert PASSWORD not in caplog.text


def test_login_logs_no_tokens(anon_client, user, caplog):
    caplog.set_level(logging.INFO)

    tokens = anon_client.post(
        "/api/v1/auth/login",
        {"username": "olena", "password": PASSWORD},
        format="json",
    ).json()

    assert f"Користувач id={user.id} увійшов" in caplog.text
    assert tokens["access"] not in caplog.text
    assert tokens["refresh"] not in caplog.text
    assert PASSWORD not in caplog.text


def test_failed_login_is_warning(anon_client, user, caplog):
    caplog.set_level(logging.INFO)

    anon_client.post(
        "/api/v1/auth/login",
        {"username": "olena", "password": "wrong-password"},
        format="json",
    )

    record = caplog.records[-1]
    assert record.levelno == logging.WARNING
    assert "401 POST /api/v1/auth/login" in record.getMessage()
    assert "wrong-password" not in caplog.text


def test_forbidden_action_is_warning(other_client, other_user, recipe, caplog):
    caplog.set_level(logging.INFO)

    other_client.delete(f"/api/v1/recipes/{recipe.id}")

    record = caplog.records[-1]
    assert record.levelno == logging.WARNING
    assert f"user={other_user.id}" in record.getMessage()


def test_validation_error_logs_only_field_names(user_client, caplog):
    caplog.set_level(logging.INFO)

    user_client.post("/api/v1/recipes", {"title": "Секретна назва"}, format="json")

    record = caplog.records[-1]
    assert record.levelno == logging.INFO
    assert "некоректні поля" in record.getMessage()
    assert "Секретна назва" not in caplog.text


def test_recipe_creation_is_logged(user_client, user, recipe_payload, caplog):
    caplog.set_level(logging.INFO)

    response = user_client.post("/api/v1/recipes", recipe_payload, format="json")

    assert (
        f"Створено рецепт id={response.json()['id']} автором id={user.id}"
        in caplog.text
    )
