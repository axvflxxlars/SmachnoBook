import logging

from django.contrib.auth import get_user_model
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsAdminOrReadOnly, IsAuthorOrAdminOrReadOnly

from .exceptions import ConflictError
from .models import Category, Ingredient, Recipe
from .openapi import (
    BAD_QUERY,
    FORBIDDEN_ADMIN,
    PAGINATION_PARAMETERS,
    RECIPE_FILTER_PARAMETERS,
    SORT_PARAMETER,
    UNAUTHORIZED,
    error_response,
    not_found,
    page_of,
    validation_error_response,
)
from .serializers import (
    CategorySerializer,
    IngredientSerializer,
    RecipeListSerializer,
    RecipeSerializer,
    UserSerializer,
)

User = get_user_model()

# Логер з назвою модуля ("recipes.views"). Налаштування — LOGGING у settings.py
logger = logging.getLogger(__name__)

MAX_LIMIT = 100
SORT_OPTIONS = {
    "newest": ("-created_at", "-id"),
    "time_asc": ("cooking_time", "id"),
}


def get_or_404(queryset, pk, label):
    try:
        return queryset.get(pk=pk)
    except queryset.model.DoesNotExist:
        raise NotFound(f"{label} з id={pk} не знайдено.") from None


def int_param(request, name, default=None):
    raw = request.query_params.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValidationError(f"Параметр {name} має бути цілим числом.") from None
    if value < 1:
        raise ValidationError(f"Параметр {name} має бути не менше 1.")
    return value


def paginate(request, queryset, serializer_class):
    page = int_param(request, "page", default=1)
    limit = int_param(request, "limit", default=20)
    if limit > MAX_LIMIT:
        raise ValidationError(f"Параметр limit не може перевищувати {MAX_LIMIT}.")
    start = (page - 1) * limit
    items = queryset[start : start + limit]
    return {
        "data": serializer_class(items, many=True).data,
        "page": page,
        "limit": limit,
        "total": queryset.count(),
    }


def recipe_queryset():
    return Recipe.objects.select_related("category", "author")


def filter_recipes(request, queryset):
    params = request.query_params

    search = params.get("search")
    if search:
        queryset = queryset.filter(title__icontains=search)

    category_id = int_param(request, "category_id")
    if category_id:
        queryset = queryset.filter(category_id=category_id)

    ingredient_id = int_param(request, "ingredient_id")
    if ingredient_id:
        queryset = queryset.filter(ingredients__id=ingredient_id)

    difficulty = params.get("difficulty")
    if difficulty:
        if difficulty not in Recipe.Difficulty.values:
            allowed = ", ".join(Recipe.Difficulty.values)
            raise ValidationError(f"Параметр difficulty має бути одним із: {allowed}.")
        queryset = queryset.filter(difficulty=difficulty)

    max_time = int_param(request, "max_time")
    if max_time:
        queryset = queryset.filter(cooking_time__lte=max_time)

    return queryset


def sort_recipes(request, queryset):
    sort = request.query_params.get("sort", "newest")
    if sort not in SORT_OPTIONS:
        allowed = ", ".join(SORT_OPTIONS)
        raise ValidationError(f"Параметр sort має бути одним із: {allowed}.")
    return queryset.order_by(*SORT_OPTIONS[sort])


# ---------- Документація: спільні приклади ----------

# Читання доступне без токена. drf-spectacular не знає логіки наших
# permission-класів, тому для GET-запитів вказуємо це явно
PUBLIC = []

RECIPE_REQUEST_EXAMPLE = OpenApiExample(
    "Новий рецепт",
    request_only=True,
    value={
        "title": "Борщ український",
        "description": "Класичний борщ з буряком і капустою",
        "instructions": "1. Відваріть м'ясо. 2. Додайте овочі.",
        "cooking_time": 90,
        "servings": 6,
        "difficulty": "medium",
        "image_url": "https://example.com/borsch.jpg",
        "category_id": 1,
        "ingredients": [
            {"ingredient_id": 1, "amount": 2, "unit": "шт"},
            {"ingredient_id": 2, "amount": 300, "unit": "г"},
        ],
    },
)

