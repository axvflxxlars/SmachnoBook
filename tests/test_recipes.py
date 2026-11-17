"""Тести основного ресурсу: рецепти (/api/v1/recipes).

Ресурс підтримує GET, POST, PUT, DELETE і має різні права:
читати можуть усі, створювати — авторизовані, змінювати й видаляти —
лише автор рецепта або адміністратор.
"""

import pytest

from recipes.models import Ingredient, Recipe, RecipeIngredient

# Усім тестам у файлі потрібна тестова база даних
pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/recipes"


def detail_url(recipe_id):
    return f"/api/v1/recipes/{recipe_id}"


# ---------- GET /recipes: список ----------


def test_list_is_public(anon_client, recipe):
    response = anon_client.get(LIST_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["limit"] == 20
    item = body["data"][0]
    assert item["title"] == "Борщ український"
    assert item["category"] == {"id": recipe.category_id, "name": "Супи"}
    assert item["author"] == {"id": recipe.author_id, "name": "Олена Коваль"}
    # У списку немає довгих полів
    assert "instructions" not in item
    assert "ingredients" not in item


@pytest.mark.parametrize(
    ("query", "expected_titles"),
    [
        # SQLite не враховує регістр лише для латиниці, тому кирилицю
        # шукаємо в тому самому регістрі, що й у назві
        ("search=Борщ", ["Борщ український"]),
        ("search=україн", ["Борщ український"]),
        ("search=вареник", []),
        ("difficulty=medium", ["Борщ український"]),
        ("difficulty=easy", ["Салат"]),
        ("max_time=30", ["Салат"]),
    ],
)
def test_list_filters(anon_client, recipe, query, expected_titles):
    Recipe.objects.create(
        title="Салат",
        instructions="Наріжте овочі.",
        cooking_time=15,
        difficulty=Recipe.Difficulty.EASY,
        author=recipe.author,
        category=recipe.category,
    )

    response = anon_client.get(f"{LIST_URL}?{query}")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["data"]] == expected_titles


