"""
Story content for the visual-novel reader.

The chapter text lives in story_chapters.py as easy-to-edit scripts, which
story_script.py turns into reader lines. This file says who the characters
are and how the chapters are set up. Character art is still placeholder.

CHARACTERS  key -> how the character looks on screen
  name:   shown on the speaker tag
  color:  placeholder sprite colour (hex), until real sprite images exist
  sprite: image path for later (empty = draw the placeholder)

CHAPTERS    shown in the story list, in this order
  id:             stable key saved in StoryProgress (don't rename after release)
  number, title:  shown in the list
  summary:        one line under the title
  required_level: level the player must reach to read it
  cast:           who can appear, and where ("left" | "center" | "right")
  thumbnail:      character shown next to the chapter in the list
  lines:          [{"speaker": <character key, or "" for narration>, "text": ...,
                    "scene": <place name>, "on_stage": [<character keys>]}]
"""

from .story_chapters import CHAPTER_1, CHAPTER_2, CHAPTER_3
from .story_script import parse_script

CHARACTERS = {
    "me": {"name": "Me", "color": "#4A90D9", "sprite": ""},
    "student": {"name": "Varsity Jacket Guy", "color": "#7B4FA0", "sprite": ""},
    "roommate": {"name": "Roommate", "color": "#E0736A", "sprite": ""},
    "classmate": {"name": "Classmate", "color": "#E39B2D", "sprite": ""},
    "professor": {"name": "Professor", "color": "#5B6B78", "sprite": ""},
}

POSITIONS = ("left", "center", "right")


def _chapter(number, title, summary, required_level, cast, thumbnail, script):
    """Build one chapter; `cast` is [(character key, position), ...]."""
    chapter_id = f"chapter-{number}"
    keys = [key for key, _ in cast]
    return {
        "id": chapter_id,
        "number": number,
        "title": f"Chapter {number}: {title}",
        "summary": summary,
        "required_level": required_level,
        "cast": [{"character": key, "position": pos} for key, pos in cast],
        "thumbnail": thumbnail,
        "lines": parse_script(script, keys, name=chapter_id),
    }


CHAPTERS = [
    _chapter(
        1, "Get to the Point",
        "Day one at NTHU: a big suitcase, a fresh start, and not quite enough Chinese.",
        required_level=1,
        cast=[("me", "left"), ("student", "right")],
        thumbnail="student",
        script=CHAPTER_1,
    ),
    _chapter(
        2, "A Clean Slate",
        "Moving into Hsin Dorm and meeting the roommates.",
        required_level=3,
        cast=[("me", "left"), ("roommate", "right")],
        thumbnail="roommate",
        script=CHAPTER_2,
    ),
    _chapter(
        3, "The Starting Line",
        "Four weeks in, and the midterm is next week.",
        required_level=5,
        cast=[("me", "left"), ("professor", "center"), ("classmate", "right")],
        thumbnail="classmate",
        script=CHAPTER_3,
    ),
]

CHAPTERS_BY_ID = {chapter["id"]: chapter for chapter in CHAPTERS}

# Given the first time a player finishes a chapter (see onboarding.py).
# "card" rewards use the card's exact name from the Card table.
CHAPTER_REWARDS = {
    "chapter-1": [{"type": "card", "name": "Office of Global Affairs"}],
}


def character_info(key):
    """Public view of one character, as sent to the app."""
    c = CHARACTERS[key]
    return {"key": key, "name": c["name"], "color": c["color"], "sprite": c["sprite"]}


def _check_story():
    """Fail fast at server start if the story data is malformed."""
    if len(CHAPTERS_BY_ID) != len(CHAPTERS):
        raise ValueError("Two chapters share the same id.")
    for chapter in CHAPTERS:
        cid = chapter["id"]
        if not chapter["lines"]:
            raise ValueError(f"{cid} has no lines.")
        cast = {member["character"] for member in chapter["cast"]}
        for member in chapter["cast"]:
            if member["character"] not in CHARACTERS:
                raise ValueError(f"{cid}: unknown character {member['character']}")
            if member["position"] not in POSITIONS:
                raise ValueError(f"{cid}: bad position {member['position']}")
        if chapter.get("thumbnail") and chapter["thumbnail"] not in cast:
            raise ValueError(f"{cid}: thumbnail {chapter['thumbnail']} is not in the cast")
        positions = [member["position"] for member in chapter["cast"]]
        if len(set(positions)) != len(positions):
            raise ValueError(f"{cid}: two characters stand in the same place")
        for line in chapter["lines"]:
            if not line.get("text"):
                raise ValueError(f"{cid}: a line has no text")
            speaker = line.get("speaker", "")
            if speaker and speaker not in cast:
                raise ValueError(f"{cid}: speaker {speaker} is not in the cast")
            if not set(line.get("on_stage", [])) <= cast:
                raise ValueError(f"{cid}: someone on stage is not in the cast")
    for chapter_id, rewards in CHAPTER_REWARDS.items():
        if chapter_id not in CHAPTERS_BY_ID:
            raise ValueError(f"Rewards for unknown chapter {chapter_id}")
        for reward in rewards:
            if reward.get("type") != "card" or not reward.get("name"):
                raise ValueError(f"Bad reward for {chapter_id}: {reward}")


_check_story()
