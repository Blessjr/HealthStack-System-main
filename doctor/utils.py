from django.db.models import Q
from .models import Patient, User, Hospital_Information
from doctor.models import Doctor_Information, Appointment, ChatMessage, Conversation
from hospital_admin.models import hospital_department, specialization, service

def searchPatients(request):
    """
    Searches for patients based on the 'search_query' GET parameter.
    Returns a queryset of matching patients and the search string.
    """
    search_query = request.GET.get('search_query', '')
    
    patients = Patient.objects.filter(
        Q(patient_id__icontains=search_query)
    )
    
    return patients, search_query


def forward_patient_bot_messages(conversation_id):
    """
    Retrieves all patient and bot messages in a conversation that haven't been forwarded
    to the doctor yet. Marks them as forwarded after processing.

    Returns:
        QuerySet of messages that were forwarded.
    """
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return []

    # Fetch all messages from patient and bot that are not forwarded
    messages_to_forward = ChatMessage.objects.filter(
        conversation=conversation,
        sender__in=['patient', 'bot'],
        is_forwarded=False
    ).order_by('timestamp')

    # TODO: send messages via WebSocket to the doctor
    # Example: iterate and send via channels layer if needed

    # Mark all messages as forwarded
    messages_to_forward.update(is_forwarded=True)

    return messages_to_forward
