from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify


class Unit(models.Model):
    title = models.CharField(max_length=150)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Flashcard(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='flashcards', null=True, blank=True)
    word = models.CharField(max_length=100)
    definition = models.TextField()
    part_of_speech = models.CharField(max_length=40, blank=True)
    ipa = models.CharField(max_length=120, blank=True, verbose_name='IPA pronunciation')
    example = models.TextField(blank=True, verbose_name='Example sentence')

    def __str__(self):
        return self.word


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    total_score = models.IntegerField(default=0)
    words_mastered = models.IntegerField(default=0)

    def __str__(self):
        return self.user.username


class UnitProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)
    accuracy = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('user', 'unit')


class FlashcardReview(models.Model):
    """SM-2 spaced-repetition state per user per card."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    flashcard = models.ForeignKey(Flashcard, on_delete=models.CASCADE, related_name='reviews')
    ease_factor = models.FloatField(default=2.5)
    interval = models.PositiveIntegerField(default=1)   # days until next review
    repetitions = models.PositiveIntegerField(default=0)
    next_review = models.DateField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'flashcard')

    def record(self, quality: int):
        """Update SM-2 state. quality: 0–5 (0-2 = fail, 3-5 = pass)."""
        if quality >= 3:
            if self.repetitions == 0:
                self.interval = 1
            elif self.repetitions == 1:
                self.interval = 6
            else:
                self.interval = round(self.interval * self.ease_factor)
            self.repetitions += 1
        else:
            self.repetitions = 0
            self.interval = 1

        self.ease_factor = max(1.3, self.ease_factor + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        self.next_review = (timezone.now() + timezone.timedelta(days=self.interval)).date()
        self.save()
