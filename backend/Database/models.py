from django.db import models
from django.contrib.auth.models import User
import uuid


class UserActivity(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    total_distance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    total_points = models.PositiveIntegerField(default=0)
    total_steps = models.PositiveIntegerField(default=0)

class WalkingSession(models.Model):
    session_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    distance = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    steps = models.PositiveIntegerField(default=0)

    points_earned = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

class Card(models.Model):
    """A card that exists in the game (the catalog the gachapon pulls from)."""

    RARITY_CHOICES = [
        ("A", "A"),
        ("A+", "A+"),
        ("S", "S"),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    rarity = models.CharField(
        max_length=20,
        choices=RARITY_CHOICES,
        default="A"
    )
    image_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.rarity})"


class UserCard(models.Model):
    """One row per (user, card) pair; duplicates bump `quantity`."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="card_storage"
    )

    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE
    )

    quantity = models.PositiveIntegerField(default=1)

    first_obtained_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "card"],
                name="unique_card_per_user"
            )
        ]

    def __str__(self):
        return f"{self.user.username}: {self.card.name} x{self.quantity}"
