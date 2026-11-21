"""
Gacha rules (shown to players as "Capture").

Players spend points to pull cards from the catalog (the Card table).
Every number the team may want to tune is at the top of this file.

Rules
- Single pull: SINGLE_PULL_COST points. Ten-pull: TEN_PULL_COST points.
- Each pull rolls a rarity with RATES, then picks a card of that rarity
  with equal chance.
- Pity: the PITY_PULLS-th pull in a row without an S is a guaranteed S.
  A pity S prefers an S card the player doesn't own yet. Any S resets
  the counter. Normal (lucky) S pulls stay fully random.
- Ten-pull guarantee: if the first nine cards of a ten-pull are all A,
  the tenth is at least A+.
- Duplicates add 1 to the card's quantity (utils.add_card_to_storage).
"""
import random

from django.db import transaction

from .models import Card, GachaPull, UserActivity, UserCard
from .utils import add_card_to_storage

SINGLE_PULL_COST = 20
TEN_PULL_SIZE = 10
TEN_PULL_COST = 180

# Percent chance per pull, rarest first. Must add up to 100.
RATES = [
    ("S", 2),
    ("A+", 18),
    ("A", 80),
]

PITY_PULLS = 50

# Order used to "upgrade" a rarity, lowest first
RARITY_ORDER = ["A", "A+", "S"]

PULL_COSTS = {1: SINGLE_PULL_COST, TEN_PULL_SIZE: TEN_PULL_COST}

_system_rng = random.SystemRandom()


class GachaError(Exception):
    """A rule was broken; the message is safe to show to the player."""


def _check_rates():
    if sum(percent for _, percent in RATES) != 100:
        raise ValueError("Gacha RATES must add up to 100.")
    if {rarity for rarity, _ in RATES} != set(RARITY_ORDER):
        raise ValueError("Gacha RATES must cover every rarity once.")


_check_rates()


def roll_rarity(rng=None):
    """Roll one rarity using RATES."""
    rng = rng or _system_rng
    roll = rng.random() * 100
    running = 0
    for rarity, percent in RATES:
        running += percent
        if roll < running:
            return rarity
    return RATES[-1][0]


def _catalog_by_rarity():
    """{rarity: [cards]} in a stable order (by id)."""
    pools = {rarity: [] for rarity in RARITY_ORDER}
    for card in Card.objects.order_by("id"):
        pools.setdefault(card.rarity, []).append(card)
    return pools


def _available_rarity(rarity, pools):
    """
    The rolled rarity, or the nearest one that has cards
    (in case the catalog is missing a rarity).
    """
    if pools.get(rarity):
        return rarity
    start = RARITY_ORDER.index(rarity)
    # look downward first, then upward
    for r in RARITY_ORDER[start::-1] + RARITY_ORDER[start + 1:]:
        if pools.get(r):
            return r
    raise GachaError("There are no cards to capture yet.")


def _pick_card(pool, rng, prefer_ids_not_in=None):
    """Pick a card; if prefer_ids_not_in is given, unowned cards come first."""
    if prefer_ids_not_in is not None:
        unowned = [c for c in pool if c.id not in prefer_ids_not_in]
        if unowned:
            pool = unowned
    return rng.choice(pool)


def card_payload(card, quantity=None):
    """Card fields in the same shape as the card-storage endpoint."""
    data = {
        "card_id": card.id,
        "name": card.name,
        "description": card.description,
        "rarity": card.rarity,
        "image_url": card.image_url,
        "effect_type": card.effect_type,
        "effect_value": card.effect_value,
        "special_type": card.special_type,
        "special_value": card.special_value,
        "special_threshold": card.special_threshold,
    }
    if quantity is not None:
        data["quantity"] = quantity
    return data


def gacha_info(activity):
    """What the gacha screen shows: costs, rates, pity and the card pool."""
    pools = _catalog_by_rarity()
    points = activity.total_points
    return {
        "points": points,
        "single_cost": SINGLE_PULL_COST,
        "ten_cost": TEN_PULL_COST,
        "ten_size": TEN_PULL_SIZE,
        "can_single": points >= SINGLE_PULL_COST,
        "can_ten": points >= TEN_PULL_COST,
        "rates": [{"rarity": r, "percent": p} for r, p in RATES],
        "pity_pulls": PITY_PULLS,
        "pulls_since_s": activity.pulls_since_s,
        "pulls_until_pity": max(PITY_PULLS - activity.pulls_since_s, 1),
        "total_pulls": activity.total_pulls,
        "pool": {
            rarity: [card.name for card in pools.get(rarity, [])]
            for rarity, _ in RATES
        },
    }


def pull(user, count, rng=None):
    """
    Spend points and pull `count` cards (1 or TEN_PULL_SIZE).

    Returns (results, activity). Raises GachaError if the player can't pull.
    Everything happens in one transaction: either the points are spent and
    every card is added, or nothing changes.
    """
    rng = rng or _system_rng
    cost = PULL_COSTS.get(count)
    if cost is None:
        raise GachaError(f"You can capture 1 or {TEN_PULL_SIZE} cards at a time.")

    pools = _catalog_by_rarity()
    if not any(pools.values()):
        raise GachaError("There are no cards to capture yet.")

    with transaction.atomic():
        UserActivity.objects.get_or_create(user=user)
        activity = UserActivity.objects.select_for_update().get(user=user)

        if activity.total_points < cost:
            raise GachaError(
                f"You need {cost - activity.total_points} more points for this capture."
            )
        activity.total_points -= cost

        owned_ids = set(
            UserCard.objects.filter(user=user).values_list("card_id", flat=True)
        )
        results = []

        for i in range(count):
            activity.pulls_since_s += 1
            activity.total_pulls += 1

            is_pity = activity.pulls_since_s >= PITY_PULLS
            rarity = "S" if is_pity else roll_rarity(rng)

            # Ten-pull guarantee: nine A's in a row -> the tenth is at least A+
            is_guarantee = (
                count == TEN_PULL_SIZE
                and i == count - 1
                and rarity == "A"
                and all(r["rarity"] == "A" for r in results)
            )
            if is_guarantee:
                rarity = "A+"

            rarity = _available_rarity(rarity, pools)
            card = _pick_card(
                pools[rarity], rng,
                prefer_ids_not_in=owned_ids if is_pity else None,
            )

            if card.rarity == "S":
                activity.pulls_since_s = 0

            user_card, is_new = add_card_to_storage(user, card)
            owned_ids.add(card.id)
            GachaPull.objects.create(
                user=user, card=card, rarity=card.rarity, was_pity=is_pity
            )

            results.append({
                **card_payload(card),
                "is_new": is_new,
                "pity": is_pity,
                "guaranteed": is_guarantee,
            })

        activity.save(update_fields=["total_points", "pulls_since_s", "total_pulls"])

    return results, activity
