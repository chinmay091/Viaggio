from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User, UserPreference


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = (
            "preferred_categories",
            "preferred_cuisines",
            "price_preference",
            "dietary_restrictions",
            "max_walking_distance_m",
            "updated_at",
        )
        read_only_fields = ("updated_at",)


class UserSerializer(serializers.ModelSerializer):
    preferences = UserPreferenceSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "phone",
            "avatar_url",
            "preferred_language",
            "location_sharing_consent",
            "preferences",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = ("email", "username", "password", "password_confirm", "location_sharing_consent")

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        # Automatically initialize default preferences
        UserPreference.objects.create(user=user)
        return user


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "username",
            "phone",
            "avatar_url",
            "preferred_language",
            "location_sharing_consent",
        )
