from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .models import Category, Ingredient, Recipe, RecipeIngredient

User = get_user_model()


def user_name(user):
    return user.get_full_name() or user.username


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ["id", "name"]


class AuthorShortSerializer(serializers.ModelSerializer):
    """Автор у складі рецепта: лише id та ім'я."""

    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name"]

    # Підказка типу -> str потрібна drf-spectacular, щоб знати тип поля
    def get_name(self, user) -> str:
        return user_name(user)


class UserSerializer(AuthorShortSerializer):
    """Публічна сторінка автора."""

    recipes_count = serializers.SerializerMethodField()

    class Meta(AuthorShortSerializer.Meta):
        fields = ["id", "name", "recipes_count"]

    def get_recipes_count(self, user) -> int:
        return user.recipes.count()


class RecipeIngredientSerializer(serializers.Serializer):
    # Лише на вході: id інгредієнта
    ingredient_id = serializers.PrimaryKeyRelatedField(
        source="ingredient",
        queryset=Ingredient.objects.all(),
        write_only=True,
    )
    # Лише на виході: id і назва інгредієнта
    id = serializers.IntegerField(source="ingredient_id", read_only=True)
    name = serializers.CharField(source="ingredient.name", read_only=True)
    # coerce_to_string=False: у відповіді число (2.0), а не рядок ("2.00")
    amount = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=Decimal("0.01"),
        coerce_to_string=False,
    )
    unit = serializers.CharField(max_length=20)


class RecipeSerializer(serializers.ModelSerializer):
    # На вході приймаємо id категорії, на виході віддаємо об'єкт category
    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=Category.objects.all(),
        write_only=True,
    )
    category = CategorySerializer(read_only=True)
    # Автора не передають у запиті: його підставляє в'юха з токена
    author = AuthorShortSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        source="recipe_ingredients",
        many=True,
        allow_empty=False,
    )

    class Meta:
        model = Recipe
        fields = [
            "id",
            "title",
            "description",
            "instructions",
            "cooking_time",
            "servings",
            "difficulty",
            "image_url",
            "created_at",
            "category_id",
            "category",
            "author",
            "ingredients",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_ingredients(self, items):
        ids = [item["ingredient"].id for item in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                "Інгредієнти в рецепті не повинні повторюватись."
            )
        return items

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop("recipe_ingredients")
        recipe = Recipe.objects.create(**validated_data)
        self._save_items(recipe, items)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        items = validated_data.pop("recipe_ingredients")
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        instance.recipe_ingredients.all().delete()
        self._save_items(instance, items)
        return instance

    @staticmethod
    def _save_items(recipe, items):
        RecipeIngredient.objects.bulk_create(
            [RecipeIngredient(recipe=recipe, **item) for item in items]
        )


class RecipeListSerializer(serializers.ModelSerializer):
    """Коротка версія рецепта для списків."""

    category = CategorySerializer(read_only=True)
    author = AuthorShortSerializer(read_only=True)

    class Meta:
        model = Recipe
        fields = [
            "id",
            "title",
            "cooking_time",
            "difficulty",
            "image_url",
            "category",
            "author",
        ]
