"""
New-player rewards and the tutorial.

- Signing up gives the starter support card.
- Finishing certain chapters for the first time gives a card
  (story_data.CHAPTER_REWARDS).
- The tutorial's run step gives a one-time bonus, whether the player
  runs or skips.
"""
from django.db import transaction

from . import gacha
from .models import Card, UserActivity
from .story_data import CHAPTER_REWARDS
from .tutorial_data import TUTORIAL_STEPS
from .utils import add_card_to_storage

STARTER_CARD_NAME = "NTHU Main Gate"
TUTORIAL_RUN_BONUS = 100


def give_card_by_name(user, name):
    """Add one copy of the named card. Returns the Card, or None if missing."""
    card = Card.objects.filter(name=name).first()
    if card is None:
        return None
    add_card_to_storage(user, card)
    return card


def give_starter_card(user):
    return give_card_by_name(user, STARTER_CARD_NAME)


def grant_chapter_rewards(user, chapter_id):
    """
    Give a chapter's rewards. Call only the first time it is completed.
    Returns the cards given, in the card-storage shape.
    """
    given = []
    for reward in CHAPTER_REWARDS.get(chapter_id, []):
        if reward["type"] == "card":
            card = give_card_by_name(user, reward["name"])
            if card is not None:
                given.append({"type": "card", **gacha.card_payload(card)})
    return given


def _fill(text, values):
    return text.format_map(values)


def tutorial_for(user):
    """The tutorial steps with this player's name and the current numbers."""
    activity, _ = UserActivity.objects.get_or_create(user=user)
    values = {
        "username": user.username,
        "bonus": TUTORIAL_RUN_BONUS,
        "single_cost": gacha.SINGLE_PULL_COST,
        "ten_size": gacha.TEN_PULL_SIZE,
        "ten_cost": gacha.TEN_PULL_COST,
        "ten_full_price": gacha.SINGLE_PULL_COST * gacha.TEN_PULL_SIZE,
        "pity_minus_one": gacha.PITY_PULLS - 1,
    }
    steps = [
        {
            "id": step["id"],
            "text": _fill(step["text"], values),
            "target": step["target"],
            "mode": step["mode"],
            "advance_on": step.get("advance_on"),
        }
        for step in TUTORIAL_STEPS
    ]
    return {
        "steps": steps,
        "starter_card_name": STARTER_CARD_NAME,
        "bonus_points": TUTORIAL_RUN_BONUS,
        "bonus_claimed": activity.tutorial_bonus_claimed,
    }


def claim_tutorial_run_bonus(user):
    """
    Give the tutorial run bonus once per player.
    Returns (points_awarded, activity); points_awarded is 0 if already claimed.
    """
    with transaction.atomic():
        UserActivity.objects.get_or_create(user=user)
        activity = UserActivity.objects.select_for_update().get(user=user)
        if activity.tutorial_bonus_claimed:
            return 0, activity
        activity.total_points += TUTORIAL_RUN_BONUS
        activity.tutorial_bonus_claimed = True
        activity.save(update_fields=["total_points", "tutorial_bonus_claimed"])
    return TUTORIAL_RUN_BONUS, activity
