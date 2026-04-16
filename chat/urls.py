from django.urls import path
from . import views
urlpatterns = [
    path('chat/', views.chat_list, name='chat_list'),
    path('chat/unread-count/', views.unread_count, name='chat_unread_count'),
    path('chat/mark-read/<str:username>/', views.mark_read, name='chat_mark_read'),
    path('chat/<str:username>/', views.chat_with, name='chat_with'),
]