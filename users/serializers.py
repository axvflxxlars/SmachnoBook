from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """Дані поточного користувача (без пароля)."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "is_staff"]
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    # У моделі User email необов'язковий і неунікальний, тому описуємо поле самі
    email = serializers.EmailField(
        max_length=254,
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                lookup="iexact",
                message="Користувач з таким email уже існує.",
            )
        ],
    )
    # write_only: пароль приймаємо, але ніколи не повертаємо у відповіді
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=128,
        trim_whitespace=False,
    )
    password_confirm = serializers.CharField(
        write_only=True,
        max_length=128,
        trim_whitespace=False,
    )

    class Meta:
        model = User
        # username, first_name, last_name беруть обмеження з моделі:
        # максимум 150 символів; first_name і last_name можна не заповнювати
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "password",
            "password_confirm",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": ["Паролі не збігаються."]}
            )

        # Перевірка складності стандартними валідаторами Django
        # (AUTH_PASSWORD_VALIDATORS у settings.py)
        user = User(
            username=attrs["username"],
            email=attrs["email"],
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                {"password": list(error.messages)}
            ) from None
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        # create_user хешує пароль перед збереженням у базу
        return User.objects.create_user(**validated_data)


class LoginSerializer(TokenObtainPairSerializer):
    """Стандартний логін SimpleJWT + дані користувача у відповіді."""

    default_error_messages = {
        "no_active_account": "Неправильне ім'я користувача або пароль.",
    }

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserProfileSerializer(self.user).data
        return data
