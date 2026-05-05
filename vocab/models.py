# Create your models here.
from django.db import models
from django.contrib.auth.models import User
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
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name="flashcards", null=True, blank=True)
    word = models.CharField(max_length=100)
    definition = models.TextField()

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
