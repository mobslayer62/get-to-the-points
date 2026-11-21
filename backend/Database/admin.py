from django.contrib import admin

from .models import (
    Card, EquippedCard, GachaPull, SessionStart, StoryProgress, UserActivity,
    UserCard, WalkingSession,
)


@admin.register(SessionStart)
class SessionStartAdmin(admin.ModelAdmin):
    list_display = ["user", "session_id", "started_at"]
    list_filter = ["user"]
    readonly_fields = ["session_id", "started_at"]


@admin.register(EquippedCard)
class EquippedCardAdmin(admin.ModelAdmin):
    list_display = ["user", "slot", "card"]
    list_filter = ["user"]
    search_fields = ["user__username", "card__name"]


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = (
        "user", "level", "total_points", "total_distance", "total_steps",
        "pulls_since_s", "total_pulls",
    )
    search_fields = ("user__username",)


@admin.register(WalkingSession)
class WalkingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "user", "distance", "steps", "duration_seconds",
        "points_earned", "bonus_points", "created_at",
    )
    list_filter = ("user",)
    readonly_fields = ("session_id", "created_at")


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = [
        "name", "rarity", "effect_type", "effect_value",
        "special_type", "special_value", "special_threshold",
    ]
    list_filter = ["rarity", "effect_type", "special_type"]
    search_fields = ["name"]
    fieldsets = [
        (None, {"fields": ["name", "description", "rarity", "image_url"]}),
        ("Passive", {"fields": ["effect_type", "effect_value"]}),
        ("Special", {"fields": ["special_type", "special_value", "special_threshold"]}),
    ]


@admin.register(UserCard)
class UserCardAdmin(admin.ModelAdmin):
    list_display = ["user", "card", "quantity", "first_obtained_at"]
    list_filter = ["card__rarity"]
    search_fields = ["user__username", "card__name"]


@admin.register(StoryProgress)
class StoryProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "chapter_id", "completed_at"]
    list_filter = ["chapter_id"]
    search_fields = ["user__username"]


@admin.register(GachaPull)
class GachaPullAdmin(admin.ModelAdmin):
    list_display = ["user", "card", "rarity", "was_pity", "pulled_at"]
    list_filter = ["rarity", "was_pity"]
    search_fields = ["user__username", "card__name"]
