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

    # Story level (1-5). Raised by spending points, see progression.py
    level = models.PositiveSmallIntegerField(default=1)

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

    # Total points for the run, including bonus_points from cards.
    points_earned = models.PositiveIntegerField(default=0)
    bonus_points = models.PositiveIntegerField(default=0)

    # Per-card bonus breakdown worked out when the run was saved. Stored
    # because some specials depend on the player's lifetime distance at
    # that moment, which can't be recomputed later.
    card_bonus_breakdown = models.JSONField(default=list, blank=True)

    # Snapshot of the player's loadout when this session was saved, so
    # card benefits can be worked out (or audited) per session later.
    equipped_cards = models.ManyToManyField(
        "Card",
        blank=True,
        related_name="sessions_equipped_in"
    )

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

    # What the card does when equipped for a run. A card has up to two
    # benefits: a passive (effect_*) and a special (special_*). Both are
    # worked out in utils.calculate_card_bonuses; add new types there too.
    EFFECT_NONE = "none"

    # ----- Passive -----
    EFFECT_POINTS_PERCENT = "points_percent"
    EFFECT_WALK_POINTS_PERCENT = "walk_points_percent"
    EFFECT_RUN_POINTS_PERCENT = "run_points_percent"
    EFFECT_FLAT_POINTS = "flat_points"
    EFFECT_CHOICES = [
        (EFFECT_NONE, "No effect"),
        (EFFECT_POINTS_PERCENT, "+% of the run's base points"),
        (EFFECT_WALK_POINTS_PERCENT, "+% of the run's base points (walks only)"),
        (EFFECT_RUN_POINTS_PERCENT, "+% of the run's base points (runs only)"),
        (EFFECT_FLAT_POINTS, "+flat points per run"),
    ]

    effect_type = models.CharField(
        max_length=30,
        choices=EFFECT_CHOICES,
        default=EFFECT_NONE
    )
    effect_value = models.PositiveIntegerField(
        default=0,
        help_text=(
            "For the '+%' types: the percent, e.g. 25 = +25% of the run's base "
            "points. For '+flat points': points added per run. "
            "Ignored for 'No effect'."
        ),
    )

    # ----- Special -----
    SPECIAL_DISTANCE_MILESTONE = "distance_milestone"
    SPECIAL_WALK_DISTANCE = "walk_distance"
    SPECIAL_RUN_DISTANCE = "run_distance"
    SPECIAL_MIN_DURATION = "min_duration"
    SPECIAL_CHOICES = [
        (EFFECT_NONE, "No special"),
        (SPECIAL_DISTANCE_MILESTONE,
         "+points every time total (lifetime) distance passes another X m"),
        (SPECIAL_WALK_DISTANCE, "+points per X m walked in the run (walks only)"),
        (SPECIAL_RUN_DISTANCE, "+points per X m run in the session (runs only)"),
        (SPECIAL_MIN_DURATION, "+points if the run lasts at least X minutes"),
    ]

    special_type = models.CharField(
        max_length=30,
        choices=SPECIAL_CHOICES,
        default=EFFECT_NONE
    )
    special_value = models.PositiveIntegerField(
        default=0,
        help_text="Points the special grants each time it triggers.",
    )
    special_threshold = models.PositiveIntegerField(
        default=0,
        help_text=(
            "The X in the special: metres for the distance specials "
            "(5000 = every 5 km), minutes for 'lasts at least'."
        ),
    )

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


class EquippedCard(models.Model):
    """
    One of the (up to) MAX_SLOTS cards a player brings into a session.

    The database itself refuses two cards in the same slot and the same
    card in two slots, so duplicates are impossible even if the API is
    bypassed.
    """

    MAX_SLOTS = 4

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="equipped_cards"
    )

    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE
    )

    slot = models.PositiveSmallIntegerField()  # 1..MAX_SLOTS

    class Meta:
        ordering = ["slot"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "slot"],
                name="one_card_per_slot"
            ),
            models.UniqueConstraint(
                fields=["user", "card"],
                name="no_duplicate_equipped_card"
            ),
            models.CheckConstraint(
                condition=models.Q(slot__gte=1) & models.Q(slot__lte=4),
                name="equipped_slot_in_range"
            ),
        ]

    def __str__(self):
        return f"{self.user.username} slot {self.slot}: {self.card.name}"


class SessionStart(models.Model):
    """
    A run the player has started but not finished yet.

    The loadout is locked in here the moment the run starts, so changing
    equipped cards mid-run has no effect on that run. finish-session only
    accepts session ids that have a SessionStart, then copies the locked
    cards onto the WalkingSession and deletes this row.
    """

    session_id = models.UUIDField(unique=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="session_starts"
    )

    equipped_cards = models.ManyToManyField(
        Card,
        blank=True,
        related_name="session_starts"
    )

    started_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} started {self.started_at:%Y-%m-%d %H:%M}"


# ----- Keep loadouts valid -----

from django.db.models.signals import post_delete, pre_delete  # noqa: E402
from django.dispatch import receiver  # noqa: E402


@receiver(post_delete, sender=UserCard)
def unequip_lost_card(sender, instance, **kwargs):
    """
    When a player loses a card (deleted in the admin, or by any future
    code), unequip it right away and close the gap in their slots.
    Deleting the Card itself already unequips it via on_delete=CASCADE.
    """
    from .utils import compact_equipped_slots

    removed, _ = EquippedCard.objects.filter(
        user_id=instance.user_id, card_id=instance.card_id
    ).delete()
    if removed:
        compact_equipped_slots(instance.user_id)


@receiver(pre_delete, sender=Card)
def remember_players_with_card_equipped(sender, instance, **kwargs):
    """Note who has this card equipped before the cascade removes it."""
    instance._equipped_user_ids = list(
        EquippedCard.objects
        .filter(card=instance)
        .values_list("user_id", flat=True)
        .distinct()
    )


@receiver(post_delete, sender=Card)
def close_gaps_after_card_removed(sender, instance, **kwargs):
    """A card was removed from the game: close the gap in those loadouts."""
    from .utils import compact_equipped_slots

    for user_id in getattr(instance, "_equipped_user_ids", []):
        compact_equipped_slots(user_id)


class StoryProgress(models.Model):
    """One row per chapter a player has finished reading."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="story_progress"
    )

    # Matches an "id" in story_data.CHAPTERS
    chapter_id = models.CharField(max_length=50)

    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "chapter_id"],
                name="unique_chapter_per_user"
            )
        ]
