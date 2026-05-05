import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.http import HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Flashcard, Unit, Profile, UnitProgress


def _get_or_create_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def register(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        if not username or not password:
            return render(request, 'vocab/register.html',
                          {'error': 'Username and password are required.'})
        try:
            user = User.objects.create_user(username=username, password=password)
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
        return render(request, 'vocab/login.html', {'error': 'Invalid credentials'})
    return render(request, 'vocab/login.html')


@require_POST
def logout_user(request):
    logout(request)
    return redirect('home')


def home(request):
    return render(request, 'vocab/index.html')


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
        xp_earned = int(round(30 * (accuracy / 100)))
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

        try:
            payload = json.loads(request.POST.get('answers') or '')
        except json.JSONDecodeError:
            return HttpResponseBadRequest("Malformed quiz submission.")

        mc_answers = payload.get('mc', []) if isinstance(payload, dict) else []
        match_attempts = payload.get('matches', []) if isinstance(payload, dict) else []

        valid_ids = {c.id for c in cards}

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

        total_questions = mc_total + match_total
        if total_questions == 0:
            return HttpResponseBadRequest("Empty quiz submission.")

        accuracy = round(((mc_correct + match_correct) / total_questions) * 100, 2)
        is_completed_now = accuracy >= 80.0

        progress, _ = UnitProgress.objects.get_or_create(user=request.user, unit=unit)
        previous_best = progress.accuracy or 0.0
        was_completed = progress.is_completed

        # Award XP only on improvement, scaled to the delta. Prevents replay farming.
        earned_xp = 0
        if accuracy > previous_best:
            earned_xp = int(round(30 * ((accuracy - previous_best) / 100)))
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
def ranking_view(request):
    profiles = list(Profile.objects.order_by('-total_score')[:10])

    points_to_top_3 = None
    if len(profiles) >= 3:
        top_3_score = profiles[2].total_score
        try:
            user_profile = Profile.objects.get(user=request.user)
            if user_profile.total_score < top_3_score:
                points_to_top_3 = top_3_score - user_profile.total_score + 1
        except Profile.DoesNotExist:
            pass

    return render(request, 'vocab/ranking.html', {
        'profiles': profiles,
        'points_to_top_3': points_to_top_3,
    })
