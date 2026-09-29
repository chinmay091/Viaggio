from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    RefreshView,
    UserProfileView,
    UserPreferenceView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth_register"),
    path("login/", LoginView.as_view(), name="auth_login"),
    path("refresh/", RefreshView.as_view(), name="auth_token_refresh"),
    path("me/", UserProfileView.as_view(), name="auth_me"),
    path("preferences/", UserPreferenceView.as_view(), name="auth_preferences"),
]
