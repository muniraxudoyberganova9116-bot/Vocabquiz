import json
import time

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.http import HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Flashcard, FlashcardReview, Unit, Profile, UnitProgress

# ─── constants ────────────────────────────────────────────────────────────────
XP_PER_UNIT = 30
MASTERY_THRESHOLD = 80.0
QUIZ_COOLDOWN_SECONDS = 20
LEADERBOARD_PAGE_SIZE = 20


# ─── helpers ──────────────────────────────────────────────────────────────────

def _get_or_create_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def grade_quiz(cards, payload):
    """
    Grade a quiz submission and return (accuracy, mc_correct, mc_total,
    match_correct, match_total).  Pure function — no DB writes.
    """
    valid_ids = {c.id for c in cards}

    mc_answers = payload.get('mc', []) if isinstance(payload, dict) else []
    match_attempts = payload.get('matches', []) if isinstance(payload, dict) else []

    mc_total = len(mc_answers)
    mc_correct = 0
    for ans in mc_answers:
        q_id = ans.get('question_id')
        s_id = ans.get('selected_id')
        if q_id in valid_ids and s_id in valid_ids and q_id == s_id:
            mc_correct += 1

    match_total = len(match_attempts)
    match_correct = 0
    for m in match_attempts:
        w_id = m.get('word_id')
        d_id = m.get('def_id')
        if w_id in valid_ids and d_id in valid_ids and w_id == d_id:
            match_correct += 1

    total = mc_total + match_total
    if total == 0:
        return None, mc_correct, mc_total, match_correct, match_total

    accuracy = round(((mc_correct + match_correct) / total) * 100, 2)
    return accuracy, mc_correct, mc_total, match_correct, match_total


# ─── auth ─────────────────────────────────────────────────────────────────────

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        if not username or not password:
            return render(request, 'vocab/register.html',
                          {'error': 'Username and password are required.'})
        try:
            user = User.objects.create_user(username=username, email=email, password=password)
        except IntegrityError:
            return render(request, 'vocab/register.html',
                          {'error': 'That username is already taken.'})
        Profile.objects.create(user=user)
        login(request, user)
        return redirect('unit_hub')
    return render(request, 'vocab/register.html')


