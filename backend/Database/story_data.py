"""
Story content for the visual-novel reader.

Everything here is PLACEHOLDER text and art to test the reader and the
unlock rules. Replace it when the real story is written; the app needs no
changes as long as the shape stays the same.

CHARACTERS  key -> how the character looks on screen
  name:   shown on the speaker tag
  color:  placeholder sprite colour (hex), until real sprite images exist
  sprite: image path for later (empty = draw the placeholder)

CHAPTERS    shown in the story list, in this order
  id:             stable key saved in StoryProgress (don't rename after release)
  number, title:  shown in the list
  required_level: level the player must reach to read it
  cast:           who stands on screen, and where ("left" | "center" | "right")
  lines:          [{"speaker": <character key, or "" for narration>, "text": ...}]
"""

CHARACTERS = {
    "person_a": {"name": "Person A", "color": "#4A90D9", "sprite": ""},
    "person_b": {"name": "Person B", "color": "#E0736A", "sprite": ""},
}

POSITIONS = ("left", "center", "right")


def _placeholder_dialogue():
    """Person A and Person B take turns: A1, B1, A2, B2, A3, B3."""
    lines = []
    for i in range(1, 4):
        lines.append({"speaker": "person_a", "text": f"Dialog A{i}"})
        lines.append({"speaker": "person_b", "text": f"Dialog B{i}"})
    return lines


def _placeholder_chapter(number, required_level):
    return {
        "id": f"chapter-{number}",
        "number": number,
        "title": f"Chapter {number}: Placeholder title",
        "summary": "Placeholder summary.",
        "required_level": required_level,
        "cast": [
            {"character": "person_a", "position": "left"},
            {"character": "person_b", "position": "right"},
        ],
        "lines": _placeholder_dialogue(),
    }


CHAPTERS = [
    _placeholder_chapter(1, required_level=1),
    _placeholder_chapter(2, required_level=3),
    _placeholder_chapter(3, required_level=5),
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
        for line in chapter["lines"]:
            if not line.get("text"):
                raise ValueError(f"{cid}: a line has no text")
            speaker = line.get("speaker", "")
            if speaker and speaker not in cast:
                raise ValueError(f"{cid}: speaker {speaker} is not in the cast")
    for chapter_id, rewards in CHAPTER_REWARDS.items():
        if chapter_id not in CHAPTERS_BY_ID:
            raise ValueError(f"Rewards for unknown chapter {chapter_id}")
        for reward in rewards:
            if reward.get("type") != "card" or not reward.get("name"):
                raise ValueError(f"Bad reward for {chapter_id}: {reward}")


_check_story()
