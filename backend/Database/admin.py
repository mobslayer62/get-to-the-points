from django.contrib import admin

from .models import Card, UserCard


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ["name", "rarity"]
    list_filter = ["rarity"]
    search_fields = ["name"]


@admin.register(UserCard)
class UserCardAdmin(admin.ModelAdmin):
    list_display = ["user", "card", "quantity", "first_obtained_at"]
    list_filter = ["card__rarity"]
    search_fields = ["user__username", "card__name"]
