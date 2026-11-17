import logging

from drf_spectacular.utils import (
    OpenApiExample,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from recipes.openapi import UNAUTHORIZED, error_response, validation_error_response

from .serializers import LoginSerializer, RegisterSerializer, UserProfileSerializer

logger = logging.getLogger(__name__)

INVALID_TOKEN = error_response(
    "Refresh-токен недійсний або прострочений",
    "Токен недійсний або термін його дії минув.",
)


@extend_schema(tags=["Авторизація"])
class RegisterView(APIView):
    permission_classes = [AllowAny]
    # Реєстрації токен не потрібен, тому навіть прострочений токен
    # у заголовку не повинен заважати
    authentication_classes = []

    @extend_schema(
        summary="Реєстрація",
        description=(
            "Створює нового користувача. Пароль зберігається лише у вигляді "
            "хеша й не повертається у відповіді."
        ),
        request=RegisterSerializer,
        responses={
            201: UserProfileSerializer,
            400: validation_error_response(
                {
                    "email": ["Введіть коректну адресу електронної пошти."],
                    "password_confirm": ["Паролі не збігаються."],
                }
            ),
        },
        examples=[
            OpenApiExample(
                "Новий користувач",
                request_only=True,
                value={
                    "username": "olena",
                    "first_name": "Олена",
                    "last_name": "Коваль",
                    "email": "olena@example.com",
                    "password": "Strong_Pass_2026",
                    "password_confirm": "Strong_Pass_2026",
                },
            )
        ],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        logger.info("Зареєстровано користувача id=%s (%s)", user.id, user.username)
        return Response(
            UserProfileSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Авторизація"])
class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

    @extend_schema(
        summary="Вхід",
        description=(
            "Повертає access-токен (5 хвилин) і refresh-токен (1 день). "
            "Access передається в заголовку `Authorization: Bearer <access>`."
        ),
        request=inline_serializer(
            name="LoginRequest",
            fields={
                "username": serializers.CharField(),
                "password": serializers.CharField(),
            },
        ),
        responses={
            200: inline_serializer(
                name="LoginResponse",
                fields={
                    "access": serializers.CharField(),
                    "refresh": serializers.CharField(),
                    "user": UserProfileSerializer(),
                },
            ),
            401: error_response(
                "Неправильний логін або пароль",
                "Неправильне ім'я користувача або пароль.",
            ),
        },
    )
    def post(self, request, *args, **kwargs):
        # Якщо логін або пароль неправильні, super().post кидає виняток,
        # і цей рядок не виконається (невдалу спробу залогує обробник помилок)
        response = super().post(request, *args, **kwargs)
        # Логуємо лише id: токени в логи потрапляти не повинні
        logger.info("Користувач id=%s увійшов у систему", response.data["user"]["id"])
        return response


@extend_schema(tags=["Авторизація"])
class RefreshView(TokenRefreshView):
    @extend_schema(
        summary="Оновити access-токен",
        description="Повертає новий access-токен за refresh-токеном.",
        responses={
            200: inline_serializer(
                name="RefreshResponse",
                fields={"access": serializers.CharField()},
            ),
            401: INVALID_TOKEN,
        },
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(tags=["Авторизація"])
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Поточний користувач",
        responses={
            200: UserProfileSerializer,
            401: UNAUTHORIZED,
        },
    )
    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)
