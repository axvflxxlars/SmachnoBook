"""Спільні елементи OpenAPI-документації.

Тут лише опис для drf-spectacular: ці серіалізатори не використовуються
для обробки запитів, вони описують формат відповідей, який в'юхи
формують вручну (сторінки списків і помилки).
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    inline_serializer,
)
from rest_framework import serializers

from .models import Recipe

# ---------- Помилки ----------

ErrorSerializer = inline_serializer(
    name="Error",
    fields={"error": serializers.CharField()},
)

ValidationErrorSerializer = inline_serializer(
    name="ValidationError",
    fields={
        "error": serializers.CharField(),
        "details": serializers.DictField(
            child=serializers.ListField(child=serializers.CharField()),
            help_text="Помилки для кожного поля запиту",
        ),
    },
)


def error_response(description, message):
    return OpenApiResponse(
        response=ErrorSerializer,
        description=description,
        examples=[OpenApiExample(description, value={"error": message})],
    )


def validation_error_response(details):
    return OpenApiResponse(
        response=ValidationErrorSerializer,
        description="Некоректні дані запиту",
        examples=[
            OpenApiExample(
                "Помилка валідації",
                value={
                    "error": "Некоректні дані. Перевірте поля запиту.",
                    "details": details,
                },
            )
        ],
    )


UNAUTHORIZED = error_response(
    "Немає токена, токен недійсний або прострочений",
    "Потрібна авторизація. Передайте access-токен у заголовку "
    "Authorization: Bearer <token>.",
)
FORBIDDEN_ADMIN = error_response(
    "Дія доступна лише адміністратору",
    "Ця дія доступна лише адміністратору.",
)
BAD_QUERY = error_response(
    "Некоректні query-параметри",
    "Параметр sort має бути одним із: newest, time_asc.",
)


def not_found(label):
    return error_response(f"{label} не знайдено", f"{label} з id=999 не знайдено.")


# ---------- Сторінки списків ----------


def page_of(item_serializer, name):
    """Описує відповідь функції paginate(): data, page, limit, total."""
    return inline_serializer(
        name=name,
        fields={
            "data": item_serializer(many=True),
            "page": serializers.IntegerField(),
            "limit": serializers.IntegerField(),
            "total": serializers.IntegerField(help_text="Загальна кількість"),
        },
    )


# ---------- Query-параметри ----------

PAGINATION_PARAMETERS = [
    OpenApiParameter(
        "page", OpenApiTypes.INT, description="Номер сторінки (від 1)", default=1
    ),
    OpenApiParameter(
        "limit",
        OpenApiTypes.INT,
        description="Кількість на сторінці (від 1 до 100)",
        default=20,
    ),
]

SORT_PARAMETER = OpenApiParameter(
    "sort",
    OpenApiTypes.STR,
    enum=["newest", "time_asc"],
    default="newest",
    description="Сортування: спочатку нові або за часом приготування",
)

RECIPE_FILTER_PARAMETERS = [
    OpenApiParameter("search", OpenApiTypes.STR, description="Пошук за назвою рецепта"),
    OpenApiParameter(
        "category_id", OpenApiTypes.INT, description="Рецепти цієї категорії"
    ),
    OpenApiParameter(
        "ingredient_id",
        OpenApiTypes.INT,
        description="Рецепти, де використано цей інгредієнт",
    ),
    OpenApiParameter(
        "difficulty",
        OpenApiTypes.STR,
        enum=Recipe.Difficulty.values,
        description="Складність",
    ),
    OpenApiParameter(
        "max_time",
        OpenApiTypes.INT,
        description="Максимальний час приготування, хв",
    ),
    SORT_PARAMETER,
    *PAGINATION_PARAMETERS,
]