def login_user(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('unit_hub')
        return render(request, 'vocab/login.html', {'error': 'Invalid credentials.'})
    return render(request, 'vocab/login.html')


@require_POST
def logout_user(request):
    logout(request)
    return redirect('home')


# ─── pages ────────────────────────────────────────────────────────────────────

def home(request):
    context = {}
    if request.user.is_authenticated:
        profile = _get_or_create_profile(request.user)
        progress_qs = (
            UnitProgress.objects
            .filter(user=request.user)
            .select_related('unit')
            .order_by('-id')
        )
        progress_list = list(progress_qs)
        completed = sum(1 for p in progress_list if p.is_completed)
        total_units = Unit.objects.count()

        last_progress = progress_list[0] if progress_list else None
        next_unit = (
            Unit.objects
            .exclude(id__in=[p.unit_id for p in progress_list if p.is_completed])
            .first()
        )
        resume_unit = last_progress.unit if last_progress else next_unit

        context.update({
            'profile': profile,
            'completed_units': completed,
            'total_units': total_units,
            'resume_unit': resume_unit,
            'last_progress': last_progress,
        })
    return render(request, 'vocab/index.html', context)


@login_required(login_url='login')
def unit_hub(request):
    units = list(Unit.objects.prefetch_related('flashcards').all())
    progress_by_unit = {
        p.unit_id: p
        for p in UnitProgress.objects.filter(user=request.user)
    }

    units_with_progress = []
    completed_count = 0
    best_accuracy = 0.0
    for u in units:
        p = progress_by_unit.get(u.id)
        if p and p.is_completed:
            completed_count += 1
        if p and p.accuracy and p.accuracy > best_accuracy:
            best_accuracy = p.accuracy
        flashcards = list(u.flashcards.all())
        accuracy = (p.accuracy if p else 0.0) or 0.0
        xp_earned = int(round(XP_PER_UNIT * (accuracy / 100)))
        units_with_progress.append({
            'unit': u,
            'progress': p,
            'preview_words': [f.word for f in flashcards[:4]],
            'extra_words': max(0, len(flashcards) - 4),
            'total_words': len(flashcards),
            'xp_earned': xp_earned,
        })

    profile = _get_or_create_profile(request.user)
    total_units = len(units)
    completion_pct = int((completed_count / total_units) * 100) if total_units else 0

    return render(request, 'vocab/quiz_hub.html', {
        'units_with_progress': units_with_progress,
        'profile': profile,
        'completed_count': completed_count,
        'total_units': total_units,
        'completion_pct': completion_pct,
        'best_accuracy': best_accuracy,
    })


@login_required(login_url='login')
def unit_detail(request, unit_slug):
    unit = get_object_or_404(Unit, slug=unit_slug)
    progress = UnitProgress.objects.filter(user=request.user, unit=unit).first()
    return render(request, 'vocab/unit_detail.html', {'unit': unit, 'progress': progress})


@login_required(login_url='login')
def flashcards_view(request, unit_slug):
    unit = get_object_or_404(Unit, slug=unit_slug)
    cards = unit.flashcards.all()
    return render(request, 'vocab/flashcards.html', {'unit': unit, 'cards': cards})


@login_required(login_url='login')
def quiz_detail(request, unit_slug):
    unit = get_object_or_404(Unit, slug=unit_slug)
    cards = list(unit.flashcards.all())

    if request.method == 'POST':
        if len(cards) < 3:
            return HttpResponseBadRequest("Not enough cards for a quiz.")

        # Rate-limit: one submission per QUIZ_COOLDOWN_SECONDS per unit
        cooldown_key = f'quiz_last_{unit.id}'
        last_ts = request.session.get(cooldown_key, 0)
        now_ts = time.time()
        if now_ts - last_ts < QUIZ_COOLDOWN_SECONDS:
            return HttpResponseBadRequest("Please wait before resubmitting.")
        request.session[cooldown_key] = now_ts

        try:
            payload = json.loads(request.POST.get('answers') or '')
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Malformed quiz submission.")

        accuracy, mc_correct, mc_total, match_correct, match_total = grade_quiz(cards, payload)
        if accuracy is None:
            return HttpResponseBadRequest("Empty quiz submission.")

        is_completed_now = accuracy >= MASTERY_THRESHOLD

        progress, _ = UnitProgress.objects.get_or_create(user=request.user, unit=unit)
        previous_best = progress.accuracy or 0.0
        was_completed = progress.is_completed

        earned_xp = 0
        if accuracy > previous_best:
            earned_xp = int(round(XP_PER_UNIT * ((accuracy - previous_best) / 100)))
            progress.accuracy = accuracy

        if is_completed_now and not was_completed:
            progress.is_completed = True

        progress.save()

        profile = _get_or_create_profile(request.user)
        if earned_xp:
            profile.total_score += earned_xp
        if is_completed_now and not was_completed:
            profile.words_mastered += len(cards)
        profile.save()

        # Update SR state: correct cards get quality=4, incorrect get quality=1
        mc_correct_ids = {
            ans['question_id'] for ans in (payload.get('mc') or [])
            if ans.get('question_id') in {c.id for c in cards}
            and ans.get('question_id') == ans.get('selected_id')
        }
        match_correct_ids = {
            m['word_id'] for m in (payload.get('matches') or [])
            if m.get('word_id') in {c.id for c in cards}
            and m.get('word_id') == m.get('def_id')
        }
        correct_ids = mc_correct_ids | match_correct_ids
        for card in cards:
            review, _ = FlashcardReview.objects.get_or_create(
                user=request.user, flashcard=card,
                defaults={'next_review': timezone.now().date()},
            )
            review.record(4 if card.id in correct_ids else 1)

        return render(request, 'vocab/quiz_result.html', {
            'unit': unit,
            'accuracy': accuracy,
            'is_completed': progress.is_completed,
            'just_completed': is_completed_now and not was_completed,
            'xp_gained': earned_xp,
            'best_accuracy': progress.accuracy,
        })

    return render(request, 'vocab/quiz.html', {'unit': unit, 'cards': cards})


@login_required(login_url='login')
def daily_review(request):
    """Show cards due today for spaced-repetition review."""
    today = timezone.now().date()
    due_reviews = (
        FlashcardReview.objects
        .filter(user=request.user, next_review__lte=today)
        .select_related('flashcard', 'flashcard__unit')
        .order_by('next_review', 'id')
    )

    if request.method == 'POST':
        review_id = request.POST.get('review_id')
        quality = request.POST.get('quality')
        try:
            review = FlashcardReview.objects.get(id=review_id, user=request.user)
            review.record(int(quality))
        except (FlashcardReview.DoesNotExist, ValueError, TypeError):
            pass
        return redirect('daily_review')

    cards_data = [
        {
            'id': r.flashcard.id,
            'review_id': r.id,
            'word': r.flashcard.word,
            'ipa': r.flashcard.ipa,
            'pos': r.flashcard.part_of_speech,
            'definition': r.flashcard.definition,
            'example': r.flashcard.example,
        }
        for r in due_reviews
    ]
    return render(request, 'vocab/daily_review.html', {
        'cards_json': json.dumps(cards_data),
        'due_count': len(cards_data),
    })


@login_required(login_url='login')
def ranking_view(request):
    all_profiles = Profile.objects.order_by('-total_score').select_related('user')
    paginator = Paginator(all_profiles, LEADERBOARD_PAGE_SIZE)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    points_to_top_3 = None
    top_profiles = list(all_profiles[:3])
    if len(top_profiles) >= 3:
        top_3_score = top_profiles[2].total_score
        try:
            user_profile = Profile.objects.get(user=request.user)
            if user_profile.total_score < top_3_score:
                points_to_top_3 = top_3_score - user_profile.total_score + 1
        except Profile.DoesNotExist:
            pass

    return render(request, 'vocab/ranking.html', {
        'page_obj': page_obj,
        'profiles': page_obj.object_list,
        'points_to_top_3': points_to_top_3,
    })
