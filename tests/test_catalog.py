"""Категорії, інгредієнти й автори: права за ролями та конфлікти 409."""

import pytest

from recipes.models import Category, Ingredient

pytestmark = pytest.mark.django_db


# ---------- Категорії: змінювати може лише адміністратор ----------


def test_categories_list_is_public(anon_client, category):
    response = anon_client.get("/api/v1/categories")

    assert response.status_code == 200
    assert response.json() == {"data": [{"id": category.id, "name": "Супи"}]}


@pytest.mark.parametrize(
    ("client_fixture", "expected_status"),
    [
        ("anon_client", 401),
        ("user_client", 403),
        ("admin_api_client", 201),
    ],
)
def test_create_category_permissions(request, client_fixture, expected_status):
    # request.getfixturevalue дозволяє вибрати фікстуру за назвою з параметра
    client = request.getfixturevalue(client_fixture)

    response = client.post("/api/v1/categories", {"name": "Десерти"}, format="json")

    assert response.status_code == expected_status
    assert Category.objects.filter(name="Десерти").exists() == (expected_status == 201)


def test_create_duplicate_category(admin_api_client, category):
    response = admin_api_client.post(
        "/api/v1/categories", {"name": "Супи"}, format="json"
    )

    assert response.status_code == 400
    assert "name" in response.json()["details"]


def test_admin_updates_category(admin_api_client, category):
    response = admin_api_client.put(
        f"/api/v1/categories/{category.id}", {"name": "Перші страви"}, format="json"
    )

    assert response.status_code == 200
    category.refresh_from_db()
    assert category.name == "Перші страви"


def test_delete_category_with_recipes_conflict(admin_api_client, recipe):
    response = admin_api_client.delete(f"/api/v1/categories/{recipe.category_id}")

    assert response.status_code == 409
    assert "рецептів: 1" in response.json()["error"]
    assert Category.objects.filter(pk=recipe.category_id).exists()


def test_delete_empty_category(admin_api_client, category):
    response = admin_api_client.delete(f"/api/v1/categories/{category.id}")

    assert response.status_code == 204
    assert not Category.objects.exists()


def test_get_missing_category(anon_client):
    assert anon_client.get("/api/v1/categories/999").status_code == 404


# ---------- Інгредієнти: створювати може кожен авторизований ----------


def test_user_creates_ingredient(user_client):
    response = user_client.post(
        "/api/v1/ingredients", {"name": "Цибуля"}, format="json"
    )

    assert response.status_code == 201
    assert Ingredient.objects.filter(name="Цибуля").exists()


def test_ingredients_search(anon_client, ingredient, second_ingredient):
    response = anon_client.get("/api/v1/ingredients?search=Бур")

    assert response.status_code == 200
    assert [item["name"] for item in response.json()["data"]] == ["Буряк"]


def test_user_cannot_delete_ingredient(user_client, ingredient):
    response = user_client.delete(f"/api/v1/ingredients/{ingredient.id}")

    assert response.status_code == 403
    assert Ingredient.objects.filter(pk=ingredient.id).exists()


def test_admin_updates_ingredient(admin_api_client, ingredient):
    response = admin_api_client.put(
        f"/api/v1/ingredients/{ingredient.id}",
        {"name": "Буряк столовий"},
        format="json",
    )

    assert response.status_code == 200
    assert response.json() == {"id": ingredient.id, "name": "Буряк столовий"}


def test_delete_ingredient_in_use_conflict(admin_api_client, recipe, ingredient):
    response = admin_api_client.delete(f"/api/v1/ingredients/{ingredient.id}")

    assert response.status_code == 409
    assert Ingredient.objects.filter(pk=ingredient.id).exists()


def test_admin_deletes_unused_ingredient(admin_api_client, second_ingredient):
    response = admin_api_client.delete(f"/api/v1/ingredients/{second_ingredient.id}")

    assert response.status_code == 204


def test_get_ingredient(anon_client, ingredient):
    response = anon_client.get(f"/api/v1/ingredients/{ingredient.id}")

    assert response.status_code == 200
    assert response.json() == {"id": ingredient.id, "name": "Буряк"}


# ---------- Рецепти категорії, інгредієнта, автора ----------


@pytest.mark.parametrize("kind", ["categories", "ingredients", "users"])
def test_related_recipes(anon_client, recipe, ingredient, kind):
    parent_id = {
        "categories": recipe.category_id,
        "ingredients": ingredient.id,
        "users": recipe.author_id,
    }[kind]

    response = anon_client.get(f"/api/v1/{kind}/{parent_id}/recipes")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == [recipe.id]


@pytest.mark.parametrize("kind", ["categories", "ingredients", "users"])
def test_related_recipes_of_missing_parent(anon_client, kind):
    assert anon_client.get(f"/api/v1/{kind}/999/recipes").status_code == 404


def test_author_page(anon_client, recipe, user):
    response = anon_client.get(f"/api/v1/users/{user.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "name": "Олена Коваль",
        "recipes_count": 1,
    }
