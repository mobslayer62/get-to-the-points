from decimal import Decimal, ROUND_FLOOR

def convert_distance_to_points(distance, multiplier=1):
    points = (distance / Decimal("10")) * Decimal(str(multiplier))

    return int(points.to_integral_value(rounding=ROUND_FLOOR))

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
