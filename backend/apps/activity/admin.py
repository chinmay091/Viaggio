"""
Admin registrations for the activity app (P3-F1).
"""

from django.contrib import admin

from .models import ActivityAggregate, HistoricalBaseline, UserActivity


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "place", "h3_index_res8", "h3_index_res9", "timestamp")
    list_filter = ("timestamp",)
    search_fields = ("user__email", "place__name", "h3_index_res8", "h3_index_res9")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ActivityAggregate)
class ActivityAggregateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "h3_index",
        "resolution",
        "time_bucket",
        "active_count",
        "event_count",
        "created_at",
    )
    list_filter = ("resolution", "time_bucket")
    search_fields = ("h3_index",)
    readonly_fields = ("created_at",)


@admin.register(HistoricalBaseline)
class HistoricalBaselineAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "h3_index",
        "resolution",
        "day_of_week",
        "time_bucket_minutes",
        "avg_active_count",
        "stddev_active_count",
        "sample_count",
        "updated_at",
    )
    list_filter = ("resolution", "day_of_week")
    search_fields = ("h3_index",)
    readonly_fields = ("updated_at",)
