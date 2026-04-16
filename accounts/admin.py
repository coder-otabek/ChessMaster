from django.contrib import admin
from .models import Profile, PasswordResetOTP

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'rating', 'wins', 'losses', 'draws', 'games_played', 'is_online']
    list_filter  = ['is_online']
    search_fields = ['user__username', 'user__email']
    ordering = ['-rating']

@admin.register(PasswordResetOTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ['user', 'email', 'otp', 'created_at', 'is_used']
    list_filter  = ['is_used']
