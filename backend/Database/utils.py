from decimal import Decimal, ROUND_FLOOR

def convert_distance_to_points(distance, multiplier=1):
    points = (distance / Decimal("10")) * Decimal(str(multiplier))

    return int(points.to_integral_value(rounding=ROUND_FLOOR))