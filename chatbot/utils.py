import os
import pandas as pd
from difflib import get_close_matches
from django.conf import settings

# Load CSV
def load_dataset():
    csv_path = os.path.join(settings.BASE_DIR, 'chatbot', 'data', 'bilingual_medical_chatbot_12000.csv')
    try:
        df = pd.read_csv(csv_path)
        return df
    except FileNotFoundError:
        return None

# Search logic
def search_csv_response(user_input):
    df = load_dataset()
    if df is None:
        return "⚠️ Data file not found. Please contact a doctor."

    # Lowercase for matching
    questions = df['question'].astype(str).str.lower().tolist()
    matches = get_close_matches(user_input.lower(), questions, n=1, cutoff=0.5)

    if matches:
        match = matches[0]
        answer = df[df['question'].str.lower() == match]['answer'].values
        return answer[0] if len(answer) else "⚠️ Answer not found."
    return "😕 Sorry, I couldn't understand that. Try rephrasing or ask something else."

# When a message is sent
from doctor.models import Conversation, ChatMessage
from django.utils import timezone

def save_message(user, sender, message, language='en'):
    # Get or create conversation
    conversation, created = Conversation.objects.get_or_create(patient=user)
    
    # Save message
    ChatMessage.objects.create(
        conversation=conversation,
        sender=sender,
        message=message,
        language=language,
        timestamp=timezone.now()
    )