from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


class ConflictError(APIException):


    status_code = status.HTTP_409_CONFLICT
    default_detail = "Конфлікт з поточним станом даних."
    default_code = "conflict"


def custom_exception_handler(exc, context):

    response = exception_handler(exc, context)
    if response is None:
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
    else:
        message = response.data.get("detail", "Сталася помилка.")
        response.data = {"error": str(message)}
    return response
