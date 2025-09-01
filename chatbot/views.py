from datetime import timezone
import os
import json
import time
import pandas as pd
from difflib import get_close_matches
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from langdetect import detect, LangDetectException
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.shortcuts import render
from gtts import gTTS
from io import BytesIO

# Use your actual models
from .models import ChatSession, ChatMessage, Conversation
# Doctor presence
from doctor.models import Doctor_Information as Doctor

# Optional: only needed for translation helper below
import google.generativeai as genai
if getattr(settings, "GEMINI_API_KEY", None):
    genai.configure(api_key=settings.GEMINI_API_KEY)

# Use your ai_service for AI replies
from .ai_service import get_ai_response

# ========================
# 📄 Class-based Chat View
# ========================
class ChatView(TemplateView):
    template_name = 'chatbot/chat.html'

# ========================
# 📁 CSV Utility Functions
# ========================
def load_qa_pairs():
    csv_path = os.path.join(settings.BASE_DIR, 'chatbot', 'chat_data.csv')
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print("⚠️ CSV file not found at:", csv_path)
        return []

    df = df.sort_values(by=['conversation_id', 'timestamp'])
    qa_pairs = []

    for i in range(len(df) - 1):
        current = df.iloc[i]
        next_msg = df.iloc[i + 1]
        if str(current.get('sender', '')).lower() == 'user' and str(next_msg.get('sender', '')).lower() in ['bot', 'assistant']:
            question = str(current.get('message', '')).strip()
            answer = str(next_msg.get('message', '')).strip()
            if question and answer:
                qa_pairs.append((question, answer))

    return qa_pairs

def search_csv_response(user_input):
    qa_pairs = load_qa_pairs()
    if not qa_pairs:
        return "⚠️ Data file not found or no valid Q&A pairs. Please contact a doctor."

    questions = [q.lower() for q, _ in qa_pairs]
    matches = get_close_matches(user_input.lower(), questions, n=1, cutoff=0.5)

    if matches:
        matched_q = matches[0]
        for q, a in qa_pairs:
            if q.lower() == matched_q:
                return a

    return "😕 Sorry, I couldn't understand that. Try rephrasing or ask something else."

# ========================
# 🌍 Translate text using Gemini (helper)
# ========================
def translate_text(text, target_language):
    """
    Best-effort translation helper. Uses Gemini if configured.
    """
    if not getattr(settings, "AIzaSyBrY97CUIpihBwnNGn-GGlCx0XPw-nZIVQ", None):
        return text  # No key -> skip translation
    try:
        target = 'French' if target_language == 'fr' else 'English'
        prompt = f"Translate this to {target}:\n{text}"
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return (response.text or text).strip()
    except Exception as e:
        print("❌ Translation error:", e)
        return text

# ========================
# 🧠 Chatbot Decision Logic
# ========================
def get_or_create_active_session(user):
    """
    Returns an open ChatSession for the user or creates a new one.
    Also ensures a Conversation exists.
    """
    if not user.is_authenticated:
        return None, None
    
    # Get or create conversation
    conversation, created = Conversation.objects.get_or_create(patient=user)
    
    # Get or create chat session
    existing = ChatSession.objects.filter(user=user, ended_at__isnull=True).order_by('-started_at').first()
    if existing:
        return existing, conversation
    
    session = ChatSession.objects.create(user=user)
    return session, conversation

