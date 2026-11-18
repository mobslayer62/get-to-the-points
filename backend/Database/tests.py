import uuid
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Card, UserActivity, UserCard, WalkingSession
from .utils import add_card_to_storage, convert_distance_to_points, find_session_problem

STRONG_PASSWORD = "runFast!2026"


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
        return self.client.post("/api/finish-session/", payload, format="json")

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
