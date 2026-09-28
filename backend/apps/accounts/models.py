import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.common.models import AuditModel
from .managers import UserManager


class User(AbstractUser, AuditModel):
    """
    Custom User model for Viaggio.
    Uses UUID as the primary key and email for authentication.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier (UUID v4)"
    )
    email = models.EmailField(
        unique=True,
        db_index=True,
        max_length=255,
        help_text="User email address (used for login)"
    )
    username = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        help_text="Optional display name or handle"
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Optional contact phone number"
    )
    avatar_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        help_text="URL to user's profile avatar"
    )
    preferred_language = models.CharField(
        max_length=10,
        default="en",
        help_text="Preferred interface language code (e.g. 'en', 'hi')"
    )
    location_sharing_consent = models.BooleanField(
        default=False,
        help_text="Explicit consent granted by user for browser/device location sharing (City Pulse)"
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return self.email


class UserPreference(AuditModel):
    """
    Stores personalization preferences for discovery and recommendation engine.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="preferences",
        help_text="Associated user account"
    )
    preferred_categories = models.JSONField(
        default=list,
        blank=True,
        help_text="List of preferred categories (e.g. ['restaurants', 'cafes', 'museums'])"
    )
    preferred_cuisines = models.JSONField(
        default=list,
        blank=True,
        help_text="List of preferred cuisines (e.g. ['italian', 'coastal', 'north_indian'])"
    )
    price_preference = models.IntegerField(
        default=2,
        help_text="Budget preference: 1 (Budget), 2 (Moderate), 3 (Upscale), 4 (Fine Dining)"
    )
    dietary_restrictions = models.JSONField(
        default=list,
        blank=True,
        help_text="Dietary flags (e.g. ['vegetarian', 'vegan', 'halal', 'gluten_free'])"
    )
    max_walking_distance_m = models.IntegerField(
        default=2000,
        help_text="Maximum preferred walking distance in meters"
    )

    class Meta:
        db_table = "user_preferences"
        verbose_name = "User Preference"
        verbose_name_plural = "User Preferences"

    def __str__(self):
        return f"Preferences for {self.user.email}"
