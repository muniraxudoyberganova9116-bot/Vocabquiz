from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('learn/', views.unit_hub, name='unit_hub'),
    path('learn/<slug:unit_slug>/', views.unit_detail, name='unit_detail'),
    path('learn/<slug:unit_slug>/flashcards/', views.flashcards_view, name='flashcards'),
    path('learn/<slug:unit_slug>/quiz/', views.quiz_detail, name='quiz_detail'),
    path('ranking/', views.ranking_view, name='ranking'),
    path('review/', views.daily_review, name='daily_review'),
]