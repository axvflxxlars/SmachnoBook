from rest_framework.permissions import SAFE_METHODS, BasePermission

# SAFE_METHODS — це GET, HEAD і OPTIONS: запити, які нічого не змінюють.
# Якщо has_permission повертає False для неавторизованого користувача,
# DRF сам відповідає 401, а для авторизованого — 403 з текстом message.


class IsAdminOrReadOnly(BasePermission):
    """Читати можуть усі, змінювати — лише адміністратор (is_staff)."""

    message = "Ця дія доступна лише адміністратору."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class IsAuthorOrAdminOrReadOnly(BasePermission):
    """Читати можуть усі, змінювати об'єкт — його автор або адміністратор."""

    message = "Змінювати й видаляти рецепт може лише його автор або адміністратор."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.author_id == request.user.id or request.user.is_staff
