from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class ChatSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    doctor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='doctor_sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Session {self.id} for {self.user}"
    
class Conversation(models.Model):
    # FIXED: Use patient field instead of participants for the save_message function
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_conversations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chatbot_conversation'  # Add this line
        # Ensure one conversation per patient
        unique_together = ['patient']

    def __str__(self):
        return f"Conversation {self.id} for {self.patient.username}"

class ChatMessage(models.Model):
    SENDER_CHOICES = [
        ('patient', 'Patient'),
        ('doctor', 'Doctor'),
        ('bot', 'Bot'),
    ]
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('fr', 'French')
    ]
    
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    message = models.TextField()
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en')
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    # Add this new field:
    forwarded_to_doctor = models.BooleanField(default=False)  # New field added here

    class Meta:
        db_table = 'chatbot_chatmessage'
        ordering = ('timestamp',)

    def __str__(self):
        return f"{self.sender}: {self.message[:30]}"