from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import Message, ChatSession

@shared_task
def forward_to_doctor(session_id: int, message_id: int) -> None:
    """Forward a user's message to their assigned doctor when the doctor comes online."""
    try:
        message = Message.objects.get(id=message_id, session_id=session_id)
        subject = f"New message from {message.session.user.username}"
        send_mail(
            subject,
            message.content,
            settings.DEFAULT_FROM_EMAIL,
            [settings.DOCTOR_EMAIL],
            fail_silently=False,
        )
    except Message.DoesNotExist:
        pass
