import factory
from django.contrib.auth import get_user_model

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """Factory for the custom UUID/email User model (email is the login id)."""

    class Meta:
        model = User
        django_get_or_create = ("email",)

    email = factory.Sequence(lambda n: f"user{n + 1}@example.com")
    username = factory.Sequence(lambda n: f"user{n + 1}")
    # Strong enough to satisfy AUTH_PASSWORD_VALIDATORS if ever routed through
    # the registration serializer; the factory itself bypasses validation.
    password = factory.PostGenerationMethodCall("set_password", "Viaggio-test-Passw0rd!x")
