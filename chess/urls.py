from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    path('play/', views.find_opponent_view, name='find_opponent'),
    path('play/queue/join/',   views.queue_join,   name='queue_join'),
    path('play/queue/status/', views.queue_status, name='queue_status'),
    path('play/queue/leave/',  views.queue_leave,  name='queue_leave'),
    path('play/check-invite/', views.check_invite, name='check_invite'),
    path('play/check-active-game/', views.check_active_game, name='check_active_game'),
    path('play/online-players/',    views.online_players_api, name='online_players_api'),

    # O'yin
    path('chess/game/<int:game_id>/',              views.game_view,        name='chess_game'),
    path('chess/game/<int:game_id>/move/',         views.game_move,        name='game_move'),
    path('chess/game/<int:game_id>/legal-moves/',  views.game_legal_moves, name='game_legal_moves'),
    path('chess/game/<int:game_id>/resign/',       views.game_resign,      name='game_resign'),
    path('chess/game/<int:game_id>/draw/',         views.game_draw_offer,  name='game_draw_offer'),
    path('chess/game/<int:game_id>/abandon/',      views.game_abandon,     name='game_abandon'),

    # Chaqiruv — respond/cancel/status OLDIN, username KEYIN
    path('challenge/respond/<int:invite_id>/',     views.challenge_respond, name='challenge_respond'),
    path('challenge/cancel/<int:invite_id>/',      views.challenge_cancel,  name='challenge_cancel'),
    path('challenge/status/<int:invite_id>/',      views.challenge_status,  name='challenge_status'),
    path('challenge/<str:username>/',              views.challenge_player,  name='challenge_player'),
]