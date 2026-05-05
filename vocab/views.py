# Create your views here.

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from .models import Flashcard, Unit, Profile, UnitProgress

def register(request):
    if request.method == 'POST':
        user = User.objects.create_user(request.POST['username'], password=request.POST['password'])
        Profile.objects.create(user=user)
        login(request, user)
        return redirect('unit_hub')
    return render(request, 'vocab/register.html')

def login_user(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user:
            login(request, user)
            return redirect('unit_hub')
        return render(request, 'vocab/login.html', {'error': 'Invalid credentials'})
    return render(request, 'vocab/login.html')

def logout_user(request):
    logout(request)
    return redirect('home')

def home(request):
    return render(request, 'vocab/index.html')

@login_required(login_url='login')
def unit_hub(request):
    units = Unit.objects.all()
    # In a real app we would pass progress per user too
    return render(request, 'vocab/quiz_hub.html', {'units': units})

@login_required(login_url='login')
def unit_detail(request, unit_slug):
    unit = get_object_or_404(Unit, slug=unit_slug)
    # Check completeness if user is logged in
    progress = None
    if request.user.is_authenticated:
        progress, _ = UnitProgress.objects.get_or_create(user=request.user, unit=unit)
    return render(request, 'vocab/unit_detail.html', {'unit': unit, 'progress': progress})

@login_required(login_url='login')
def flashcards_view(request, unit_slug):
    unit = get_object_or_404(Unit, slug=unit_slug)
    cards = unit.flashcards.all()
    return render(request, 'vocab/flashcards.html', {'unit': unit, 'cards': cards})

@login_required(login_url='login')
def quiz_detail(request, unit_slug):
    unit = get_object_or_404(Unit, slug=unit_slug)
    cards = unit.flashcards.all()
    # Logic to process a submitted quiz
    if request.method == 'POST':
        if request.user.is_authenticated:
            # We assume JS fetches accuracy and sends it, or calculate from POST data
            accuracy = float(request.POST.get('accuracy', 0))
            is_completed = accuracy >= 80.0
            
            # Update points: 30xp max * (accuracy / 100)
            earned_xp = int(30 * (accuracy / 100))
            
            profile, _ = Profile.objects.get_or_create(user=request.user)
            profile.total_score += earned_xp
            profile.save()

            progress, _ = UnitProgress.objects.get_or_create(user=request.user, unit=unit)
            progress.is_completed = is_completed
            progress.accuracy = accuracy
            progress.save()

            return render(request, 'vocab/quiz_result.html', {
                'unit': unit, 
                'accuracy': accuracy, 
                'is_completed': is_completed, 
                'xp_gained': earned_xp
            })
    return render(request, 'vocab/quiz.html', {'unit': unit, 'cards': cards})

@login_required(login_url='login')
def ranking_view(request):
    profiles = list(Profile.objects.order_by('-total_score')[:10])
    
    # Calculate points needed to reach top 3
    points_to_top_3 = None
    if profiles and len(profiles) >= 3:
        top_3_score = profiles[2].total_score
    elif profiles:
        top_3_score = profiles[-1].total_score
    else:
        top_3_score = 0

    user_profile = None
    if request.user.is_authenticated:
        try:
            user_profile = Profile.objects.get(user=request.user)
            if user_profile.total_score < top_3_score:
                points_to_top_3 = top_3_score - user_profile.total_score + 1
        except Profile.DoesNotExist:
            pass

    return render(request, 'vocab/ranking.html', {
        'profiles': profiles,
        'points_to_top_3': points_to_top_3
    })