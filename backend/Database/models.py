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

    duration_seconds = models.PositiveIntegerField(default=0)

    points_earned = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)