def get_response_from_doctor_or_ai(request, user_input, language, session, conversation):
    """
    Save user's message, check for online doctor; if not present, ask Gemini via ai_service.
    Always writes to Message with senders: user / bot / doctor.
    """
    # Persist incoming user message
    ChatMessage.objects.create(conversation=conversation, sender="user", message=user_input, language=language)

    # Check for online doctor to handoff
    online_doctor = Doctor.objects.filter(is_online=True).first()
    if online_doctor:
        forward_msg = f"Forwarding to Doctor {online_doctor.user.get_full_name()}... Please wait."
        # Save bot notice
        bot_notice = ChatMessage.objects.create(conversation=conversation, sender="bot", message=forward_msg, language=language)

        # Notify connected WebSocket clients (patient & doctor rooms)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chat_{session.id}',
            {'type': 'chat_message', 'message': forward_msg, 'sender': 'bot'}
        )
        async_to_sync(channel_layer.group_send)(
            f'doctor_{session.id}',
            {'type': 'chat_message', 'message': user_input, 'sender': 'user'}
        )
        # Mark user message as forwarded
        try:
            last_user_msg = ChatMessage.objects.filter(conversation=conversation, sender='user').order_by('-timestamp').first()
            if last_user_msg:
                last_user_msg.forwarded_to_doctor = True
                last_user_msg.save(update_fields=['forwarded_to_doctor'])
        except Exception:
            pass

        # Also forward notice to doctor
        try:
            bot_notice.forwarded_to_doctor = True
            bot_notice.save(update_fields=['forwarded_to_doctor'])
            async_to_sync(channel_layer.group_send)(
                f'doctor_{session.id}',
                {'type': 'chat_message', 'message': forward_msg, 'sender': 'bot'}
            )
        except Exception:
            pass

        return forward_msg

    # No doctor online -> query Gemini via ai_service
    try:
        reply = get_ai_response(user_input, language=language) or ""
        reply = reply.strip() or "Sorry, I couldn't generate a response."
    except Exception as e:
        print("❌ ai_service error:", e)
        reply = None

    if not reply:
        # Fallback to CSV
        reply = search_csv_response(user_input)

    # Save bot reply
    ChatMessage.objects.create(conversation=conversation, sender="bot", message=reply, language=language)

    # Broadcast to WebSocket patient room
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{session.id}',
        {'type': 'chat_message', 'message': reply, 'sender': 'bot'}
    )

    # Also inform doctor room (if any listener)
    async_to_sync(channel_layer.group_send)(
        f'doctor_{session.id}',
        {'type': 'chat_message', 'message': reply, 'sender': 'bot'}
    )

    return reply

# ========================
# 🌐 AJAX Chat API Endpoint
# ========================
@csrf_exempt
def chat_api(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid request method."}, status=405)

    try:
        data = json.loads(request.body or "{}")
        user_message = str(data.get("message", "")).strip()
        if not user_message:
            return JsonResponse({"error": "No message provided."}, status=400)

        user = request.user if request.user.is_authenticated else None
        if not user:
            return JsonResponse({"error": "Authentication required."}, status=401)

        # Get language preference
        language = request.headers.get('X-Language', 'en')
        if language not in ['en', 'fr']:
            language = 'en'

        # Get or create active session and conversation
        session, conversation = get_or_create_active_session(user)
        
        # Save user message
        ChatMessage.objects.create(conversation=conversation, sender="user", message=user_message, language=language)

        # Try AI response first
        ai_response = get_ai_response(user_message, language)
        
        if ai_response:
            # Save and return AI response
            ChatMessage.objects.create(conversation=conversation, sender="bot", message=ai_response, language=language)
            return JsonResponse({
                "message": ai_response,
                "language": language,
                "session_id": session.id
            })
        else:
            # Fallback to CSV
            csv_response = search_csv_response(user_message)
            ChatMessage.objects.create(conversation=conversation, sender="bot", message=csv_response, language=language)
            return JsonResponse({
                "message": csv_response,
                "language": language,
                "session_id": session.id
            })

    except Exception as e:
        print("❌ Chat API Error:", e)
        # Final fallback
        error_msg = "Désolé, problème technique. Veuillez réessayer." if language == 'fr' else "Sorry, technical issue. Please try again."
        return JsonResponse({"message": error_msg, "language": language}, status=200)

# ========================
# 🔊 Text-to-Speech API Endpoint
# ========================
@csrf_exempt
def tts_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body or "{}")
            text = str(data.get("text", "")).strip()
            lang = str(data.get("language", "en"))
            if not text:
                return JsonResponse({"error": "No text provided."}, status=400)

            tts = gTTS(text=text, lang=lang)
            mp3_fp = BytesIO()
            tts.write_to_fp(mp3_fp)
            mp3_fp.seek(0)

            return HttpResponse(mp3_fp.read(), content_type="audio/mpeg")
        except Exception as e:
            print("❌ TTS API error:", e)
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method."}, status=405)

# ========================
# 🖥️ View to render chatbot page
# ========================
def chatbot_view(request):
    session, conversation = get_or_create_active_session(request.user) if request.user.is_authenticated else (None, None)
    return render(request, 'chatbot/chat.html', {
        'session': session,
        'timestamp': int(time.time())
    })
    
@csrf_exempt
def csv_fallback_api(request):
    if request.method == 'POST':
        data = json.loads(request.body or "{}")
        user_message = data.get("message", "")
        language = request.headers.get('X-Language', 'en')
        
        response = search_csv_response(user_message)
        return JsonResponse({"message": response})
    
    return JsonResponse({"error": "Invalid method"}, status=405)