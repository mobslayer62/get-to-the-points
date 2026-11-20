import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Card, EquippedCard, SessionStart, UserActivity, UserCard, WalkingSession
from .utils import (
    add_card_to_storage,
    calculate_card_bonuses,
    convert_distance_to_points,
    find_session_problem,
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
