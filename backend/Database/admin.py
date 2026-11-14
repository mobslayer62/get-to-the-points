from django.contrib import admin

from .models import UserActivity, WalkingSession


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ("user", "total_points", "total_distance", "total_steps")
    search_fields = ("user__username",)


@admin.register(WalkingSession)
class WalkingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "user", "distance", "steps", "duration_seconds",
        "points_earned", "created_at",
    )
    list_filter = ("user",)
    readonly_fields = ("session_id", "created_at")