def test_list_filter_by_category_and_ingredient(anon_client, recipe, ingredient):
    response = anon_client.get(
        f"{LIST_URL}?category_id={recipe.category_id}&ingredient_id={ingredient.id}"
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == [recipe.id]


def test_list_sort_and_pagination(anon_client, recipe):
    quick = Recipe.objects.create(
        title="Канапки",
        instructions="Зберіть канапки.",
        cooking_time=10,
        author=recipe.author,
        category=recipe.category,
    )

    first_page = anon_client.get(f"{LIST_URL}?sort=time_asc&limit=1&page=1").json()
    second_page = anon_client.get(f"{LIST_URL}?sort=time_asc&limit=1&page=2").json()

    assert first_page["total"] == 2
    assert [item["id"] for item in first_page["data"]] == [quick.id]
    assert [item["id"] for item in second_page["data"]] == [recipe.id]


@pytest.mark.parametrize(
    "query",
    ["sort=best", "page=abc", "page=0", "limit=101", "difficulty=super"],
)
def test_list_invalid_query_params(anon_client, query):
    response = anon_client.get(f"{LIST_URL}?{query}")

    assert response.status_code == 400
    assert "error" in response.json()


# ---------- GET /recipes/{id}: один рецепт ----------


def test_retrieve_is_public(anon_client, recipe, ingredient):
    response = anon_client.get(detail_url(recipe.id))

    assert response.status_code == 200
    body = response.json()
    assert body["instructions"] == recipe.instructions
    assert body["ingredients"] == [
        {"id": ingredient.id, "name": "Буряк", "amount": 2.0, "unit": "шт"}
    ]


def test_retrieve_missing_recipe(anon_client):
    response = anon_client.get(detail_url(999))

    assert response.status_code == 404
    assert response.json() == {"error": "Рецепт з id=999 не знайдено."}


# ---------- POST /recipes: створення ----------


def test_create_requires_authentication(anon_client, recipe_payload):
    response = anon_client.post(LIST_URL, recipe_payload, format="json")

    assert response.status_code == 401
    assert not Recipe.objects.exists()


def test_create_with_invalid_token(make_client, recipe_payload):
    client = make_client()
    client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")

    response = client.post(LIST_URL, recipe_payload, format="json")

    assert response.status_code == 401
    assert response.json() == {"error": "Токен недійсний або термін його дії минув."}


def test_create_recipe(user_client, user, recipe_payload):
    response = user_client.post(LIST_URL, recipe_payload, format="json")

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Вареники з картоплею"
    assert body["author"] == {"id": user.id, "name": "Олена Коваль"}
    assert len(body["ingredients"]) == 2

    recipe = Recipe.objects.get(pk=body["id"])
    assert recipe.author == user
    assert recipe.recipe_ingredients.count() == 2


def test_create_ignores_author_from_body(user_client, user, other_user, recipe_payload):
    """Автора не можна підмінити: він завжди береться з токена."""
    recipe_payload["author_id"] = other_user.id

    response = user_client.post(LIST_URL, recipe_payload, format="json")

    assert response.status_code == 201
    assert Recipe.objects.get(pk=response.json()["id"]).author == user


@pytest.mark.parametrize(
    ("changes", "invalid_field"),
    [
        ({"title": ""}, "title"),
        ({"cooking_time": 0}, "cooking_time"),
        ({"difficulty": "super"}, "difficulty"),
        ({"category_id": 999}, "category_id"),
        ({"ingredients": []}, "ingredients"),
        ({"image_url": "not-a-url"}, "image_url"),
    ],
)
def test_create_with_invalid_data(user_client, recipe_payload, changes, invalid_field):
    recipe_payload.update(changes)

    response = user_client.post(LIST_URL, recipe_payload, format="json")

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "Некоректні дані. Перевірте поля запиту."
    assert invalid_field in body["details"]
    assert not Recipe.objects.exists()


def test_create_with_duplicate_ingredients(user_client, recipe_payload, ingredient):
    recipe_payload["ingredients"] = [
        {"ingredient_id": ingredient.id, "amount": 1, "unit": "шт"},
        {"ingredient_id": ingredient.id, "amount": 2, "unit": "шт"},
    ]

    response = user_client.post(LIST_URL, recipe_payload, format="json")

    assert response.status_code == 400
    assert response.json()["details"]["ingredients"] == [
        "Інгредієнти в рецепті не повинні повторюватись."
    ]


def test_create_with_missing_ingredient(user_client, recipe_payload):
    recipe_payload["ingredients"] = [{"ingredient_id": 999, "amount": 1, "unit": "шт"}]

    response = user_client.post(LIST_URL, recipe_payload, format="json")

    assert response.status_code == 400
    assert "ingredients" in response.json()["details"]


# ---------- PUT /recipes/{id}: оновлення ----------


def test_author_can_update_recipe(user_client, recipe, recipe_payload, ingredient):
    response = user_client.put(detail_url(recipe.id), recipe_payload, format="json")

    assert response.status_code == 200
    recipe.refresh_from_db()
    assert recipe.title == "Вареники з картоплею"
    assert recipe.cooking_time == 40
    # Список інгредієнтів замінено повністю
    assert recipe.recipe_ingredients.count() == 2
    assert recipe.recipe_ingredients.get(ingredient=ingredient).unit == "шт"


def test_admin_can_update_any_recipe(admin_api_client, recipe, recipe_payload, user):
    response = admin_api_client.put(
        detail_url(recipe.id), recipe_payload, format="json"
    )

    assert response.status_code == 200
    recipe.refresh_from_db()
    assert recipe.title == "Вареники з картоплею"
    # Автор не змінюється, навіть якщо рецепт редагує адміністратор
    assert recipe.author == user


def test_other_user_cannot_update_recipe(other_client, recipe, recipe_payload):
    response = other_client.put(detail_url(recipe.id), recipe_payload, format="json")

    assert response.status_code == 403
    assert response.json() == {
        "error": "Змінювати й видаляти рецепт може лише його автор або адміністратор."
    }
    recipe.refresh_from_db()
    assert recipe.title == "Борщ український"


def test_update_requires_authentication(anon_client, recipe, recipe_payload):
    response = anon_client.put(detail_url(recipe.id), recipe_payload, format="json")

    assert response.status_code == 401


def test_update_missing_recipe(user_client, recipe_payload):
    response = user_client.put(detail_url(999), recipe_payload, format="json")

    assert response.status_code == 404


def test_update_with_invalid_data(user_client, recipe, recipe_payload):
    recipe_payload["cooking_time"] = -5

    response = user_client.put(detail_url(recipe.id), recipe_payload, format="json")

    assert response.status_code == 400
    assert "cooking_time" in response.json()["details"]
    recipe.refresh_from_db()
    assert recipe.cooking_time == 90


# ---------- DELETE /recipes/{id}: видалення ----------


def test_author_can_delete_recipe(user_client, recipe, ingredient):
    response = user_client.delete(detail_url(recipe.id))

    assert response.status_code == 204
    assert not Recipe.objects.filter(pk=recipe.id).exists()
    # Рядки зв'язку видалено (CASCADE), а сам інгредієнт лишився
    assert not RecipeIngredient.objects.exists()
    assert Ingredient.objects.filter(pk=ingredient.id).exists()


def test_admin_can_delete_any_recipe(admin_api_client, recipe):
    response = admin_api_client.delete(detail_url(recipe.id))

    assert response.status_code == 204
    assert not Recipe.objects.exists()


def test_other_user_cannot_delete_recipe(other_client, recipe):
    response = other_client.delete(detail_url(recipe.id))

    assert response.status_code == 403
    assert Recipe.objects.filter(pk=recipe.id).exists()


def test_delete_requires_authentication(anon_client, recipe):
    response = anon_client.delete(detail_url(recipe.id))

    assert response.status_code == 401
    assert Recipe.objects.filter(pk=recipe.id).exists()


def test_delete_missing_recipe(user_client):
    response = user_client.delete(detail_url(999))

    assert response.status_code == 404


def test_method_not_allowed(user_client, recipe):
    response = user_client.patch(detail_url(recipe.id), {"title": "X"}, format="json")

    assert response.status_code == 405
