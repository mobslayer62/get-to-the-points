import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

import random

from . import gacha
from .models import (
    Card, EquippedCard, GachaPull, SessionStart, StoryProgress, UserActivity,
    UserCard, WalkingSession,
)
from .progression import LEVEL_UP_COSTS, MAX_LEVEL, level_up_cost
from .story_data import CHAPTERS, CHARACTERS
from .utils import (
    add_card_to_storage,
    calculate_card_bonuses,
    convert_distance_to_points,
    find_session_problem,
    is_walk,
)

STRONG_PASSWORD = "runFast!2026"


def start_run(client, session_id):
    return client.post(
        "/api/start-session/", {"session_id": session_id}, format="json"
    )


class PointRulesTests(TestCase):
    def test_ten_points_per_hundred_meters(self):
        self.assertEqual(convert_distance_to_points(Decimal("100")), 10)
        self.assertEqual(convert_distance_to_points(Decimal("1000")), 100)

    def test_partial_distance_rounds_down(self):
        self.assertEqual(convert_distance_to_points(Decimal("99.99")), 9)
        self.assertEqual(convert_distance_to_points(Decimal("5")), 0)

    def test_multiplier(self):
        self.assertEqual(convert_distance_to_points(Decimal("1000"), 1.5), 150)

    def test_normal_run_is_accepted(self):
        # 5 km in 30 minutes
        self.assertIsNone(find_session_problem(Decimal("5000"), 1800))

    def test_too_fast_is_rejected(self):
        # 5 km in 5 minutes
        self.assertIsNotNone(find_session_problem(Decimal("5000"), 300))

    def test_too_far_is_rejected(self):
        self.assertIsNotNone(find_session_problem(Decimal("60000"), 6 * 3600))

    def test_short_jitter_session_skips_speed_check(self):
        self.assertIsNone(find_session_problem(Decimal("50"), 2))


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_returns_token_and_creates_activity(self):
        res = self.client.post(
            "/api/register/",
            {"username": "runner1", "password": STRONG_PASSWORD},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        self.assertIn("token", res.data)
        user = User.objects.get(username="runner1")
        self.assertTrue(UserActivity.objects.filter(user=user).exists())

    def test_register_duplicate_username(self):
        User.objects.create_user("runner1", password=STRONG_PASSWORD)
        res = self.client.post(
            "/api/register/",
            {"username": "Runner1", "password": STRONG_PASSWORD},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("username", res.data)

    def test_register_weak_password(self):
        res = self.client.post(
            "/api/register/",
            {"username": "runner2", "password": "123"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("password", res.data)

    def test_login_success(self):
        User.objects.create_user("runner1", password=STRONG_PASSWORD)
        res = self.client.post(
            "/api/login/",
            {"username": "runner1", "password": STRONG_PASSWORD},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["username"], "runner1")
        self.assertIn("token", res.data)

    def test_login_wrong_password(self):
        User.objects.create_user("runner1", password=STRONG_PASSWORD)
        res = self.client.post(
            "/api/login/",
            {"username": "runner1", "password": "wrong"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_logout_invalidates_token(self):
        user = User.objects.create_user("runner1", password=STRONG_PASSWORD)
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.assertEqual(self.client.post("/api/logout/").status_code, 204)
        self.assertEqual(self.client.get("/api/player-stats/").status_code, 401)


class FinishSessionApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("runner1", password=STRONG_PASSWORD)
        token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def post_session(self, **overrides):
        payload = {
            "session_id": str(uuid.uuid4()),
            "distance": "1000.00",
            "steps": 1300,
            "duration_seconds": 600,
        }
        payload.update(overrides)
        start_run(self.client, payload["session_id"])
        return self.client.post("/api/finish-session/", payload, format="json")

    def test_finish_without_start_is_rejected(self):
        res = self.client.post(
            "/api/finish-session/",
            {"session_id": str(uuid.uuid4()), "distance": "100", "duration_seconds": 60},
            format="json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(WalkingSession.objects.count(), 0)

    def test_cannot_finish_someone_elses_started_run(self):
        session_id = str(uuid.uuid4())
        start_run(self.client, session_id)

        other = User.objects.create_user("runner2", password=STRONG_PASSWORD)
        other_client = APIClient()
        other_client.force_authenticate(other)
        res = other_client.post(
            "/api/finish-session/",
            {"session_id": session_id, "distance": "100", "duration_seconds": 60},
            format="json",
        )
        self.assertEqual(res.status_code, 403)

    def test_start_record_is_removed_after_finish(self):
        self.post_session()
        self.assertEqual(SessionStart.objects.count(), 0)

    def test_requires_login(self):
        self.client.credentials()
        self.assertEqual(self.post_session().status_code, 401)

    def test_awards_points_and_saves_session(self):
        res = self.post_session()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["points_earned"], 100)
        self.assertEqual(res.data["total_points"], 100)
        self.assertFalse(res.data["already_processed"])

        session = WalkingSession.objects.get(user=self.user)
        self.assertEqual(session.steps, 1300)
        self.assertEqual(session.duration_seconds, 600)

        activity = UserActivity.objects.get(user=self.user)
        self.assertEqual(activity.total_steps, 1300)

    def test_same_session_twice_awards_once(self):
        session_id = str(uuid.uuid4())
        self.post_session(session_id=session_id)
        res = self.post_session(session_id=session_id)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["already_processed"])
        self.assertEqual(res.data["total_points"], 100)
        self.assertEqual(WalkingSession.objects.count(), 1)

    def test_other_users_session_id_is_forbidden(self):
        session_id = str(uuid.uuid4())
        self.post_session(session_id=session_id)

        other = User.objects.create_user("runner2", password=STRONG_PASSWORD)
        other_token = Token.objects.create(user=other)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {other_token.key}")
        self.assertEqual(self.post_session(session_id=session_id).status_code, 403)

    def test_invalid_session_id(self):
        self.assertEqual(self.post_session(session_id="not-a-uuid").status_code, 400)

    def test_negative_distance(self):
        self.assertEqual(self.post_session(distance="-5").status_code, 400)

    def test_impossible_speed_rejected(self):
        res = self.post_session(distance="5000.00", duration_seconds=60)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(WalkingSession.objects.filter(user=self.user).exists())

    def test_history_and_stats(self):
        self.post_session(distance="500.00")
        self.post_session(distance="1500.00", duration_seconds=900)

        history = self.client.get("/api/activity-history/")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.data["sessions"]), 2)
        self.assertEqual(history.data["total_points"], 200)

        stats = self.client.get("/api/player-stats/")
        self.assertEqual(stats.data["sessions_completed"], 2)
        self.assertEqual(stats.data["longest_session"], "1500.00")


class CardStorageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("player", password="pw")
        self.other = User.objects.create_user("other", password="pw")
        self.fire = Card.objects.create(name="Fire Dragon", rarity="S")
        self.slime = Card.objects.create(name="Slime", rarity="A")

    def test_new_card_is_added_with_quantity_one(self):
        user_card, is_new = add_card_to_storage(self.user, self.fire)
        self.assertTrue(is_new)
        self.assertEqual(user_card.quantity, 1)

    def test_duplicate_increments_quantity(self):
        add_card_to_storage(self.user, self.fire)
        add_card_to_storage(self.user, self.fire)
        user_card, is_new = add_card_to_storage(self.user, self.fire)
        self.assertFalse(is_new)
        self.assertEqual(user_card.quantity, 3)
        self.assertEqual(UserCard.objects.filter(user=self.user).count(), 1)

    def test_storage_is_per_user(self):
        add_card_to_storage(self.user, self.fire)
        _, is_new = add_card_to_storage(self.other, self.fire)
        self.assertTrue(is_new)

    def test_card_storage_endpoint(self):
        add_card_to_storage(self.user, self.fire)
        add_card_to_storage(self.user, self.fire)
        add_card_to_storage(self.user, self.slime)

        client = APIClient()
        client.force_authenticate(self.user)
        res = client.get("/api/card-storage/")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["unique_cards"], 2)
        self.assertEqual(res.data["total_cards"], 3)
        fire = next(c for c in res.data["cards"] if c["name"] == "Fire Dragon")
        self.assertEqual(fire["quantity"], 2)


class HomeSummaryApiTests(TestCase):
    def setUp(self):
        # Migration 0011 seeds the real card catalog; start these tests from
        # an empty catalog so the counts below only see cards made here.
        Card.objects.all().delete()
        self.user = User.objects.create_user("runner1", password=STRONG_PASSWORD)
        token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def post_run(self, distance):
        session_id = str(uuid.uuid4())
        start_run(self.client, session_id)
        return self.client.post(
            "/api/finish-session/",
            {
                "session_id": session_id,
                "distance": distance,
                "steps": 100,
                "duration_seconds": 900,
            },
            format="json",
        )

    def test_requires_login(self):
        self.client.credentials()
        self.assertEqual(self.client.get("/api/home/").status_code, 401)

    def test_new_player_gets_empty_summary(self):
        res = self.client.get("/api/home/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["username"], "runner1")
        self.assertEqual(res.data["total_points"], 0)
        self.assertEqual(res.data["sessions_completed"], 0)
        self.assertEqual(res.data["recent_sessions"], [])
        self.assertEqual(res.data["cards"], {"unique_owned": 0, "catalog_size": 0})

    def test_points_and_recent_runs_newest_first(self):
        for distance in ["100.00", "200.00", "300.00", "400.00"]:
            self.post_run(distance)

        res = self.client.get("/api/home/")
        self.assertEqual(res.data["total_points"], 100)
        self.assertEqual(res.data["sessions_completed"], 4)
        self.assertEqual(
            [s["distance"] for s in res.data["recent_sessions"]],
            ["400.00", "300.00", "200.00"],
        )

    def test_card_counts(self):
        owned = Card.objects.create(name="Morning Jogger", rarity="A")
        Card.objects.create(name="Campus Sprinter", rarity="S")
        add_card_to_storage(self.user, owned)
        add_card_to_storage(self.user, owned)

        res = self.client.get("/api/home/")
        self.assertEqual(res.data["cards"], {"unique_owned": 1, "catalog_size": 2})

    def test_only_own_data(self):
        other = User.objects.create_user("runner2", password=STRONG_PASSWORD)
        WalkingSession.objects.create(user=other, distance=Decimal("500"), points_earned=50)
        res = self.client.get("/api/home/")
        self.assertEqual(res.data["sessions_completed"], 0)


class EquippedCardsApiTests(TestCase):
    URL = "/api/equipped-cards/"

    def setUp(self):
        self.user = User.objects.create_user("runner", password=STRONG_PASSWORD)
        UserActivity.objects.create(user=self.user)
        self.client = APIClient()
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        self.cards = [Card.objects.create(name=f"Card {i}") for i in range(6)]
        for card in self.cards:
            add_card_to_storage(self.user, card)

    def ids(self, n):
        return [c.id for c in self.cards[:n]]

    def test_empty_loadout_by_default(self):
        res = self.client.get(self.URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["max_slots"], 4)
        self.assertEqual(res.data["cards"], [])

    def test_equip_four_cards_in_order(self):
        ids = self.ids(4)[::-1]
        res = self.client.put(self.URL, {"card_ids": ids}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual([c["card_id"] for c in res.data["cards"]], ids)
        self.assertEqual([c["slot"] for c in res.data["cards"]], [1, 2, 3, 4])

    def test_more_than_four_rejected(self):
        res = self.client.put(self.URL, {"card_ids": self.ids(5)}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(EquippedCard.objects.count(), 0)

    def test_duplicates_rejected(self):
        cid = self.cards[0].id
        res = self.client.put(self.URL, {"card_ids": [cid, cid]}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_unowned_card_rejected(self):
        other = Card.objects.create(name="Not mine")
        res = self.client.put(self.URL, {"card_ids": [other.id]}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_put_replaces_and_can_clear(self):
        self.client.put(self.URL, {"card_ids": self.ids(4)}, format="json")
        res = self.client.put(self.URL, {"card_ids": [self.cards[5].id]}, format="json")
        self.assertEqual([c["card_id"] for c in res.data["cards"]], [self.cards[5].id])
        res = self.client.put(self.URL, {"card_ids": []}, format="json")
        self.assertEqual(res.data["cards"], [])

    def finish(self, sid):
        return self.client.post(
            "/api/finish-session/",
            {"session_id": sid, "distance": "500", "duration_seconds": 300},
            format="json",
        )

    def test_loadout_locked_at_start(self):
        self.client.put(self.URL, {"card_ids": self.ids(2)}, format="json")
        sid = str(uuid.uuid4())
        res = start_run(self.client, sid)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(sorted(res.data["equipped_card_ids"]), sorted(self.ids(2)))

        # Swapping cards mid-run doesn't change this run.
        self.client.put(self.URL, {"card_ids": [self.cards[5].id]}, format="json")
        res = self.finish(sid)
        self.assertEqual(sorted(res.data["equipped_card_ids"]), sorted(self.ids(2)))

    def test_retrying_start_keeps_first_loadout(self):
        self.client.put(self.URL, {"card_ids": self.ids(1)}, format="json")
        sid = str(uuid.uuid4())
        start_run(self.client, sid)
        self.client.put(self.URL, {"card_ids": self.ids(3)}, format="json")
        res = start_run(self.client, sid)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["equipped_card_ids"], self.ids(1))

    def test_cannot_restart_finished_run(self):
        sid = str(uuid.uuid4())
        start_run(self.client, sid)
        self.finish(sid)
        self.assertEqual(start_run(self.client, sid).status_code, 400)

    def test_session_snapshots_loadout(self):
        self.client.put(self.URL, {"card_ids": self.ids(2)}, format="json")
        sid = str(uuid.uuid4())
        start_run(self.client, sid)
        self.client.post(
            "/api/finish-session/",
            {"session_id": sid, "distance": "500", "duration_seconds": 300},
            format="json",
        )
        # Changing the loadout later doesn't rewrite the past session.
        self.client.put(self.URL, {"card_ids": []}, format="json")
        session = WalkingSession.objects.get(session_id=sid)
        self.assertEqual(
            sorted(session.equipped_cards.values_list("id", flat=True)),
            sorted(self.ids(2)),
        )

    def test_db_blocks_duplicate_equip(self):
        from django.db import IntegrityError, transaction
        EquippedCard.objects.create(user=self.user, card=self.cards[0], slot=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            EquippedCard.objects.create(user=self.user, card=self.cards[0], slot=2)


class CardBenefitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("runner", password=STRONG_PASSWORD)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.pct25 = Card.objects.create(
            name="Plus 25 Percent", effect_type="points_percent", effect_value=25
        )
        self.pct10 = Card.objects.create(
            name="Plus 10 Percent", effect_type="points_percent", effect_value=10
        )
        self.flat5 = Card.objects.create(
            name="Plus 5 Flat", effect_type="flat_points", effect_value=5
        )
        self.blank = Card.objects.create(name="Blank")
        for card in (self.pct25, self.pct10, self.flat5, self.blank):
            add_card_to_storage(self.user, card)

    def run_with(self, cards, distance="1000"):
        self.client.put(
            "/api/equipped-cards/",
            {"card_ids": [c.id for c in cards]},
            format="json",
        )
        sid = str(uuid.uuid4())
        start_run(self.client, sid)
        return self.client.post(
            "/api/finish-session/",
            {"session_id": sid, "distance": distance, "duration_seconds": 600},
            format="json",
        )

    def test_bonus_math(self):
        total, breakdown = calculate_card_bonuses(
            100, [self.pct25, self.pct10, self.flat5, self.blank]
        )
        self.assertEqual([b["bonus"] for b in breakdown], [25, 10, 5, 0])
        self.assertEqual(total, 40)

    def test_percent_rounds_down(self):
        total, _ = calculate_card_bonuses(9, [self.pct25])  # 2.25 -> 2
        self.assertEqual(total, 2)

    def test_no_cards_no_bonus(self):
        res = self.run_with([])
        self.assertEqual(res.data["base_points"], 100)
        self.assertEqual(res.data["bonus_points"], 0)
        self.assertEqual(res.data["points_earned"], 100)

    def test_run_applies_equipped_card_bonuses(self):
        # 1000 m = 100 base; +25 +10 +5 +0 = 140
        res = self.run_with([self.pct25, self.pct10, self.flat5, self.blank])
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["base_points"], 100)
        self.assertEqual(res.data["bonus_points"], 40)
        self.assertEqual(res.data["points_earned"], 140)
        self.assertEqual(res.data["total_points"], 140)
        self.assertEqual(len(res.data["card_bonuses"]), 4)
        self.assertEqual(UserActivity.objects.get(user=self.user).total_points, 140)

    def test_retry_returns_same_result_without_double_award(self):
        self.client.put(
            "/api/equipped-cards/", {"card_ids": [self.pct25.id]}, format="json"
        )
        sid = str(uuid.uuid4())
        start_run(self.client, sid)
        payload = {"session_id": sid, "distance": "1000", "duration_seconds": 600}
        first = self.client.post("/api/finish-session/", payload, format="json")
        again = self.client.post("/api/finish-session/", payload, format="json")
        self.assertTrue(again.data["already_processed"])
        self.assertEqual(again.data["bonus_points"], first.data["bonus_points"])
        self.assertEqual(again.data["card_bonuses"], first.data["card_bonuses"])
        self.assertEqual(again.data["total_points"], 125)

    def test_cards_api_shows_effects(self):
        res = self.client.get("/api/card-storage/")
        card = next(c for c in res.data["cards"] if c["name"] == "Plus 25 Percent")
        self.assertEqual(card["effect_type"], "points_percent")
        self.assertEqual(card["effect_value"], 25)


class EquippedOwnershipTests(TestCase):
    URL = "/api/equipped-cards/"

    def setUp(self):
        self.user = User.objects.create_user("runner", password=STRONG_PASSWORD)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.cards = [Card.objects.create(name=f"Card {i}") for i in range(4)]
        for card in self.cards:
            add_card_to_storage(self.user, card)
        self.client.put(
            self.URL, {"card_ids": [c.id for c in self.cards]}, format="json"
        )

    def equipped(self):
        return list(
            EquippedCard.objects.filter(user=self.user)
            .order_by("slot")
            .values_list("slot", "card_id")
        )

    def test_losing_a_card_unequips_it_and_closes_gap(self):
        UserCard.objects.get(user=self.user, card=self.cards[1]).delete()
        c = self.cards
        self.assertEqual(self.equipped(), [(1, c[0].id), (2, c[2].id), (3, c[3].id)])

    def test_bulk_losing_cards_unequips_them(self):
        UserCard.objects.filter(
            user=self.user, card__in=[self.cards[0], self.cards[2]]
        ).delete()
        c = self.cards
        self.assertEqual(self.equipped(), [(1, c[1].id), (2, c[3].id)])

    def test_deleting_card_from_game_unequips_it(self):
        self.cards[0].delete()
        self.assertEqual(len(self.equipped()), 3)
        self.assertEqual(self.equipped()[0][0], 1)

    def test_get_removes_unowned_card(self):
        # Simulate a card lost without the signal firing (e.g. raw update).
        UserCard.objects.filter(user=self.user, card=self.cards[0]).update(quantity=0)
        res = self.client.get(self.URL)
        self.assertEqual(
            [c["card_id"] for c in res.data["cards"]],
            [c.id for c in self.cards[1:]],
        )
        self.assertEqual([c["slot"] for c in res.data["cards"]], [1, 2, 3])

    def test_start_never_locks_in_unowned_card(self):
        UserCard.objects.filter(user=self.user, card=self.cards[3]).update(quantity=0)
        res = start_run(self.client, str(uuid.uuid4()))
        self.assertEqual(
            sorted(res.data["equipped_card_ids"]),
            sorted(c.id for c in self.cards[:3]),
        )
        self.assertEqual(len(self.equipped()), 3)

    def test_other_players_loadout_untouched(self):
        other = User.objects.create_user("other", password=STRONG_PASSWORD)
        add_card_to_storage(other, self.cards[0])
        EquippedCard.objects.create(user=other, card=self.cards[0], slot=1)
        UserCard.objects.get(user=self.user, card=self.cards[0]).delete()
        self.assertTrue(EquippedCard.objects.filter(user=other).exists())


class SupportCardEffectTests(TestCase):
    """The five Week 8 shortlist cards, built from passive + special effects."""

    def setUp(self):
        self.user = User.objects.create_user("support", password=STRONG_PASSWORD)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        def make(name, effect_type, effect_value, special_type, value, threshold):
            card = Card.objects.create(
                name=name,
                effect_type=effect_type, effect_value=effect_value,
                special_type=special_type, special_value=value,
                special_threshold=threshold,
            )
            add_card_to_storage(self.user, card)
            return card

        # Passive +15%, +50 every 5 km accumulated
        self.general = make("General", "points_percent", 15,
                            "distance_milestone", 50, 5000)
        # Passive +5%, +10 for a session of 20+ min
        self.physics = make("Physics", "points_percent", 5,
                            "min_duration", 10, 20)
        # Passive +25% on walks, +10 per km walked
        self.delta = make("Delta", "walk_points_percent", 25,
                          "walk_distance", 10, 1000)
        # Passive +5%, +50 for a session of 40+ min
        self.education = make("Education", "points_percent", 5,
                              "min_duration", 50, 40)

    def bonus(self, card, base, **kw):
        _, [entry] = calculate_card_bonuses(base, [card], **kw)
        return entry["passive_bonus"], entry["special_bonus"]

    def test_walk_or_run_by_average_speed(self):
        self.assertTrue(is_walk(3000, 30 * 60))   # 1.67 m/s
        self.assertFalse(is_walk(3000, 15 * 60))  # 3.33 m/s
        self.assertTrue(is_walk(150, 0))          # untimed short run

    def test_distance_milestone_counts_lifetime_distance(self):
        # 4.5 km before, +1 km now -> passes 5 km once
        self.assertEqual(self.bonus(self.general, 100, distance=1000,
                                    previous_total_distance=4500), (15, 50))
        # 5.5 km before, +1 km now -> no new milestone
        self.assertEqual(self.bonus(self.general, 100, distance=1000,
                                    previous_total_distance=5500), (15, 0))
        # 0 -> 11 km in one go passes 5 km and 10 km
        self.assertEqual(self.bonus(self.general, 1100, distance=11000), (165, 100))

    def test_min_duration(self):
        self.assertEqual(self.bonus(self.physics, 100, duration_seconds=20 * 60), (5, 10))
        self.assertEqual(self.bonus(self.physics, 100, duration_seconds=20 * 60 - 1), (5, 0))
        self.assertEqual(self.bonus(self.education, 100, duration_seconds=40 * 60), (5, 50))
        self.assertEqual(self.bonus(self.education, 100, duration_seconds=39 * 60), (5, 0))

    def test_walk_only_card(self):
        # 2.5 km walk in 30 min: +25% of 250 = 62, 2 full km = +20
        self.assertEqual(self.bonus(self.delta, 250, distance=2500,
                                    duration_seconds=30 * 60), (62, 20))
        # same distance as a run in 10 min: nothing
        self.assertEqual(self.bonus(self.delta, 250, distance=2500,
                                    duration_seconds=10 * 60), (0, 0))

    def test_run_only_cards(self):
        steady = Card.objects.create(
            name="Steady runner",
            effect_type="run_points_percent", effect_value=15,
            special_type="run_distance", special_value=5, special_threshold=1000,
        )
        long_run = Card.objects.create(
            name="Distance runner",
            effect_type="run_points_percent", effect_value=10,
            special_type="run_distance", special_value=40, special_threshold=5000,
        )
        # 5 km run in 30 min (2.78 m/s): base 500
        run = {"distance": 5000, "duration_seconds": 30 * 60}
        self.assertEqual(self.bonus(steady, 500, **run), (75, 25))
        self.assertEqual(self.bonus(long_run, 500, **run), (50, 40))
        # 3 km run: no full 5 km yet
        self.assertEqual(self.bonus(long_run, 300, distance=3000,
                                    duration_seconds=18 * 60), (30, 0))
        # Same 5 km as a walk (60 min): nothing
        walk = {"distance": 5000, "duration_seconds": 60 * 60}
        self.assertEqual(self.bonus(steady, 500, **walk), (0, 0))
        self.assertEqual(self.bonus(long_run, 500, **walk), (0, 0))

    def finish_run(self, cards, distance, duration_seconds, started_seconds_ago):
        self.client.put("/api/equipped-cards/",
                        {"card_ids": [c.id for c in cards]}, format="json")
        sid = str(uuid.uuid4())
        start_run(self.client, sid)
        SessionStart.objects.filter(session_id=sid).update(
            started_at=timezone.now() - timedelta(seconds=started_seconds_ago)
        )
        return self.client.post("/api/finish-session/", {
            "session_id": sid, "distance": distance,
            "duration_seconds": duration_seconds,
        }, format="json")

    def test_full_run_through_api(self):
        # 3 km walk in 45 min: base 300
        res = self.finish_run([self.general, self.physics, self.delta, self.education],
                       "3000", 45 * 60, 46 * 60)
        self.assertEqual(res.status_code, 200)
        by_name = {c["name"]: c["bonus"] for c in res.data["card_bonuses"]}
        self.assertEqual(by_name, {
            "General": 45,         # 15%, no 5 km milestone yet
            "Physics": 15 + 10,
            "Delta": 75 + 30,
            "Education": 15 + 50,
        })
        self.assertEqual(res.data["points_earned"], 300 + 45 + 25 + 105 + 65)

    def test_milestone_triggers_on_later_run(self):
        self.finish_run([self.general], "3000", 30 * 60, 31 * 60)
        res = self.finish_run([self.general], "3000", 30 * 60, 31 * 60)  # 6 km total
        self.assertEqual(res.data["card_bonuses"][0]["special_bonus"], 50)

    def test_claimed_duration_capped_by_real_time(self):
        # Claims 40 min, but the run was started only 5 min ago.
        res = self.finish_run([self.education], "500", 40 * 60, 5 * 60)
        self.assertEqual(res.data["card_bonuses"][0]["special_bonus"], 0)

    def test_retry_returns_saved_breakdown(self):
        self.client.put("/api/equipped-cards/",
                        {"card_ids": [self.general.id]}, format="json")
        sid = str(uuid.uuid4())
        start_run(self.client, sid)
        payload = {"session_id": sid, "distance": "6000", "duration_seconds": 3600}
        first = self.client.post("/api/finish-session/", payload, format="json")
        again = self.client.post("/api/finish-session/", payload, format="json")
        self.assertEqual(first.data["card_bonuses"][0]["special_bonus"], 50)
        self.assertEqual(again.data["card_bonuses"], first.data["card_bonuses"])

    def test_card_storage_shows_special(self):
        res = self.client.get("/api/card-storage/")
        card = next(c for c in res.data["cards"] if c["name"] == "General")
        self.assertEqual(card["special_type"], "distance_milestone")
        self.assertEqual(card["special_value"], 50)
        self.assertEqual(card["special_threshold"], 5000)


class LevelAndStoryRulesTests(TestCase):
    def test_costs_match_design(self):
        self.assertEqual(LEVEL_UP_COSTS, {1: 100, 2: 200, 3: 350, 4: 500})
        self.assertEqual(MAX_LEVEL, 5)

    def test_no_cost_at_max_level(self):
        self.assertIsNone(level_up_cost(MAX_LEVEL))

    def test_three_placeholder_chapters(self):
        self.assertEqual(
            [(c["title"], c["required_level"]) for c in CHAPTERS],
            [
                ("Chapter 1: Placeholder title", 1),
                ("Chapter 2: Placeholder title", 3),
                ("Chapter 3: Placeholder title", 5),
            ],
        )

    def test_placeholder_dialogue_alternates_a_and_b(self):
        for chapter in CHAPTERS:
            self.assertEqual(
                [line["text"] for line in chapter["lines"]],
                ["Dialog A1", "Dialog B1", "Dialog A2", "Dialog B2", "Dialog A3", "Dialog B3"],
            )
            self.assertEqual(
                [line["speaker"] for line in chapter["lines"]],
                ["person_a", "person_b"] * 3,
            )

    def test_every_speaker_is_a_known_character(self):
        for chapter in CHAPTERS:
            for line in chapter["lines"]:
                self.assertIn(line["speaker"], CHARACTERS)


class LevelAndStoryApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("storyrunner", password=STRONG_PASSWORD)
        token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def give_points(self, points):
        activity, _ = UserActivity.objects.get_or_create(user=self.user)
        activity.total_points = points
        activity.save()

    def activity(self):
        return UserActivity.objects.get(user=self.user)

    # ----- level -----

    def test_new_player_is_level_1(self):
        res = self.client.get("/api/level/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["level"], 1)
        self.assertEqual(res.data["next_level_cost"], 100)
        self.assertFalse(res.data["can_level_up"])
        self.assertEqual(res.data["next_unlock"]["chapter_id"], "chapter-2")

    def test_level_up_spends_points(self):
        self.give_points(150)
        res = self.client.post("/api/level/up/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["points_spent"], 100)
        self.assertEqual(res.data["level"]["level"], 2)
        self.assertEqual(self.activity().total_points, 50)

    def test_not_enough_points(self):
        self.give_points(99)
        res = self.client.post("/api/level/up/")
        self.assertEqual(res.status_code, 400)
        self.assertIn("1 more points", res.data["error"])
        self.assertEqual(self.activity().level, 1)
        self.assertEqual(self.activity().total_points, 99)

    def test_full_climb_to_max_level(self):
        self.give_points(100 + 200 + 350 + 500)
        unlocked = []
        for _ in range(4):
            res = self.client.post("/api/level/up/")
            self.assertEqual(res.status_code, 200)
            unlocked += [c["id"] for c in res.data["unlocked_chapters"]]

        self.assertEqual(self.activity().level, 5)
        self.assertEqual(self.activity().total_points, 0)
        self.assertEqual(unlocked, ["chapter-2", "chapter-3"])

        res = self.client.post("/api/level/up/")
        self.assertEqual(res.status_code, 400)
        self.assertIn("maximum", res.data["error"])

    def test_level_requires_login(self):
        self.client.credentials()
        self.assertEqual(self.client.post("/api/level/up/").status_code, 401)

    # ----- story -----

    def test_story_list(self):
        res = self.client.get("/api/story/")
        self.assertEqual(res.status_code, 200)
        chapters = res.data["chapters"]
        self.assertEqual(
            {c["id"]: c["unlocked"] for c in chapters},
            {"chapter-1": True, "chapter-2": False, "chapter-3": False},
        )
        self.assertEqual(chapters[0]["number"], 1)
        self.assertEqual(chapters[0]["thumbnail"]["name"], "Person A")

    def test_read_unlocked_chapter(self):
        res = self.client.get("/api/story/chapter-1/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            [(m["key"], m["position"]) for m in res.data["cast"]],
            [("person_a", "left"), ("person_b", "right")],
        )
        self.assertEqual(res.data["cast"][0]["name"], "Person A")
        self.assertEqual(res.data["lines"][0], {"speaker": "person_a", "text": "Dialog A1"})

    def test_locked_chapter_is_forbidden(self):
        res = self.client.get("/api/story/chapter-2/")
        self.assertEqual(res.status_code, 403)
        self.assertIn("level 3", res.data["error"])

    def test_chapter_unlocks_after_level_up(self):
        self.give_points(300)
        self.client.post("/api/level/up/")
        self.client.post("/api/level/up/")
        self.assertEqual(self.client.get("/api/story/chapter-2/").status_code, 200)

    def test_unknown_chapter(self):
        self.assertEqual(self.client.get("/api/story/nope/").status_code, 404)

    def test_complete_chapter_once(self):
        first = self.client.post("/api/story/chapter-1/complete/")
        second = self.client.post("/api/story/chapter-1/complete/")
        self.assertTrue(first.data["first_time"])
        self.assertFalse(second.data["first_time"])
        self.assertEqual(StoryProgress.objects.filter(user=self.user).count(), 1)

        res = self.client.get("/api/story/")
        done = {c["id"]: c["completed"] for c in res.data["chapters"]}
        self.assertTrue(done["chapter-1"])

    def test_cannot_complete_locked_chapter(self):
        res = self.client.post("/api/story/chapter-3/complete/")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(StoryProgress.objects.count(), 0)

    def test_home_shows_level_and_story(self):
        res = self.client.get("/api/home/")
        self.assertEqual(res.data["level"]["level"], 1)
        self.assertEqual(res.data["story"]["unlocked"], 1)
        self.assertEqual(res.data["story"]["total"], 3)
        self.assertEqual(res.data["story"]["next_to_read"], "Chapter 1: Placeholder title")


class LevelTabApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("levelrunner", password=STRONG_PASSWORD)
        token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def set_progress(self, points, level=1):
        activity, _ = UserActivity.objects.get_or_create(user=self.user)
        activity.total_points = points
        activity.level = level
        activity.save()

    def test_levels_list_costs_and_rewards(self):
        res = self.client.get("/api/level/")
        self.assertEqual(res.status_code, 200)
        levels = res.data["levels"]
        self.assertEqual([lv["level"] for lv in levels], [1, 2, 3, 4, 5])
        self.assertEqual([lv["cost"] for lv in levels], [None, 100, 200, 350, 500])
        self.assertEqual([lv["total_cost"] for lv in levels], [0, 100, 300, 650, 1150])
        self.assertEqual(
            [[r["id"] for r in lv["rewards"]] for lv in levels],
            [["chapter-1"], [], ["chapter-2"], [], ["chapter-3"]],
        )

    def test_levels_list_state(self):
        self.set_progress(0, level=3)
        levels = self.client.get("/api/level/").data["levels"]
        self.assertEqual([lv["reached"] for lv in levels], [True, True, True, False, False])
        self.assertEqual([lv["current"] for lv in levels], [False, False, True, False, False])

    def test_next_level_rewards_empty_when_none(self):
        data = self.client.get("/api/level/").data
        self.assertEqual(data["next_level"], 2)
        self.assertEqual(data["next_level_rewards"], [])

    def test_next_level_rewards_lists_chapter(self):
        self.set_progress(0, level=2)
        data = self.client.get("/api/level/").data
        self.assertEqual(data["next_level"], 3)
        self.assertEqual(
            data["next_level_rewards"],
            [{"type": "chapter", "id": "chapter-2", "title": "Chapter 2: Placeholder title"}],
        )

    def test_max_level_has_no_next(self):
        self.set_progress(0, level=5)
        data = self.client.get("/api/level/").data
        self.assertIsNone(data["next_level"])
        self.assertIsNone(data["next_level_cost"])
        self.assertEqual(data["next_level_rewards"], [])

    def test_story_list_level_includes_next_rewards(self):
        self.set_progress(250, level=2)
        level = self.client.get("/api/story/").data["level"]
        self.assertTrue(level["can_level_up"])
        self.assertEqual(level["next_level_rewards"][0]["id"], "chapter-2")


class FixedRng:
    """Fake random source for tests: random() cycles through `values`,
    choice() always takes the first item."""

    def __init__(self, values):
        self.values = list(values)
        self.i = 0

    def random(self):
        value = self.values[self.i % len(self.values)]
        self.i += 1
        return value

    def choice(self, seq):
        return seq[0]


ROLL_A = 0.5    # 50  -> A
ROLL_AP = 0.1   # 10  -> A+
ROLL_S = 0.01   # 1   -> S


class GachaRulesTests(TestCase):
    """Uses the 10 cards seeded by migration 0011 (2 S, 3 A+, 5 A)."""

    def setUp(self):
        self.user = User.objects.create_user("gacharunner", password=STRONG_PASSWORD)
        self.activity = UserActivity.objects.create(user=self.user, total_points=1000)

    def refresh(self):
        self.activity.refresh_from_db()
        return self.activity

    def test_design_numbers(self):
        self.assertEqual(gacha.SINGLE_PULL_COST, 20)
        self.assertEqual(gacha.TEN_PULL_COST, 180)
        self.assertEqual(dict(gacha.RATES), {"S": 2, "A+": 18, "A": 80})
        self.assertEqual(gacha.PITY_PULLS, 50)

    def test_seeded_catalog_has_every_rarity(self):
        counts = {r: Card.objects.filter(rarity=r).count() for r in ["S", "A+", "A"]}
        self.assertEqual(counts, {"S": 2, "A+": 3, "A": 5})

    def test_roll_rates_over_many_pulls(self):
        rng = random.Random(42)
        n = 100_000
        rolls = [gacha.roll_rarity(rng) for _ in range(n)]
        self.assertAlmostEqual(rolls.count("S") / n * 100, 2, delta=0.3)
        self.assertAlmostEqual(rolls.count("A+") / n * 100, 18, delta=0.8)
        self.assertAlmostEqual(rolls.count("A") / n * 100, 80, delta=0.8)

    def test_single_pull_spends_points_and_stores_card(self):
        results, activity = gacha.pull(self.user, 1, FixedRng([ROLL_A]))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["rarity"], "A")
        self.assertTrue(results[0]["is_new"])
        self.assertEqual(self.refresh().total_points, 980)
        self.assertEqual(self.activity.total_pulls, 1)
        self.assertEqual(self.activity.pulls_since_s, 1)
        self.assertEqual(UserCard.objects.filter(user=self.user).count(), 1)
        self.assertEqual(GachaPull.objects.filter(user=self.user).count(), 1)

    def test_ten_pull_costs_180(self):
        results, _ = gacha.pull(self.user, 10, random.Random(1))
        self.assertEqual(len(results), 10)
        self.assertEqual(self.refresh().total_points, 820)
        self.assertEqual(self.activity.total_pulls, 10)

    def test_not_enough_points_changes_nothing(self):
        self.activity.total_points = 19
        self.activity.save()
        with self.assertRaises(gacha.GachaError):
            gacha.pull(self.user, 1, FixedRng([ROLL_A]))
        self.assertEqual(self.refresh().total_points, 19)
        self.assertEqual(UserCard.objects.count(), 0)
        self.assertEqual(GachaPull.objects.count(), 0)

    def test_only_1_or_10(self):
        with self.assertRaises(gacha.GachaError):
            gacha.pull(self.user, 5, FixedRng([ROLL_A]))

    def test_duplicate_adds_quantity(self):
        gacha.pull(self.user, 1, FixedRng([ROLL_A]))
        results, _ = gacha.pull(self.user, 1, FixedRng([ROLL_A]))
        self.assertFalse(results[0]["is_new"])
        self.assertEqual(UserCard.objects.get(user=self.user).quantity, 2)

    def test_pity_on_50th_pull(self):
        self.activity.pulls_since_s = 49
        self.activity.save()
        results, activity = gacha.pull(self.user, 1, FixedRng([ROLL_A]))
        self.assertEqual(results[0]["rarity"], "S")
        self.assertTrue(results[0]["pity"])
        self.assertEqual(activity.pulls_since_s, 0)
        self.assertTrue(GachaPull.objects.get(user=self.user).was_pity)

    def test_pity_prefers_unowned_s(self):
        first_s, second_s = Card.objects.filter(rarity="S").order_by("id")
        UserCard.objects.create(user=self.user, card=first_s)
        self.activity.pulls_since_s = 49
        self.activity.save()
        results, _ = gacha.pull(self.user, 1, FixedRng([ROLL_A]))
        self.assertEqual(results[0]["card_id"], second_s.id)
        self.assertTrue(results[0]["is_new"])

    def test_pity_gives_any_s_when_all_owned(self):
        for card in Card.objects.filter(rarity="S"):
            UserCard.objects.create(user=self.user, card=card)
        self.activity.pulls_since_s = 49
        self.activity.save()
        results, _ = gacha.pull(self.user, 1, FixedRng([ROLL_A]))
        self.assertEqual(results[0]["rarity"], "S")
        self.assertFalse(results[0]["is_new"])

    def test_lucky_s_resets_counter(self):
        self.activity.pulls_since_s = 10
        self.activity.save()
        results, activity = gacha.pull(self.user, 1, FixedRng([ROLL_S]))
        self.assertEqual(results[0]["rarity"], "S")
        self.assertFalse(results[0]["pity"])
        self.assertEqual(activity.pulls_since_s, 0)

    def test_pity_inside_a_ten_pull(self):
        self.activity.pulls_since_s = 45
        self.activity.save()
        results, activity = gacha.pull(self.user, 10, FixedRng([ROLL_A]))
        self.assertEqual(results[4]["rarity"], "S")
        self.assertTrue(results[4]["pity"])
        self.assertEqual(activity.pulls_since_s, 5)

    def test_ten_pull_guarantees_a_plus(self):
        results, _ = gacha.pull(self.user, 10, FixedRng([ROLL_A]))
        self.assertEqual([r["rarity"] for r in results[:9]], ["A"] * 9)
        self.assertEqual(results[9]["rarity"], "A+")
        self.assertTrue(results[9]["guaranteed"])

    def test_no_guarantee_needed_if_a_plus_already_pulled(self):
        results, _ = gacha.pull(self.user, 10, FixedRng([ROLL_AP] + [ROLL_A] * 9))
        self.assertEqual(results[0]["rarity"], "A+")
        self.assertEqual(results[9]["rarity"], "A")
        self.assertFalse(results[9]["guaranteed"])

    def test_empty_catalog(self):
        Card.objects.all().delete()
        with self.assertRaises(gacha.GachaError):
            gacha.pull(self.user, 1, FixedRng([ROLL_A]))
        self.assertEqual(self.refresh().total_points, 1000)

    def test_missing_rarity_falls_back(self):
        Card.objects.filter(rarity="S").delete()
        results, _ = gacha.pull(self.user, 1, FixedRng([ROLL_S]))
        self.assertEqual(results[0]["rarity"], "A+")


class GachaApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("gachaapi", password=STRONG_PASSWORD)
        token = Token.objects.create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        UserActivity.objects.create(user=self.user, total_points=200)

    def test_info(self):
        res = self.client.get("/api/gacha/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["single_cost"], 20)
        self.assertEqual(res.data["ten_cost"], 180)
        self.assertTrue(res.data["can_ten"])
        self.assertEqual(res.data["pulls_until_pity"], 50)
        self.assertEqual(len(res.data["pool"]["S"]), 2)

    def test_pull_one(self):
        res = self.client.post("/api/gacha/pull/", {"count": 1}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["results"]), 1)
        self.assertIn("name", res.data["results"][0])
        self.assertEqual(res.data["gacha"]["points"], 180)

    def test_pull_ten(self):
        res = self.client.post("/api/gacha/pull/", {"count": 10}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["results"]), 10)
        self.assertEqual(res.data["gacha"]["points"], 20)
        rarities = [r["rarity"] for r in res.data["results"]]
        self.assertTrue(any(r in ("A+", "S") for r in rarities))

    def test_not_enough_points(self):
        self.client.post("/api/gacha/pull/", {"count": 10}, format="json")
        res = self.client.post("/api/gacha/pull/", {"count": 10}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("more points", res.data["error"])

    def test_bad_count(self):
        res = self.client.post("/api/gacha/pull/", {"count": "lots"}, format="json")
        self.assertEqual(res.status_code, 400)
        res = self.client.post("/api/gacha/pull/", {"count": 3}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_requires_login(self):
        self.client.credentials()
        self.assertEqual(self.client.post("/api/gacha/pull/", {"count": 1}).status_code, 401)

    def test_pulled_cards_show_in_storage(self):
        self.client.post("/api/gacha/pull/", {"count": 10}, format="json")
        storage = self.client.get("/api/card-storage/").data
        self.assertEqual(storage["total_cards"], 10)

    def test_home_shows_pity(self):
        res = self.client.get("/api/home/")
        self.assertEqual(res.data["gacha"]["pulls_until_pity"], 50)



class OnboardingTests(TestCase):
    """Starter card, Chapter 1 card, tutorial and its one-time run bonus."""

    def register(self, username="newplayer"):
        client = APIClient()
        res = client.post(
            "/api/register/",
            {"username": username, "password": STRONG_PASSWORD},
            format="json",
        )
        self.assertEqual(res.status_code, 201)
        client.credentials(HTTP_AUTHORIZATION=f"Token {res.data['token']}")
        return client, User.objects.get(username=username)

    def owned_names(self, user):
        return set(
            UserCard.objects.filter(user=user).values_list("card__name", flat=True)
        )

    # ----- cards -----

    def test_sign_up_gives_starter_card(self):
        _, user = self.register()
        self.assertEqual(self.owned_names(user), {"NTHU Main Gate"})

    def test_sign_up_still_works_without_starter_card(self):
        Card.objects.filter(name="NTHU Main Gate").delete()
        _, user = self.register()
        self.assertEqual(self.owned_names(user), set())

    def test_chapter_1_gives_office_of_global_affairs_once(self):
        client, user = self.register()
        first = client.post("/api/story/chapter-1/complete/")
        self.assertEqual([r["name"] for r in first.data["rewards"]], ["Office of Global Affairs"])
        self.assertEqual(first.data["rewards"][0]["rarity"], "A")

        second = client.post("/api/story/chapter-1/complete/")
        self.assertEqual(second.data["rewards"], [])
        card = UserCard.objects.get(user=user, card__name="Office of Global Affairs")
        self.assertEqual(card.quantity, 1)

    def test_other_chapters_give_no_card(self):
        client, user = self.register()
        activity = UserActivity.objects.get(user=user)
        activity.level = 3
        activity.save()
        res = client.post("/api/story/chapter-2/complete/")
        self.assertEqual(res.data["rewards"], [])

    # ----- tutorial -----

    def test_tutorial_steps(self):
        client, _ = self.register("daniel")
        data = client.get("/api/tutorial/").data
        steps = data["steps"]
        self.assertEqual(steps[0]["id"], "welcome")
        self.assertEqual(steps[-1]["id"], "end")
        profile = next(s for s in steps if s["id"] == "profile")
        self.assertIn("daniel", profile["text"])
        for step in steps:
            self.assertNotIn("{", step["text"])
            if step["mode"] in ("tap", "run"):
                self.assertTrue(step["target"])
                self.assertTrue(step["advance_on"])
        self.assertEqual([s["mode"] for s in steps].count("run"), 1)
        self.assertEqual(data["starter_card_name"], "NTHU Main Gate")
        self.assertEqual(data["bonus_points"], 100)
        self.assertFalse(data["bonus_claimed"])

    def test_tutorial_capture_text_uses_real_prices(self):
        client, _ = self.register()
        steps = client.get("/api/tutorial/").data["steps"]
        text = next(s for s in steps if s["id"] == "capture_explained")["text"]
        self.assertIn("20 points", text)
        self.assertIn("180 points instead of 200", text)

    def test_run_bonus_only_once(self):
        client, user = self.register()
        first = client.post("/api/tutorial/run-bonus/")
        self.assertEqual(first.data["awarded"], 100)
        self.assertEqual(first.data["total_points"], 100)

        second = client.post("/api/tutorial/run-bonus/")
        self.assertEqual(second.data["awarded"], 0)
        self.assertEqual(UserActivity.objects.get(user=user).total_points, 100)
        self.assertTrue(client.get("/api/tutorial/").data["bonus_claimed"])

    def test_tutorial_requires_login(self):
        client = APIClient()
        self.assertEqual(client.get("/api/tutorial/").status_code, 401)
        self.assertEqual(client.post("/api/tutorial/run-bonus/").status_code, 401)
