"""
Level and story rules.

Players spend points to level up. Each level unlocks story chapters
(see story_data.py). All checks happen here on the server.
"""
from django.db import transaction

from .models import StoryProgress, UserActivity
from .story_data import CHAPTERS, CHAPTERS_BY_ID, character_info

MAX_LEVEL = 5

# Cost to go FROM this level to the next one.
LEVEL_UP_COSTS = {
    1: 100,
    2: 200,
    3: 350,
    4: 500,
}


class ProgressionError(Exception):
    """A rule was broken; the message is safe to show to the player."""


def level_up_cost(level):
    """Points needed to leave `level`, or None at the max level."""
    if level >= MAX_LEVEL:
        return None
    return LEVEL_UP_COSTS[level]


def chapters_unlocked_at(level):
    """Chapters that become available exactly at `level`."""
    return [c for c in CHAPTERS if c["required_level"] == level]


def level_rewards(level):
    """
    What the player gets on reaching `level`.
    Each reward is {"type", "id", "title"}; only chapters for now, but
    other reward types (e.g. gacha tickets) can be added here later.
    """
    return [
        {"type": "chapter", "id": c["id"], "title": c["title"]}
        for c in chapters_unlocked_at(level)
    ]


def levels_overview(activity):
    """Every level from 1 to MAX_LEVEL with its cost, rewards and state."""
    levels = []
    total = 0
    for level in range(1, MAX_LEVEL + 1):
        cost = level_up_cost(level - 1) if level > 1 else None
        total += cost or 0
        levels.append({
            "level": level,
            "cost": cost,              # points to reach it from the level below
            "total_cost": total,       # points to reach it from level 1
            "rewards": level_rewards(level),
            "reached": level <= activity.level,
            "current": level == activity.level,
        })
    return levels


def is_unlocked(chapter, level):
    return level >= chapter["required_level"]


def get_activity(user):
    activity, _ = UserActivity.objects.get_or_create(user=user)
    return activity


def level_summary(activity):
    level = activity.level
    cost = level_up_cost(level)
    upcoming = [c for c in CHAPTERS if c["required_level"] > level]
    next_unlock = min(upcoming, key=lambda c: c["required_level"]) if upcoming else None

    next_level = level + 1 if level < MAX_LEVEL else None

    return {
        "level": level,
        "max_level": MAX_LEVEL,
        "next_level": next_level,
        "next_level_rewards": level_rewards(next_level) if next_level else [],
        "points": activity.total_points,
        "next_level_cost": cost,
        "points_needed": max(cost - activity.total_points, 0) if cost else 0,
        "can_level_up": cost is not None and activity.total_points >= cost,
        "next_unlock": (
            {
                "chapter_id": next_unlock["id"],
                "title": next_unlock["title"],
                "required_level": next_unlock["required_level"],
            }
            if next_unlock else None
        ),
    }


def level_up(user):
    """
    Spend points to go up one level.

    Returns (activity, points_spent, newly_unlocked_chapters).
    Raises ProgressionError if at max level or short of points.
    """
    with transaction.atomic():
        get_activity(user)
        activity = UserActivity.objects.select_for_update().get(user=user)

        cost = level_up_cost(activity.level)
        if cost is None:
            raise ProgressionError("You are already at the maximum level.")
        if activity.total_points < cost:
            raise ProgressionError(
                f"You need {cost - activity.total_points} more points to level up."
            )

        activity.total_points -= cost
        activity.level += 1
        activity.save(update_fields=["total_points", "level"])

    return activity, cost, chapters_unlocked_at(activity.level)


def story_overview(user):
    """The chapter list with each chapter's lock and completion state."""
    activity = get_activity(user)
    completed = set(
        StoryProgress.objects.filter(user=user).values_list("chapter_id", flat=True)
    )

    chapters = [
        {
            "id": c["id"],
            "number": c["number"],
            "title": c["title"],
            "summary": c["summary"],
            # the chapter's chosen thumbnail, or else its first cast member
            "thumbnail": character_info(c.get("thumbnail") or c["cast"][0]["character"]),
            "required_level": c["required_level"],
            "unlocked": is_unlocked(c, activity.level),
            "completed": c["id"] in completed,
            "line_count": len(c["lines"]),
        }
        for c in CHAPTERS
    ]
    return activity, chapters


def readable_chapter(user, chapter_id):
    """
    The chapter if the player may read it.

    Raises KeyError for an unknown id, ProgressionError if still locked.
    """
    chapter = CHAPTERS_BY_ID[chapter_id]
    activity = get_activity(user)
    if not is_unlocked(chapter, activity.level):
        raise ProgressionError(
            f"Reach level {chapter['required_level']} to unlock {chapter['title']}."
        )
    return chapter


def chapter_for_reader(chapter):
    """What the reader needs: who is on screen, and the lines in order."""
    return {
        "id": chapter["id"],
        "number": chapter["number"],
        "title": chapter["title"],
        "cast": [
            {**character_info(m["character"]), "position": m["position"]}
            for m in chapter["cast"]
        ],
        "lines": chapter["lines"],
    }


def complete_chapter(user, chapter_id):
    """Mark a chapter as read. Returns True the first time only."""
    readable_chapter(user, chapter_id)
    _, created = StoryProgress.objects.get_or_create(user=user, chapter_id=chapter_id)
    return created
