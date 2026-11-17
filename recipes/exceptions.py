import logging

from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    NotAuthenticated,
    ValidationError,
)
from rest_framework.views import exception_handler
from rest_framework_simplejwt.exceptions import InvalidToken

logger = logging.getLogger(__name__)


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Конфлікт з поточним станом даних."
    default_code = "conflict"


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        # Не помилка DRF (баг у коді). Django сам залогує її як ERROR
        # з traceback через логер django.request і поверне 500
        return None

    if isinstance(exc, ValidationError):
        details = response.data
        if isinstance(details, list):
            message = " ".join(str(item) for item in details)
            response.data = {"error": message}
        else:
            response.data = {
                "error": "Некоректні дані. Перевірте поля запиту.",
                "details": details,
            }
    elif isinstance(exc, NotAuthenticated):
        response.data = {
            "error": "Потрібна авторизація. Передайте access-токен "
            "у заголовку Authorization: Bearer <token>."
        }
    elif isinstance(exc, InvalidToken):
        response.data = {"error": "Токен недійсний або термін його дії минув."}
    else:
        message = response.data.get("detail", "Сталася помилка.")
        response.data = {"error": str(message)}

    log_client_error(response, context.get("request"))
    return response


def log_client_error(response, request):
    """Логує відповідь 4xx: статус, метод, адресу, користувача і причину.

    Тіло запиту навмисно не логується: там можуть бути паролі й токени.
    Для помилок валідації логуються лише назви полів, а не їхні значення.
    """
    if request is None:
        return

    if "details" in response.data:
        reason = "некоректні поля: " + ", ".join(response.data["details"])
    else:
        reason = response.data["error"]

    # 401 і 403 — спроби доступу без прав: це варто помічати (WARNING).
    # Інші 4xx (400, 404, 409) — звичайні помилки клієнта (INFO)
    if response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ):
        level = logging.WARNING
    else:
        level = logging.INFO

    logger.log(
        level,
        "%s %s %s user=%s: %s",
        response.status_code,
        request.method,
        request.path,
        user_id(request),
        reason,
    )


def user_id(request):
    try:
        user = request.user
    except APIException:
        # Помилка сталася до автентифікації, і токен у запиті недійсний
        return "anonymous"
    return user.id if user.is_authenticated else "anonymous"
