from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Conversation(models.Model):
    patient = models.ForeignKey(User, related_name='conversations', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Conversation {self.id} with {self.patient}"

class ChatSession(models.Model):
    # Optional: keep both Conversation and ChatSession, or merge into one model if needed
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Session {self.id} for {self.user}"

class ChatMessage(models.Model):
    # You can use either conversation or session depending on your flow
    conversation = models.ForeignKey(Conversation, related_name='messages', null=True, blank=True, on_delete=models.CASCADE)
    session = models.ForeignKey(ChatSession, related_name='messages', null=True, blank=True, on_delete=models.CASCADE)
    
    sender = models.CharField(
        max_length=50,
        choices=[('user', 'User'), ('bot', 'Bot'), ('doctor', 'Doctor'), ('assistant', 'Assistant')]
    )
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    language = models.CharField(max_length=10, default='en')
    handled_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='handled_messages'
    )

    class Meta:
        ordering = ('timestamp',)

    def __str__(self):
        snippet = self.message[:30]
        return f"{self.sender}: {snippet}"
