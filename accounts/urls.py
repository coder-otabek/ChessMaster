from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('register/',        views.register_view,        name='register'),
    path('register/verify/', views.register_verify_view,  name='register_verify'),
    path('register/resend/', views.register_resend_view,  name='register_resend'),
    path('login/',    views.login_view,    name='login'),
    path('logout/',   views.logout_view,   name='logout'),

    # Password reset
    path('password-reset/',         views.password_reset_request, name='password_reset'),
    path('password-reset/verify/',  views.password_reset_verify,  name='password_reset_verify'),
    path('password-reset/resend/',  views.password_reset_resend,  name='password_reset_resend'),
    path('password-reset/confirm/', views.password_reset_confirm, name='password_reset_confirm'),
    path('password-change/',        views.password_change_view,   name='password_change'),

    # Profile
    path('profile/<str:username>/', views.profile_view,      name='profile'),
    path('profile/edit/me/',        views.profile_edit_view,  name='profile_edit'),
    path('history/',                views.game_history_view,  name='game_history'),

    # Admin
    path('admin-panel/',                         views.admin_dashboard,             name='admin_dashboard'),
    path('admin-panel/players/',                 views.admin_players,               name='admin_players'),
    path('admin-panel/players/<int:user_id>/edit/',   views.admin_edit_player,      name='admin_edit_player'),
    path('admin-panel/players/<int:user_id>/reset-pw/', views.admin_reset_player_password, name='admin_reset_player_password'),
    path('admin-panel/players/<int:user_id>/toggle/',   views.admin_toggle_active,  name='admin_toggle_active'),
    path('admin-panel/games/',                   views.admin_games,                 name='admin_games'),
    path('admin-panel/games/create/',            views.admin_create_game,           name='admin_create_game'),
    path('admin-panel/games/live/',              views.admin_live_games,            name='admin_live_games'),
    path('admin-panel/games/<int:game_id>/force-end/', views.admin_force_end_game,  name='admin_force_end_game'),
    path('admin-panel/games/<int:game_id>/watch/', views.admin_watch_game,          name='admin_watch_game'),
    path('admin-panel/ratings/',                 views.admin_ratings_page,          name='admin_ratings'),
    path('admin-panel/ratings/excel/',           views.admin_export_excel,          name='admin_export_excel'),
    path('admin-panel/ratings/csv/',             views.admin_export_csv,            name='admin_export_csv'),

    # Superuser
    path('superuser/users/',                views.superuser_users,       name='superuser_users'),
    path('superuser/users/add/',            views.superuser_add_user,    name='superuser_add_user'),
    path('superuser/users/<int:user_id>/delete/', views.superuser_delete_user, name='superuser_delete_user'),
    path('superuser/settings/',             views.superuser_settings,    name='superuser_settings'),
    path('api/live-status/',                views.live_status,           name='live_status'),
]