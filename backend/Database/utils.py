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