RECIPE_RESPONSE_EXAMPLE = OpenApiExample(
    "Рецепт",
    response_only=True,
    value={
        "id": 1,
        "title": "Борщ український",
        "description": "Класичний борщ з буряком і капустою",
        "instructions": "1. Відваріть м'ясо. 2. Додайте овочі.",
        "cooking_time": 90,
        "servings": 6,
        "difficulty": "medium",
        "image_url": "https://example.com/borsch.jpg",
        "created_at": "2026-11-16T12:00:00Z",
        "category": {"id": 1, "name": "Супи"},
        "author": {"id": 2, "name": "Олена Коваль"},
        "ingredients": [
            {"id": 1, "name": "Буряк", "amount": 2.0, "unit": "шт"},
            {"id": 2, "name": "Капуста", "amount": 300.0, "unit": "г"},
        ],
    },
)

RECIPE_VALIDATION_ERROR = validation_error_response(
    {
        "cooking_time": ["Переконайтесь, що це значення більше чи дорівнює 1."],
        "ingredients": ["Цей список не може бути порожнім."],
    }
)

FORBIDDEN_NOT_AUTHOR = error_response(
    "Рецепт належить іншому користувачу",
    "Змінювати й видаляти рецепт може лише його автор або адміністратор.",
)

RecipePage = page_of(RecipeListSerializer, "RecipePage")
IngredientPage = page_of(IngredientSerializer, "IngredientPage")


# ---------- Рецепти ----------


