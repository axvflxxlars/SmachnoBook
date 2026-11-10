from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import ConflictError
from .models import Category, Ingredient, Recipe
from .serializers import (
    CategorySerializer,
    IngredientSerializer,
    RecipeListSerializer,
    RecipeSerializer,
    UserSerializer,
)

User = get_user_model()

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
        raise ValidationError(
            f"Параметр {name} має бути цілим числом."
        ) from None
    if value < 1:
        raise ValidationError(f"Параметр {name} має бути не менше 1.")
    return value


def paginate(request, queryset, serializer_class):
    page = int_param(request, "page", default=1)
    limit = int_param(request, "limit", default=20)
    if limit > MAX_LIMIT:
        raise ValidationError(
            f"Параметр limit не може перевищувати {MAX_LIMIT}."
        )
    start = (page - 1) * limit
    items = queryset[start:start + limit]
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
            raise ValidationError(
                f"Параметр difficulty має бути одним із: {allowed}."
            )
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




class RecipeListView(APIView):
    def get(self, request):
        recipes = filter_recipes(request, recipe_queryset())
        recipes = sort_recipes(request, recipes)
        return Response(paginate(request, recipes, RecipeListSerializer))

    def post(self, request):
        serializer = RecipeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RecipeDetailView(APIView):
    def get(self, request, pk):
        queryset = recipe_queryset().prefetch_related(
            "recipe_ingredients__ingredient"
        )
        recipe = get_or_404(queryset, pk, "Рецепт")
        return Response(RecipeSerializer(recipe).data)

    def put(self, request, pk):
        recipe = get_or_404(recipe_queryset(), pk, "Рецепт")
        serializer = RecipeSerializer(recipe, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        recipe = get_or_404(recipe_queryset(), pk, "Рецепт")
        recipe.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)




class CategoryListView(APIView):
    def get(self, request):
        serializer = CategorySerializer(Category.objects.all(), many=True)
        return Response({"data": serializer.data})

    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CategoryDetailView(APIView):
    def get(self, request, pk):
        category = get_or_404(Category.objects.all(), pk, "Категорію")
        return Response(CategorySerializer(category).data)

    def put(self, request, pk):
        category = get_or_404(Category.objects.all(), pk, "Категорію")
        serializer = CategorySerializer(category, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

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
        return Response(status=status.HTTP_204_NO_CONTENT)




class IngredientListView(APIView):
    def get(self, request):
        ingredients = Ingredient.objects.all()
        search = request.query_params.get("search")
        if search:
            ingredients = ingredients.filter(name__icontains=search)
        return Response(paginate(request, ingredients, IngredientSerializer))

    def post(self, request):
        serializer = IngredientSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class IngredientDetailView(APIView):
    def get(self, request, pk):
        ingredient = get_or_404(Ingredient.objects.all(), pk, "Інгредієнт")
        return Response(IngredientSerializer(ingredient).data)

    def put(self, request, pk):
        ingredient = get_or_404(Ingredient.objects.all(), pk, "Інгредієнт")
        serializer = IngredientSerializer(ingredient, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        ingredient = get_or_404(Ingredient.objects.all(), pk, "Інгредієнт")
        count = ingredient.recipes.count()
        if count:
            raise ConflictError(
                f"Неможливо видалити інгредієнт «{ingredient.name}», "
                f"оскільки він використовується в рецептах: {count}."
            )
        ingredient.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)





class UserDetailView(APIView):
    def get(self, request, pk):
        user = get_or_404(User.objects.all(), pk, "Автора")
        return Response(UserSerializer(user).data)





class RelatedRecipesView(APIView):

    model = None
    label = ""

    def get_recipes(self, obj):
        raise NotImplementedError

    def get(self, request, pk):
        obj = get_or_404(self.model.objects.all(), pk, self.label)
        recipes = sort_recipes(request, self.get_recipes(obj))
        return Response(paginate(request, recipes, RecipeListSerializer))


class CategoryRecipesView(RelatedRecipesView):
    model = Category
    label = "Категорію"

    def get_recipes(self, obj):
        return recipe_queryset().filter(category=obj)


class IngredientRecipesView(RelatedRecipesView):
    model = Ingredient
    label = "Інгредієнт"

    def get_recipes(self, obj):
        return recipe_queryset().filter(ingredients=obj)


class UserRecipesView(RelatedRecipesView):
    model = User
    label = "Автора"

    def get_recipes(self, obj):
        return recipe_queryset().filter(author=obj)
