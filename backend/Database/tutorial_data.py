"""
The first-time tutorial, step by step.

The app fetches this list from GET /api/tutorial/ and plays it on top of
the real screens, so the wording can be changed here without rebuilding
the app.

Each step
- id:          unique name
- text:        what the text box says; "{username}" is filled in per player
- target:      what to spotlight. None = nothing (centred text box),
               "back" = the back arrow in the top-left corner,
               anything else = a widget in the app tagged with that name
- mode:        "info" -> the player taps Next
               "tap"  -> only the highlighted button works; the step ends
                         when the app reports `advance_on`
               "run"  -> the run step: the player may run, or skip the run;
                         both end with the one-time tutorial bonus
- advance_on:  app event that finishes a "tap" or "run" step
"""

TUTORIAL_STEPS = [
    {
        "id": "welcome",
        "text": "Hello, and welcome to Get to the Points! Let's get started.",
        "target": None,
        "mode": "info",
    },
    {
        "id": "about",
        "text": (
            "Get to the Points is a game about exploring NTHU. You play as a "
            "new student finding your way around campus. As you walk and run, "
            "you earn points: 1 point for every 10 meters you travel. Points "
            "can be used for many different things, but we'll get to that later."
        ),
        "target": None,
        "mode": "info",
    },
    {
        "id": "main_menu",
        "text": "Let's start by looking around the main menu.",
        "target": None,
        "mode": "info",
    },
    {
        "id": "profile",
        "text": (
            "This is you, {username}! Tap this button any time to open your "
            "profile and settings."
        ),
        "target": "home_profile",
        "mode": "info",
    },
    {
        "id": "points",
        "text": "This is how many points you have right now.",
        "target": "home_points",
        "mode": "info",
    },
    {
        "id": "level_button",
        "text": "This is your level. Try tapping it!",
        "target": "home_level",
        "mode": "tap",
        "advance_on": "open_level",
    },
    {
        "id": "level_explained",
        "text": (
            "In Get to the Points, you can spend the points you've collected "
            "to level up. Each level brings rewards and unlocks the next part "
            "of the story."
        ),
        "target": "level_card",
        "mode": "info",
    },
    {
        "id": "back_from_level",
        "text": "Let's go back to the main menu. Tap the back arrow.",
        "target": "back",
        "mode": "tap",
        "advance_on": "home",
    },
    {
        "id": "cards_button",
        "text": "This is the Cards menu. Try tapping it!",
        "target": "home_cards",
        "mode": "tap",
        "advance_on": "open_cards",
    },
    {
        "id": "cards_explained",
        "text": (
            "This menu shows the support cards you own. Support cards are "
            "unique cards that give you extra points on your runs. We've given "
            "you your first one, the NTHU Main Gate, to get you started!"
        ),
        "target": None,
        "mode": "info",
    },
    {
        "id": "cards_unique",
        "text": (
            "Every support card is different. Some boost your walks, some "
            "boost your runs, and some reward long distances, so make sure you "
            "equip the ones that suit how you move around campus."
        ),
        "target": None,
        "mode": "info",
    },
    {
        "id": "back_from_cards",
        "text": "Let's go back to the main menu.",
        "target": "back",
        "mode": "tap",
        "advance_on": "home",
    },
    {
        "id": "start_run_button",
        "text": "This is the Start Tracking button. Try tapping it!",
        "target": "home_start_run",
        "mode": "tap",
        "advance_on": "open_run",
    },
    {
        "id": "run_slots",
        "text": (
            "These are your support card slots. You can bring up to 4 cards on "
            "each run. Tap a slot to equip a card."
        ),
        "target": "run_slot",
        "mode": "tap",
        "advance_on": "open_equip",
    },
    {
        "id": "equip_card",
        "text": "Tap your NTHU Main Gate card to put it in a slot.",
        "target": "equip_starter_card",
        "mode": "tap",
        "advance_on": "equip_selected",
    },
    {
        "id": "equip_save",
        "text": "Now tap Save to keep your loadout.",
        "target": "equip_save",
        "mode": "tap",
        "advance_on": "equip_saved",
    },
    {
        "id": "back_to_run",
        "text": "Nice! Now go back to the Distance Tracking screen.",
        "target": "back",
        "mode": "tap",
        "advance_on": "run_returned",
    },
    {
        "id": "run",
        "text": (
            "Your card is equipped! When you're ready to walk or run, tap "
            "Start Tracking, then tap Stop Tracking when you finish. No time right now? "
            "You can skip the run. Either way, you'll get {bonus} bonus points "
            "for your first tutorial."
        ),
        "target": "run_start_button",
        "mode": "run",
        "advance_on": "run_saved",
    },
    {
        "id": "run_result",
        "text": (
            "Here you can see how many points you earned from the run, and how "
            "they add up."
        ),
        "target": "run_result",
        "mode": "info",
    },
    {
        "id": "back_from_run",
        "text": "Let's go back to the main menu.",
        "target": "back",
        "mode": "tap",
        "advance_on": "home",
    },
    {
        "id": "capture_button",
        "text": "This is the Capture tab. Try tapping it!",
        "target": "home_capture",
        "mode": "tap",
        "advance_on": "open_capture",
    },
    {
        "id": "capture_explained",
        "text": (
            "Here you can capture places around campus and add them to your "
            "collection as support cards. Each capture costs {single_cost} "
            "points, but capturing {ten_size} at once costs only {ten_cost} "
            "points instead of {ten_full_price}."
        ),
        "target": None,
        "mode": "info",
    },
    {
        "id": "capture_pity",
        "text": (
            "S cards are rare, but if you go {pity_minus_one} captures without "
            "one, your next capture is guaranteed to be an S card."
        ),
        "target": None,
        "mode": "info",
    },
    {
        "id": "back_from_capture",
        "text": "Let's go back to the main menu.",
        "target": "back",
        "mode": "tap",
        "advance_on": "home",
    },
    {
        "id": "stats_button",
        "text": "This is the Stats tab. Try tapping it!",
        "target": "home_stats",
        "mode": "tap",
        "advance_on": "open_stats",
    },
    {
        "id": "stats_explained",
        "text": "This is where you can see your past runs and activity history.",
        "target": None,
        "mode": "info",
    },
    {
        "id": "back_from_stats",
        "text": "Let's go back to the main menu.",
        "target": "back",
        "mode": "tap",
        "advance_on": "home",
    },
    {
        "id": "story_button",
        "text": "Finally, this is the Story tab. Try tapping it!",
        "target": "home_story",
        "mode": "tap",
        "advance_on": "open_story",
    },
    {
        "id": "story_explained",
        "text": (
            "This is your journey at NTHU. You need to reach certain levels to "
            "unlock and continue the story. Finish Chapter 1 to get another "
            "support card!"
        ),
        "target": None,
        "mode": "info",
    },
    {
        "id": "back_from_story",
        "text": "Let's go back to the main menu.",
        "target": "back",
        "mode": "tap",
        "advance_on": "home",
    },
    {
        "id": "end",
        "text": (
            "That's the end of the tutorial. You can replay it any time with "
            "the Tutorial button on the main menu. Have fun, and get to the points!"
        ),
        "target": None,
        "mode": "info",
    },
]

MODES = ("info", "tap", "run")


def _check_steps():
    """Fail fast at server start if a step is malformed."""
    ids = [step["id"] for step in TUTORIAL_STEPS]
    if len(ids) != len(set(ids)):
        raise ValueError("Two tutorial steps share the same id.")
    for step in TUTORIAL_STEPS:
        if step["mode"] not in MODES:
            raise ValueError(f"Tutorial step {step['id']}: bad mode")
        if step["mode"] in ("tap", "run") and not step.get("advance_on"):
            raise ValueError(f"Tutorial step {step['id']}: needs advance_on")
        if step["mode"] in ("tap", "run") and not step.get("target"):
            raise ValueError(f"Tutorial step {step['id']}: needs a target")


_check_steps()
