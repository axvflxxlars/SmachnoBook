"""Тести реєстрації, логіну, оновлення токена і /users/me."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db

User = get_user_model()

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
ME_URL = "/api/v1/users/me"


@pytest.fixture
def register_payload():
    return {
        "username": "ivan",
        "first_name": "Іван",
        "last_name": "",
        "email": "ivan@example.com",
        "password": PASSWORD,
        "password_confirm": PASSWORD,
    }


# ---------- Реєстрація ----------


def test_register(anon_client, register_payload):
    response = anon_client.post(REGISTER_URL, register_payload, format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "ivan"
    assert body["is_staff"] is False
    assert "password" not in body

    user = User.objects.get(username="ivan")
    # У базі лише хеш, а не сам пароль
    assert user.password != PASSWORD
    assert user.check_password(PASSWORD)


def test_register_ignores_invalid_token(make_client, register_payload):
    client = make_client()
    client.credentials(HTTP_AUTHORIZATION="Bearer expired-or-broken")

    response = client.post(REGISTER_URL, register_payload, format="json")

    assert response.status_code == 201


@pytest.mark.parametrize(
    ("changes", "invalid_field"),
    [
        ({"username": ""}, "username"),
        ({"username": "x" * 151}, "username"),
        ({"email": "not-an-email"}, "email"),
        ({"email": ""}, "email"),
        ({"first_name": "x" * 151}, "first_name"),
        ({"password": "Sh0rt!", "password_confirm": "Sh0rt!"}, "password"),
        ({"password": "password123", "password_confirm": "password123"}, "password"),
        ({"password": "12345678901", "password_confirm": "12345678901"}, "password"),
        ({"password_confirm": "Other_Pass_2026"}, "password_confirm"),
    ],
)
def test_register_with_invalid_data(
    anon_client, register_payload, changes, invalid_field
):
    register_payload.update(changes)

    response = anon_client.post(REGISTER_URL, register_payload, format="json")

    assert response.status_code == 400
    assert invalid_field in response.json()["details"]
    assert not User.objects.filter(username=register_payload["username"]).exists()


def test_register_requires_fields(anon_client):
    response = anon_client.post(REGISTER_URL, {}, format="json")

    assert response.status_code == 400
    assert set(response.json()["details"]) == {
        "username",
        "email",
        "password",
        "password_confirm",
    }


def test_register_duplicate_username_and_email(anon_client, user, register_payload):
    register_payload["username"] = user.username
    # Email перевіряється без урахування регістру
    register_payload["email"] = user.email.upper()

    response = anon_client.post(REGISTER_URL, register_payload, format="json")

    assert response.status_code == 400
    assert set(response.json()["details"]) == {"username", "email"}


# ---------- Логін ----------


def test_login(anon_client, user):
    response = anon_client.post(
        LOGIN_URL, {"username": "olena", "password": PASSWORD}, format="json"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access"]
    assert body["refresh"]
    assert body["user"]["id"] == user.id


def test_login_with_wrong_password(anon_client, user):
    response = anon_client.post(
        LOGIN_URL, {"username": "olena", "password": "wrong"}, format="json"
    )

    assert response.status_code == 401
    assert response.json() == {"error": "Неправильне ім'я користувача або пароль."}


def test_login_without_fields(anon_client):
    response = anon_client.post(LOGIN_URL, {}, format="json")

    assert response.status_code == 400


# ---------- Оновлення токена ----------


def test_refresh_gives_working_access_token(anon_client, make_client, user):
    tokens = anon_client.post(
        LOGIN_URL, {"username": "olena", "password": PASSWORD}, format="json"
    ).json()

    response = anon_client.post(
        REFRESH_URL, {"refresh": tokens["refresh"]}, format="json"
    )

    assert response.status_code == 200
    client = make_client()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
    assert client.get(ME_URL).status_code == 200


def test_refresh_with_invalid_token(anon_client):
    response = anon_client.post(REFRESH_URL, {"refresh": "broken"}, format="json")

    assert response.status_code == 401


def test_refresh_does_not_accept_access_token(anon_client, user):
    access = str(AccessToken.for_user(user))

    response = anon_client.post(REFRESH_URL, {"refresh": access}, format="json")

    assert response.status_code == 401


# ---------- /users/me ----------


def test_me(user_client, user):
    response = user_client.get(ME_URL)

    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "username": "olena",
        "email": "olena@example.com",
        "first_name": "Олена",
        "last_name": "Коваль",
        "is_staff": False,
    }


def test_me_requires_authentication(anon_client):
    response = anon_client.get(ME_URL)

    assert response.status_code == 401
    assert "Authorization: Bearer" in response.json()["error"]


def test_me_with_expired_token(make_client, user):
    token = AccessToken.for_user(user)
    token.set_exp(lifetime=-timedelta(seconds=1))
    client = make_client()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = client.get(ME_URL)

    assert response.status_code == 401
    assert response.json() == {"error": "Токен недійсний або термін його дії минув."}
