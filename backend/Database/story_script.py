"""
Turns a chapter script (plain text, easy to write and edit) into the list of
lines the story reader shows, one text box per line.

Script format, one entry per line:

    [scene: Hsin Dorm]         the place shown at the top of the stage
    [enter: me]                a character steps onto the stage
    [enter: me, roommate]      several at once
    [exit: student]            a character leaves the stage
    me: “Hi!”                  a line spoken (or thought) by a character
    The bus drove away.        anything else is narration (no speaker)
    # a comment                ignored, like blank lines

A speaker must be on stage before they talk, and only characters in the
chapter's cast can enter. Mistakes raise ScriptError with the line number,
so a broken script stops the server at start-up instead of showing up
half-broken in the app.

Each parsed line looks like:
    {"speaker": "me", "text": "...", "scene": "Hsin Dorm", "on_stage": ["me"]}
"""

import re

DIRECTIVE = re.compile(r"^\[(scene|enter|exit)\s*:\s*(.*?)\s*\]$")
SPEAKER = re.compile(r"^([a-z][a-z0-9_]*)\s*:\s*(.+)$")


class ScriptError(ValueError):
    """A chapter script could not be parsed."""


def _keys(value):
    """'me, roommate' -> ['me', 'roommate']"""
    return [key.strip() for key in value.split(",") if key.strip()]


def parse_script(script, cast, name="script"):
    """
    Parse `script` for a chapter whose cast is the list of character keys
    `cast`. `name` is only used in error messages (e.g. "chapter-1").
    """
    cast = list(cast)
    scene = ""
    on_stage = []
    lines = []

    def fail(number, message):
        raise ScriptError(f"{name}, script line {number}: {message}")

    for number, raw in enumerate(script.splitlines(), start=1):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue

        directive = DIRECTIVE.match(text)
        if directive:
            kind, value = directive.groups()
            if kind == "scene":
                scene = value
                continue
            keys = _keys(value)
            if not keys:
                fail(number, f"[{kind}] needs a character")
            for key in keys:
                if key not in cast:
                    fail(number, f"'{key}' is not in this chapter's cast {cast}")
                if kind == "enter":
                    if key in on_stage:
                        fail(number, f"'{key}' is already on stage")
                    on_stage.append(key)
                else:
                    if key not in on_stage:
                        fail(number, f"'{key}' is not on stage, so can't exit")
                    on_stage.remove(key)
            continue

        if text.startswith("["):
            fail(number, f"unknown command {text!r} (use scene, enter or exit)")

        speaker = ""
        spoken = SPEAKER.match(text)
        if spoken:
            speaker, text = spoken.groups()
            if speaker not in cast:
                fail(number, f"unknown speaker '{speaker}'")
            if speaker not in on_stage:
                fail(number, f"'{speaker}' speaks but is not on stage (add [enter: {speaker}])")

        lines.append({
            "speaker": speaker,
            "text": text.strip(),
            "scene": scene,
            "on_stage": [key for key in cast if key in on_stage],
        })

    if not lines:
        raise ScriptError(f"{name}: the script has no lines")
    return lines


def word_count(lines):
    """Rough reading length of a parsed chapter."""
    return sum(len(line["text"].split()) for line in lines)
