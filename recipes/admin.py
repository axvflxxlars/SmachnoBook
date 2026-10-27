from django.contrib import admin

from .models import Category, Ingredient, Recipe, RecipeIngredient

admin.site.register(Category)
admin.site.register(Ingredient)
admin.site.register(Recipe)
admin.site.register(RecipeIngredient)
