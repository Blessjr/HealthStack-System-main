# In chatbot/admin.py
from django.contrib import admin
from .models import ChatSession, Conversation, ChatMessage

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "doctor", "started_at", "ended_at", "is_active")
    list_filter = ("is_active", "started_at")
    search_fields = ("user__username", "doctor__username")

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "created_at")
    list_filter = ("created_at",)
    search_fields = ("patient__username",)

@admin.register(ChatMessage)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "get_conversation", "sender", "get_message_preview", "timestamp", "is_read", "forwarded_to_doctor", "language")
    list_filter = ("sender", "is_read", "forwarded_to_doctor", "language", "timestamp")
    search_fields = ("message", "conversation__patient__username")
    
    def get_conversation(self, obj):
        return f"Conv {obj.conversation.id} - {obj.conversation.patient.username}"
    get_conversation.short_description = 'Conversation'
    
    def get_message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    get_message_preview.short_description = 'Message'