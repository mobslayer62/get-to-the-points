"""
Game rules for activity rewards.

All point calculations and anti-cheat checks live here (in Python) so the
Flutter app never decides how many points a player earns.
"""
from decimal import Decimal, ROUND_FLOOR

# ----- Economy -----
METERS_PER_POINT = Decimal("10")  # 10 points per 100 m

# ----- Plausibility limits for a single session -----
MAX_SESSION_DISTANCE_M = Decimal("50000")  # 50 km in one session
MAX_AVERAGE_SPEED_MPS = Decimal("7")       # ~25 km/h, faster than any realistic jog/run average
SPEED_CHECK_MIN_DISTANCE_M = Decimal("200")  # ignore GPS jitter on very short sessions
MAX_SESSION_DURATION_S = 6 * 60 * 60         # 6 hours


def convert_distance_to_points(distance, multiplier=1):
    """Base reward: floor(distance / 10) * multiplier."""
    points = (Decimal(str(distance)) / METERS_PER_POINT) * Decimal(str(multiplier))
    return int(points.to_integral_value(rounding=ROUND_FLOOR))


def calculate_card_bonuses(base_points, cards):
    """
    Work out the bonus points each equipped card adds to a run.

    - points_percent: floor(base_points * value / 100), per card
    - flat_points:    + value
    Percent bonuses are all based on the run's base points (they don't
    compound), so the order cards are equipped in doesn't matter.

    Returns (total_bonus, [{"card_id", "name", "effect_type",
    "effect_value", "bonus"}, ...]) with one entry per card.
    """
    from .models import Card

    breakdown = []
    for card in cards:
        if card.effect_type == Card.EFFECT_POINTS_PERCENT:
            bonus = int(
                (Decimal(base_points) * Decimal(card.effect_value) / Decimal(100))
                .to_integral_value(rounding=ROUND_FLOOR)
            )
        elif card.effect_type == Card.EFFECT_FLAT_POINTS:
            bonus = card.effect_value
        else:
            bonus = 0

        breakdown.append({
            "card_id": card.id,
            "name": card.name,
            "effect_type": card.effect_type,
            "effect_value": card.effect_value,
            "bonus": bonus,
        })

    return sum(b["bonus"] for b in breakdown), breakdown


def find_session_problem(distance, duration_seconds):
    """
    Return a human-readable reason if the session looks impossible,
    or None if it is acceptable.
    """
    distance = Decimal(str(distance))

    if distance > MAX_SESSION_DISTANCE_M:
        return f"Distance exceeds the {MAX_SESSION_DISTANCE_M} m per-session limit."

    if duration_seconds > MAX_SESSION_DURATION_S:
        return "Session is longer than the 6 hour limit."

    if distance >= SPEED_CHECK_MIN_DISTANCE_M:
        if duration_seconds <= 0:
            return "Session duration is required."
        average_speed = distance / Decimal(duration_seconds)
        if average_speed > MAX_AVERAGE_SPEED_MPS:
            return "Average speed is too high for walking or running."

    return None


def add_card_to_storage(user, card):
    """
    Put a pulled card into the user's storage.

    - New card  -> creates a UserCard row with quantity 1.
    - Duplicate -> adds 1 to the existing row's quantity.

    Returns (user_card, is_new).
    """
    from django.db import transaction
    from django.db.models import F

    from .models import UserCard

    with transaction.atomic():
        user_card, created = UserCard.objects.get_or_create(
            user=user,
            card=card,
            defaults={"quantity": 1}
        )

        if not created:
            # F() does the +1 inside the database, so two pulls at the
            # same time can't overwrite each other.
            UserCard.objects.filter(pk=user_card.pk).update(
                quantity=F("quantity") + 1
            )
            user_card.refresh_from_db()

    return user_card, created


# ----- Card loadout -----

def remove_unowned_equipped_cards(user):
    """
    Unequip any card the player no longer owns, then close the gaps so the
    remaining cards sit in slots 1, 2, 3... in their original order.

    Returns the number of cards removed.
    """
    from django.db import transaction

    from .models import EquippedCard, UserCard

    with transaction.atomic():
        owned = UserCard.objects.filter(
            user=user, quantity__gte=1
        ).values_list("card_id", flat=True)

        removed, _ = (
            EquippedCard.objects
            .filter(user=user)
            .exclude(card_id__in=owned)
            .delete()
        )
        if removed:
            compact_equipped_slots(user)

    return removed


def compact_equipped_slots(user):
    """
    Renumber a player's equipped cards to 1..n with no gaps.
    Moving each card down in ascending order never collides with the
    one-card-per-slot rule, because the target slot is always free.
    """
    from .models import EquippedCard

    equipped = EquippedCard.objects.filter(user=user).order_by("slot")
    for new_slot, item in enumerate(equipped, start=1):
        if item.slot != new_slot:
            item.slot = new_slot
            item.save(update_fields=["slot"])


# ----- Main menu -----

RECENT_SESSIONS_ON_HOME = 3


def build_home_summary(user):
    """
    Everything the main menu shows, in one response, so the app
    makes a single request when the menu opens.
    """
    from .models import Card, UserActivity, UserCard, WalkingSession

    activity = UserActivity.objects.filter(user=user).first()
    sessions = WalkingSession.objects.filter(user=user).order_by("-created_at", "-id")

    recent = [
        {
            "distance": str(s.distance),
            "points_earned": s.points_earned,
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions[:RECENT_SESSIONS_ON_HOME]
    ]

    return {
        "username": user.username,
        "total_points": activity.total_points if activity else 0,
        "total_distance": str(activity.total_distance) if activity else "0",
        "sessions_completed": sessions.count(),
        "recent_sessions": recent,
        "cards": {
            "unique_owned": UserCard.objects.filter(user=user).count(),
            "catalog_size": Card.objects.count(),
        },
    }
