"""Фікстури, спільні для всіх тестів.

pytest знаходить цей файл автоматично: фікстуру достатньо вказати
як аргумент тестової функції, і pytest сам її створить.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from recipes.models import Category, Ingredient, Recipe, RecipeIngredient

PASSWORD = "Strong_Pass_2026"


# ---------- Користувачі ----------


@pytest.fixture
def user(django_user_model):
    """Звичайний користувач, автор рецепта з фікстури recipe."""
    return django_user_model.objects.create_user(
        username="olena",
        email="olena@example.com",
        password=PASSWORD,
        first_name="Олена",
        last_name="Коваль",
    )


@pytest.fixture
def other_user(django_user_model):
    """Інший звичайний користувач: не автор рецепта."""
    return django_user_model.objects.create_user(
        username="petro",
        email="petro@example.com",
        password=PASSWORD,
    )


@pytest.fixture
def admin(django_user_model):
    """Адміністратор (is_staff=True)."""
    return django_user_model.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password=PASSWORD,
    )


# ---------- Клієнти API ----------


@pytest.fixture
def make_client():
    """Фабрика клієнтів: make_client(user) — клієнт з JWT цього користувача."""

    def _make_client(user=None):
        client = APIClient()
        if user is not None:
            token = AccessToken.for_user(user)
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    return _make_client


@pytest.fixture
def anon_client(make_client):
    return make_client()


@pytest.fixture
def user_client(make_client, user):
    return make_client(user)


@pytest.fixture
def other_client(make_client, other_user):
    return make_client(other_user)


@pytest.fixture
def admin_api_client(make_client, admin):
    return make_client(admin)


# ---------- Дані ----------


@pytest.fixture
def category(db):
    return Category.objects.create(name="Супи")


@pytest.fixture
def ingredient(db):
    return Ingredient.objects.create(name="Буряк")


@pytest.fixture
def second_ingredient(db):
    return Ingredient.objects.create(name="Капуста")


@pytest.fixture
def recipe(user, category, ingredient):
    """Рецепт користувача user з одним інгредієнтом."""
    recipe = Recipe.objects.create(
        title="Борщ український",
        instructions="Відваріть м'ясо, додайте овочі.",
        cooking_time=90,
        servings=6,
        difficulty=Recipe.Difficulty.MEDIUM,
        author=user,
        category=category,
    )
    RecipeIngredient.objects.create(
        recipe=recipe, ingredient=ingredient, amount=2, unit="шт"
    )
    return recipe


@pytest.fixture
def recipe_payload(category, ingredient, second_ingredient):
    """Коректне тіло запиту для створення або оновлення рецепта."""
    return {
        "title": "Вареники з картоплею",
        "description": "Домашні вареники",
        "instructions": "Зліпіть вареники й зваріть.",
        "cooking_time": 40,
        "servings": 4,
        "difficulty": "easy",
        "image_url": "https://example.com/varenyky.jpg",
        "category_id": category.id,
        "ingredients": [
            {"ingredient_id": ingredient.id, "amount": 3, "unit": "шт"},
            {"ingredient_id": second_ingredient.id, "amount": 0.5, "unit": "кг"},
        ],
    }
