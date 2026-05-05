from django.utils import timezone

from .models import FlashcardReview


def due_review_count(request):
    if not request.user.is_authenticated:
        return {}
    count = FlashcardReview.objects.filter(
        user=request.user,
        next_review__lte=timezone.now().date(),
    ).count()
    return {'due_review_count': count}