@extend_schema(tags=["Рецепти"])
class RecipeListView(APIView):
    # Список бачать усі, створювати рецепти можуть лише авторизовані
    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(
        summary="Список рецептів",
        auth=PUBLIC,
        operation_id="recipes_list",
        description="Пошук, фільтри, сортування й пагінація. Доступно всім.",
        parameters=RECIPE_FILTER_PARAMETERS,
        responses={200: RecipePage, 400: BAD_QUERY},
    )
    def get(self, request):
        logger.debug("Список рецептів, параметри: %s", dict(request.query_params))
        recipes = filter_recipes(request, recipe_queryset())
        recipes = sort_recipes(request, recipes)
        return Response(paginate(request, recipes, RecipeListSerializer))

    @extend_schema(
        summary="Створити рецепт",
        description=(
            "Потрібна авторизація. Автором стає поточний користувач "
            "(визначається за токеном), поле author_id не передається."
        ),
        request=RecipeSerializer,
        responses={
            201: RecipeSerializer,
            400: RECIPE_VALIDATION_ERROR,
            401: UNAUTHORIZED,
        },
        examples=[RECIPE_REQUEST_EXAMPLE, RECIPE_RESPONSE_EXAMPLE],
    )
    def post(self, request):
        serializer = RecipeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Автор рецепта — поточний користувач, його не передають у тілі
        recipe = serializer.save(author=request.user)
        logger.info("Створено рецепт id=%s автором id=%s", recipe.id, request.user.id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Рецепти"])
class RecipeDetailView(APIView):
    # Читати можуть усі, змінювати й видаляти — автор або адміністратор
    permission_classes = [IsAuthorOrAdminOrReadOnly]

    @extend_schema(
        summary="Отримати рецепт",
        auth=PUBLIC,
        description="Повна інформація про рецепт з інгредієнтами. Доступно всім.",
        responses={200: RecipeSerializer, 404: not_found("Рецепт")},
        examples=[RECIPE_RESPONSE_EXAMPLE],
    )
    def get(self, request, pk):
        queryset = recipe_queryset().prefetch_related("recipe_ingredients__ingredient")
        recipe = get_or_404(queryset, pk, "Рецепт")
        return Response(RecipeSerializer(recipe).data)

    @extend_schema(
        summary="Оновити рецепт",
        description=(
            "Повна заміна рецепта, список інгредієнтів замінюється повністю. "
            "Доступно автору рецепта або адміністратору."
        ),
        request=RecipeSerializer,
        responses={
            200: RecipeSerializer,
            400: RECIPE_VALIDATION_ERROR,
            401: UNAUTHORIZED,
            403: FORBIDDEN_NOT_AUTHOR,
            404: not_found("Рецепт"),
        },
        examples=[RECIPE_REQUEST_EXAMPLE, RECIPE_RESPONSE_EXAMPLE],
    )
    def put(self, request, pk):
        recipe = get_or_404(recipe_queryset(), pk, "Рецепт")
        self.check_object_permissions(request, recipe)
        serializer = RecipeSerializer(recipe, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info("Оновлено рецепт id=%s користувачем id=%s", pk, request.user.id)
        return Response(serializer.data)

    @extend_schema(
        summary="Видалити рецепт",
        description="Доступно автору рецепта або адміністратору.",
        responses={
            204: OpenApiResponse(description="Рецепт видалено"),
            401: UNAUTHORIZED,
            403: FORBIDDEN_NOT_AUTHOR,
            404: not_found("Рецепт"),
        },
    )
    def delete(self, request, pk):
        recipe = get_or_404(recipe_queryset(), pk, "Рецепт")
        self.check_object_permissions(request, recipe)
        recipe.delete()
        logger.info("Видалено рецепт id=%s користувачем id=%s", pk, request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------- Категорії ----------

CATEGORY_CONFLICT = error_response(
    "У категорії є рецепти",
    "Неможливо видалити категорію «Супи», оскільки в ній рецептів: 3. "
    "Спочатку видаліть їх або перенесіть в іншу категорію.",
)
NAME_VALIDATION_ERROR = validation_error_response(
    {"name": ["Це поле не може бути порожнім."]}
)


@extend_schema(tags=["Категорії"])
class CategoryListView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    @extend_schema(
        summary="Список категорій",
        auth=PUBLIC,
        operation_id="categories_list",
        responses={
            200: inline_serializer(
                name="CategoryList",
                fields={"data": CategorySerializer(many=True)},
            )
        },
    )
    def get(self, request):
        serializer = CategorySerializer(Category.objects.all(), many=True)
        return Response({"data": serializer.data})

    @extend_schema(
        summary="Створити категорію",
        description="Лише для адміністратора.",
        request=CategorySerializer,
        responses={
            201: CategorySerializer,
            400: NAME_VALIDATION_ERROR,
            401: UNAUTHORIZED,
            403: FORBIDDEN_ADMIN,
        },
    )
    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        logger.info(
            "Створено категорію id=%s «%s» користувачем id=%s",
            category.id,
            category.name,
            request.user.id,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Категорії"])
class CategoryDetailView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    @extend_schema(
        summary="Отримати категорію",
        auth=PUBLIC,
        responses={200: CategorySerializer, 404: not_found("Категорію")},
    )
    def get(self, request, pk):
        category = get_or_404(Category.objects.all(), pk, "Категорію")
        return Response(CategorySerializer(category).data)

    @extend_schema(
        summary="Перейменувати категорію",
        description="Лише для адміністратора.",
        request=CategorySerializer,
        responses={
            200: CategorySerializer,
            400: NAME_VALIDATION_ERROR,
            401: UNAUTHORIZED,
            403: FORBIDDEN_ADMIN,
            404: not_found("Категорію"),
        },
    )
    def put(self, request, pk):
        category = get_or_404(Category.objects.all(), pk, "Категорію")
        serializer = CategorySerializer(category, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info("Оновлено категорію id=%s користувачем id=%s", pk, request.user.id)
        return Response(serializer.data)

    @extend_schema(
        summary="Видалити категорію",
        description="Лише для адміністратора. Не можна видалити категорію з рецептами.",
        responses={
            204: OpenApiResponse(description="Категорію видалено"),
            401: UNAUTHORIZED,
            403: FORBIDDEN_ADMIN,
            404: not_found("Категорію"),
            409: CATEGORY_CONFLICT,
        },
    )
    def delete(self, request, pk):
        category = get_or_404(Category.objects.all(), pk, "Категорію")
        count = category.recipes.count()
        if count:
            raise ConflictError(
                f"Неможливо видалити категорію «{category.name}», "
                f"оскільки в ній рецептів: {count}. "
                "Спочатку видаліть їх або перенесіть в іншу категорію."
            )
        category.delete()
        logger.info("Видалено категорію id=%s користувачем id=%s", pk, request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------- Інгредієнти ----------

INGREDIENT_CONFLICT = error_response(
    "Інгредієнт використовується в рецептах",
    "Неможливо видалити інгредієнт «Буряк», оскільки він використовується "
    "в рецептах: 2.",
)


@extend_schema(tags=["Інгредієнти"])
class IngredientListView(APIView):
    # Новий інгредієнт може додати будь-який авторизований автор рецепта
    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(
        summary="Список інгредієнтів",
        auth=PUBLIC,
        operation_id="ingredients_list",
        parameters=[
            OpenApiParameter("search", OpenApiTypes.STR, description="Пошук за назвою"),
            *PAGINATION_PARAMETERS,
        ],
        responses={200: IngredientPage, 400: BAD_QUERY},
    )
    def get(self, request):
        ingredients = Ingredient.objects.all()
        search = request.query_params.get("search")
        if search:
            ingredients = ingredients.filter(name__icontains=search)
        return Response(paginate(request, ingredients, IngredientSerializer))

    @extend_schema(
        summary="Створити інгредієнт",
        description="Доступно будь-якому авторизованому користувачу.",
        request=IngredientSerializer,
        responses={
            201: IngredientSerializer,
            400: NAME_VALIDATION_ERROR,
            401: UNAUTHORIZED,
        },
    )
    def post(self, request):
        serializer = IngredientSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ingredient = serializer.save()
        logger.info(
            "Створено інгредієнт id=%s «%s» користувачем id=%s",
            ingredient.id,
            ingredient.name,
            request.user.id,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Інгредієнти"])
class IngredientDetailView(APIView):
    # Змінювати й видаляти інгредієнти може лише адміністратор
    permission_classes = [IsAdminOrReadOnly]

    @extend_schema(
        summary="Отримати інгредієнт",
        auth=PUBLIC,
        responses={200: IngredientSerializer, 404: not_found("Інгредієнт")},
    )
    def get(self, request, pk):
        ingredient = get_or_404(Ingredient.objects.all(), pk, "Інгредієнт")
        return Response(IngredientSerializer(ingredient).data)

    @extend_schema(
        summary="Перейменувати інгредієнт",
        description="Лише для адміністратора.",
        request=IngredientSerializer,
        responses={
            200: IngredientSerializer,
            400: NAME_VALIDATION_ERROR,
            401: UNAUTHORIZED,
            403: FORBIDDEN_ADMIN,
            404: not_found("Інгредієнт"),
        },
    )
    def put(self, request, pk):
        ingredient = get_or_404(Ingredient.objects.all(), pk, "Інгредієнт")
        serializer = IngredientSerializer(ingredient, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info("Оновлено інгредієнт id=%s користувачем id=%s", pk, request.user.id)
        return Response(serializer.data)

    @extend_schema(
        summary="Видалити інгредієнт",
        description=(
            "Лише для адміністратора. Не можна видалити інгредієнт, "
            "який використовується в рецептах."
        ),
        responses={
            204: OpenApiResponse(description="Інгредієнт видалено"),
            401: UNAUTHORIZED,
            403: FORBIDDEN_ADMIN,
            404: not_found("Інгредієнт"),
            409: INGREDIENT_CONFLICT,
        },
    )
    def delete(self, request, pk):
        ingredient = get_or_404(Ingredient.objects.all(), pk, "Інгредієнт")
        count = ingredient.recipes.count()
        if count:
            raise ConflictError(
                f"Неможливо видалити інгредієнт «{ingredient.name}», "
                f"оскільки він використовується в рецептах: {count}."
            )
        ingredient.delete()
        logger.info("Видалено інгредієнт id=%s користувачем id=%s", pk, request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------- Автори ----------


@extend_schema(tags=["Автори"])
class UserDetailView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Публічна інформація про автора",
        auth=PUBLIC,
        responses={200: UserSerializer, 404: not_found("Автора")},
    )
    def get(self, request, pk):
        user = get_or_404(User.objects.all(), pk, "Автора")
        return Response(UserSerializer(user).data)


# ---------- Списки рецептів категорії, інгредієнта, автора ----------


class RelatedRecipesView(APIView):
    """Спільна логіка трьох в'юх: рецепти одного батьківського об'єкта."""

    permission_classes = [AllowAny]

    model = None
    label = ""

    def get_recipes(self, obj):
        raise NotImplementedError

    def get(self, request, pk):
        obj = get_or_404(self.model.objects.all(), pk, self.label)
        recipes = sort_recipes(request, self.get_recipes(obj))
        return Response(paginate(request, recipes, RecipeListSerializer))


def related_recipes_schema(tag, label):
    return extend_schema(
        tags=[tag],
        summary=f"Рецепти: {label}",
        auth=PUBLIC,
        parameters=[SORT_PARAMETER, *PAGINATION_PARAMETERS],
        responses={200: RecipePage, 400: BAD_QUERY, 404: not_found(label)},
    )


@extend_schema_view(get=related_recipes_schema("Категорії", "Категорію"))
class CategoryRecipesView(RelatedRecipesView):
    model = Category
    label = "Категорію"

    def get_recipes(self, obj):
        return recipe_queryset().filter(category=obj)


@extend_schema_view(get=related_recipes_schema("Інгредієнти", "Інгредієнт"))
class IngredientRecipesView(RelatedRecipesView):
    model = Ingredient
    label = "Інгредієнт"

    def get_recipes(self, obj):
        return recipe_queryset().filter(ingredients=obj)


@extend_schema_view(get=related_recipes_schema("Автори", "Автора"))
class UserRecipesView(RelatedRecipesView):
    model = User
    label = "Автора"

    def get_recipes(self, obj):
        return recipe_queryset().filter(author=obj)
