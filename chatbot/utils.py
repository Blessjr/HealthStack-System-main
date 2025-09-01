import os
import pandas as pd
from difflib import get_close_matches
from django.conf import settings
from django.utils import timezone

# Import from chatbot models, not doctor models
from chatbot.models import Conversation, ChatMessage

# Load CSV
def load_dataset():
    csv_path = os.path.join(settings.BASE_DIR, 'chatbot', 'data', 'bilingual_medical_chatbot_12000.csv')
    try:
        df = pd.read_csv(csv_path)
        # Clean the data
        df = df.dropna(subset=['question', 'answer'])
        df['question'] = df['question'].astype(str).str.strip()
        df['answer'] = df['answer'].astype(str).str.strip()
        print(f"✅ Successfully loaded CSV with {len(df)} rows")
        return df
    except FileNotFoundError:
        print(f"❌ CSV file not found at: {csv_path}")
        return None
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return None

# Search logic
def search_csv_response(user_input, language='en'):
    df = load_dataset()
    if df is None:
        return get_fallback_response(language)

    # Filter by language if possible
    if 'language' in df.columns:
        df_filtered = df[df['language'] == language]
        if len(df_filtered) == 0:
            df_filtered = df  # Fallback to all data if no language match
    else:
        df_filtered = df
    
    questions = df_filtered['question'].astype(str).str.lower().tolist()
    matches = get_close_matches(user_input.lower(), questions, n=3, cutoff=0.6)

    if matches:
        # Return the best match
        match = matches[0]
        answer_row = df_filtered[df_filtered['question'].str.lower() == match]
        if not answer_row.empty:
            answer = answer_row['answer'].values[0]
            return answer
    
    return get_fallback_response(language)

def get_fallback_response(language):
    if language == 'fr':
        return "😕 Je n'ai pas bien compris votre question médicale. Pouvez-vous la reformuler ou me poser une question sur un symptôme, un médicament, ou un problème de santé spécifique?"
    else:
        return "😕 I didn't quite understand your medical question. Could you rephrase it or ask me about a specific symptom, medication, or health concern?"

# When a message is sent
def save_message(user, sender, message, language='en'):
    """
    Save a message to the conversation system
    user: The user sending the message
    sender: 'patient', 'doctor', or 'bot'
    message: The message content
    language: 'en' or 'fr'
    """
    try:
        # Get or create conversation for this patient
        conversation, created = Conversation.objects.get_or_create(patient=user)
        
        # Save message
        chat_message = ChatMessage.objects.create(
            conversation=conversation,
            sender=sender,
            message=message,
            language=language,
            timestamp=timezone.now()
        )
        
        print(f"✅ Message saved: {sender} - {message[:50]}...")
        return chat_message
        
    except Exception as e:
        print(f"❌ Error saving message: {e}")
        return None

# Additional utility function to get conversation history
def get_conversation_history(user, limit=10):
    """
    Get the conversation history for a user
    """
    try:
        conversation = Conversation.objects.filter(patient=user).first()
        if conversation:
            messages = conversation.chat_messages.all().order_by('-timestamp')[:limit]
            return list(messages.values('sender', 'message', 'timestamp', 'language'))
        return []
    except Exception as e:
        print(f"❌ Error getting conversation history: {e}")
        return []

# Enhanced CSV search with context awareness
def search_csv_with_context(user_input, previous_messages=None, language='en'):
    """
    Enhanced search that considers conversation context
    """
    # First try direct search
    response = search_csv_response(user_input, language)
    
    # If no direct match, try to understand context from previous messages
    if response.startswith("😕") and previous_messages:
        # Analyze previous messages for context
        last_few_messages = [msg['message'] for msg in previous_messages[-3:] if msg['sender'] == 'patient']
        
        if last_few_messages:
            # Create a context-aware query
            context_query = " ".join(last_few_messages + [user_input])
            context_response = search_csv_response(context_query, language)
            
            if not context_response.startswith("😕"):
                return context_response
    
    return response