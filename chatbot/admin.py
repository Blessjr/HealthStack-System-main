from django.contrib import admin
from .models import ChatSession, ChatMessage

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'started_at', 'ended_at')
    search_fields = ('user__username',)

@admin.register(ChatMessage)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'sender', 'timestamp')
    list_filter = ('sender',)
    search_fields = ('content',)
