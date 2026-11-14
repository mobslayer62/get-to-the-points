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
