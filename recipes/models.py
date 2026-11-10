from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Recipe(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Легко"
        MEDIUM = "medium", "Середньо"
        HARD = "hard", "Складно"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructions = models.TextField()
    cooking_time = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Час приготування у хвилинах",
    )
    servings = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.EASY,
    )
    image_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recipes",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="recipes",
    )
    ingredients = models.ManyToManyField(
        Ingredient,
        through="RecipeIngredient",
        related_name="recipes",
    )

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="recipe_ingredients",
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="recipe_ingredients",
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "ingredient"],
                name="unique_recipe_ingredient",
            )
        ]

    def __str__(self):
        return f"{self.recipe} — {self.ingredient}"
