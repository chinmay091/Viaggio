from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, UserPreference
from .serializers import (
    UserRegistrationSerializer,
    UserSerializer,
    UserProfileUpdateSerializer,
    UserPreferenceSerializer,
)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer that includes user details in the token response.
    """
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class LoginView(TokenObtainPairView):
    """
    User login endpoint. Accepts email and password, returns JWT tokens and user profile.

    F6: throttled (scope "login", per client IP for anonymous requests) against
    brute-force password guessing.
    """
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class RefreshView(TokenRefreshView):
    """
    SimpleJWT refresh endpoint.

    F6: throttled (scope "refresh") per user when the request carries a Bearer
    token, otherwise per client IP, to limit token-rotation spam.
    """
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "refresh"


class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint. Registers a new account and immediately returns
    JWT authentication tokens along with the created profile.

    F6: throttled (scope "register", per client IP for anonymous requests) against
    bulk account creation.
    """
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens for the newly registered user
        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user).data

        return Response(
            {
                "message": "User registered successfully.",
                "user": user_data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    Retrieve or update the authenticated user's profile information.
    """
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return UserProfileUpdateSerializer
        return UserSerializer


class UserPreferenceView(generics.RetrieveUpdateAPIView):
    """
    Retrieve or update the authenticated user's discovery and recommendation preferences.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserPreferenceSerializer

    def get_object(self):
        pref, _ = UserPreference.objects.get_or_create(user=self.request.user)
        return pref
