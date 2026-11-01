"""
Admin registrations for the discovery app (P3-F2).
"""

from django.contrib import admin

from .models import PlaceView, SavedPlace


@admin.register(SavedPlace)
class SavedPlaceAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "place", "saved_at", "created_at")
    list_filter = ("saved_at",)
    search_fields = ("user__email", "place__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PlaceView)
class PlaceViewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "place",
        "user",
        "session_id",
        "source",
        "duration_seconds",
        "created_at",
    )
    list_filter = ("source", "created_at")
    search_fields = ("place__name", "user__email", "session_id")
    readonly_fields = ("created_at",)
