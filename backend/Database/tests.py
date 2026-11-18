from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Card, UserCard
from .utils import add_card_to_storage


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
