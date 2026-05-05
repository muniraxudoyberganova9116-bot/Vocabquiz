import json

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from .models import Flashcard, FlashcardReview, Profile, Unit, UnitProgress
from .views import grade_quiz, XP_PER_UNIT, MASTERY_THRESHOLD


def _make_unit_with_cards(n=5):
    unit = Unit.objects.create(title='Test Unit', slug='test-unit')
    cards = [Flashcard.objects.create(unit=unit, word=f'word{i}', definition=f'def{i}') for i in range(n)]
    return unit, cards


class GradeQuizTests(TestCase):
    def setUp(self):
        self.unit, self.cards = _make_unit_with_cards(4)

    def test_all_correct(self):
        payload = {
            'mc': [{'question_id': c.id, 'selected_id': c.id} for c in self.cards[:2]],
            'matches': [{'word_id': c.id, 'def_id': c.id} for c in self.cards[2:]],
        }
        accuracy, *_ = grade_quiz(self.cards, payload)
        self.assertEqual(accuracy, 100.0)

    def test_all_wrong(self):
        other_id = self.cards[-1].id + 999
        payload = {
            'mc': [{'question_id': c.id, 'selected_id': other_id} for c in self.cards[:2]],
            'matches': [{'word_id': c.id, 'def_id': other_id} for c in self.cards[2:]],
        }
        accuracy, *_ = grade_quiz(self.cards, payload)
        self.assertEqual(accuracy, 0.0)

    def test_empty_payload_returns_none(self):
        accuracy, *_ = grade_quiz(self.cards, {})
        self.assertIsNone(accuracy)

    def test_invalid_card_ids_score_zero(self):
        # IDs not in this unit can't be correct, so they score 0%
        payload = {
            'mc': [{'question_id': 99999, 'selected_id': 99999}],
            'matches': [],
        }
        accuracy, *_ = grade_quiz(self.cards, payload)
        self.assertEqual(accuracy, 0.0)


class ReplayProtectionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', password='pw')
        self.unit, self.cards = _make_unit_with_cards(4)
        self.client.login(username='testuser', password='pw')

    def _submit(self, correct=True):
        payload = {
            'mc': [{'question_id': c.id, 'selected_id': c.id if correct else 0}
                   for c in self.cards[:2]],
            'matches': [{'word_id': c.id, 'def_id': c.id if correct else 0}
                        for c in self.cards[2:]],
        }
        return self.client.post(
            reverse('quiz_detail', args=[self.unit.slug]),
            {'answers': json.dumps(payload)},
        )

    def test_first_submission_accepted(self):
        resp = self._submit()
        self.assertEqual(resp.status_code, 200)

    def test_immediate_resubmit_blocked(self):
        self._submit()
        resp = self._submit()
        self.assertEqual(resp.status_code, 400)

    def test_xp_not_awarded_if_score_does_not_improve(self):
        self._submit(correct=True)
        profile = Profile.objects.get(user=self.user)
        first_xp = profile.total_score

        # Manually clear cooldown so we can resubmit
        session = self.client.session
        session[f'quiz_last_{self.unit.id}'] = 0
        session.save()

        self._submit(correct=True)
        profile.refresh_from_db()
        self.assertEqual(profile.total_score, first_xp)


class MasteryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('masteruser', password='pw')
        self.unit, self.cards = _make_unit_with_cards(4)
        self.client.login(username='masteruser', password='pw')

    def _submit_perfect(self):
        payload = {
            'mc': [{'question_id': c.id, 'selected_id': c.id} for c in self.cards[:2]],
            'matches': [{'word_id': c.id, 'def_id': c.id} for c in self.cards[2:]],
        }
        return self.client.post(
            reverse('quiz_detail', args=[self.unit.slug]),
            {'answers': json.dumps(payload)},
        )

    def test_mastery_is_sticky(self):
        self._submit_perfect()
        progress = UnitProgress.objects.get(user=self.user, unit=self.unit)
        self.assertTrue(progress.is_completed)

        # Manually clear cooldown and re-submit with wrong answers
        session = self.client.session
        session[f'quiz_last_{self.unit.id}'] = 0
        session.save()

        bad_payload = {
            'mc': [{'question_id': c.id, 'selected_id': 0} for c in self.cards[:2]],
            'matches': [{'word_id': c.id, 'def_id': 0} for c in self.cards[2:]],
        }
        self.client.post(
            reverse('quiz_detail', args=[self.unit.slug]),
            {'answers': json.dumps(bad_payload)},
        )
        progress.refresh_from_db()
        self.assertTrue(progress.is_completed)

    def test_words_mastered_incremented_once(self):
        self._submit_perfect()
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.words_mastered, len(self.cards))

        session = self.client.session
        session[f'quiz_last_{self.unit.id}'] = 0
        session.save()

        self._submit_perfect()
        profile.refresh_from_db()
        self.assertEqual(profile.words_mastered, len(self.cards))


class AuthTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_logout_requires_post(self):
        User.objects.create_user('u', password='pw')
        self.client.login(username='u', password='pw')
        resp = self.client.get(reverse('logout'))
        self.assertNotEqual(resp.status_code, 302)

    def test_duplicate_register_shows_error(self):
        User.objects.create_user('existing', password='pw')
        resp = self.client.post(reverse('register'), {
            'username': 'existing', 'password': 'pw2',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'already taken')

    def test_register_with_email(self):
        resp = self.client.post(reverse('register'), {
            'username': 'newuser', 'email': 'new@example.com', 'password': 'pass123',
        })
        self.assertRedirects(resp, reverse('unit_hub'))
        user = User.objects.get(username='newuser')
        self.assertEqual(user.email, 'new@example.com')


class SpacedRepetitionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('sruser', password='pw')
        self.unit, self.cards = _make_unit_with_cards(3)

    def test_correct_answer_increases_interval(self):
        card = self.cards[0]
        review = FlashcardReview.objects.create(user=self.user, flashcard=card)
        review.record(5)
        self.assertGreaterEqual(review.interval, 1)
        self.assertEqual(review.repetitions, 1)

    def test_wrong_answer_resets_interval(self):
        card = self.cards[0]
        review = FlashcardReview.objects.create(user=self.user, flashcard=card, repetitions=5, interval=30)
        review.record(1)
        self.assertEqual(review.interval, 1)
        self.assertEqual(review.repetitions, 0)

    def test_quiz_creates_review_records(self):
        client = Client()
        client.login(username='sruser', password='pw')
        payload = {
            'mc': [{'question_id': c.id, 'selected_id': c.id} for c in self.cards[:2]],
            'matches': [{'word_id': self.cards[2].id, 'def_id': self.cards[2].id}],
        }
        client.post(
            reverse('quiz_detail', args=[self.unit.slug]),
            {'answers': json.dumps(payload)},
        )
        self.assertEqual(FlashcardReview.objects.filter(user=self.user).count(), len(self.cards))
