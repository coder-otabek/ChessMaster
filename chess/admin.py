from django.contrib import admin
from .models import Game, MatchmakingQueue

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ['id','white_player','black_player','status','time_control','created_at']
    list_filter  = ['status','time_control']
    search_fields = ['white_player__username','black_player__username']
    ordering = ['-created_at']

@admin.register(MatchmakingQueue)
class QueueAdmin(admin.ModelAdmin):
    list_display = ['user','time_control','rating','joined_at']
