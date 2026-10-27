from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from .models import Category, Ingredient, Recipe, RecipeIngredient

User = get_user_model()


def user_name(user):
    return user.get_full_name() or user.username


def short_relations(recipe):
    return {
        "category": {
            "id": recipe.category_id,
            "name": recipe.category.name,
        },
        "author": {
            "id": recipe.author_id,
            "name": user_name(recipe.author),
        },
    }


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ["id", "name"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id"]

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "name": user_name(instance),
            "recipes_count": instance.recipes.count(),
        }


class RecipeIngredientSerializer(serializers.Serializer):

    ingredient_id = serializers.PrimaryKeyRelatedField(
        source="ingredient",
        queryset=Ingredient.objects.all(),
    )
    amount = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    unit = serializers.CharField(max_length=20)

    def to_representation(self, instance):
        return {
            "id": instance.ingredient_id,
            "name": instance.ingredient.name,
            "amount": float(instance.amount),
            "unit": instance.unit,
        }


class RecipeSerializer(serializers.ModelSerializer):

    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=Category.objects.all(),
    )
    author_id = serializers.PrimaryKeyRelatedField(
        source="author",
        queryset=User.objects.all(),
    )
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
            "author_id",
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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop("category_id")
        data.pop("author_id")
        data.update(short_relations(instance))
        return data

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

    class Meta:
        model = Recipe
        fields = ["id", "title", "cooking_time", "difficulty", "image_url"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(short_relations(instance))
        return data
