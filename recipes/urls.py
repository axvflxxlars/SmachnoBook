from django.urls import path

from . import views

urlpatterns = [
    path("recipes", views.RecipeListView.as_view()),
    path("recipes/<int:pk>", views.RecipeDetailView.as_view()),
    path("categories", views.CategoryListView.as_view()),
    path("categories/<int:pk>", views.CategoryDetailView.as_view()),
    path(
        "categories/<int:pk>/recipes",
        views.CategoryRecipesView.as_view(),
    ),
    path("ingredients", views.IngredientListView.as_view()),
    path("ingredients/<int:pk>", views.IngredientDetailView.as_view()),
    path(
        "ingredients/<int:pk>/recipes",
        views.IngredientRecipesView.as_view(),
    ),
    path("users/<int:pk>", views.UserDetailView.as_view()),
    path("users/<int:pk>/recipes", views.UserRecipesView.as_view()),
]
