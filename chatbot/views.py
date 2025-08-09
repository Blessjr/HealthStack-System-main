import os
import json
import time
import openai
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

from chatbot.models import ChatMessage, Conversation
from doctor.models import Doctor_Information as Doctor

# ========================
# 📄 Class-based Chat View
# ========================
class ChatView(TemplateView):
    template_name = 'chatbot/chat.html'

# ========================
# 🔐 OpenAI API Key
# ========================


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
        if current['sender'].lower() == 'user' and next_msg['sender'].lower() in ['bot', 'assistant']:
            question = str(current['message']).strip()
            answer = str(next_msg['message']).strip()
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
# 🌍 Translate text using OpenAI
# ========================
def translate_text(text, target_language):
    prompt = f"Translate this to {'French' if target_language == 'fr' else 'English'}:\n{text}"
    try:
        response = openai.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a translation assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ Translation error:", e)
        return text

# ========================
# 🧠 Chatbot Decision Logic
# ========================
def get_response_from_doctor_or_ai(request, user_input, language, conversation=None):
    """
    Save the user message and respond either by forwarding to an online doctor or
    generating AI response (OpenAI API), with fallback to CSV search.

    If conversation is None, message is saved without conversation context.
    """

    # Save user's message (with conversation if provided)
    if conversation:
        ChatMessage.objects.create(
            conversation=conversation,
            sender="user",
            message=user_input,
            language=language
        )
    else:
        ChatMessage.objects.create(
            sender="user",
            message=user_input,
            language=language
        )

    # Check for online doctor
    online_doctor = Doctor.objects.filter(is_online=True).first()
    if online_doctor:
        forward_msg = f"Forwarding to Doctor {online_doctor.user.get_full_name()}... Please wait."

        # Save assistant message about forwarding
        if conversation:
            ChatMessage.objects.create(
                conversation=conversation,
                sender="assistant",
                message=forward_msg,
                language=language,
                handled_by=online_doctor.user  # assuming you have this field
            )
        else:
            ChatMessage.objects.create(
                sender="assistant",
                message=forward_msg,
                language=language,
                handled_by=online_doctor.user
            )

        # Notify WebSocket group if conversation available
        if conversation:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'chat_{conversation.id}',
                {
                    'type': 'chat_message',
                    'message': forward_msg,
                    'sender': 'assistant',
                }
            )
        return forward_msg
        return forward_msg

    # Prepare system prompt based on language
    system_prompt = (
        "Tu es un assistant médical virtuel. Réponds toujours en français."
        if language == "fr"
        else "You are a virtual medical assistant. Always reply in English."
    )

    messages = request.session.get("chat_history", [])
    if not any(m["role"] == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": user_input})

    try:
        response = openai.chat.completions.create(
            model="deepseek-chat",
            messages=messages
        )
        reply = response.choices[0].message.content.strip()
        messages.append({"role": "assistant", "content": reply})
        request.session["chat_history"] = messages

        # Save assistant's response
        if conversation:
            ChatMessage.objects.create(
                conversation=conversation,
                sender="assistant",
                message=reply,
                language=language
            )
        else:
            ChatMessage.objects.create(
                sender="assistant",
                message=reply,
                language=language
            )

        # Notify WebSocket group if conversation available
        if conversation:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'chat_{conversation.id}',
                {
                    'type': 'chat_message',
                    'message': reply,
                    'sender': 'assistant',
                }
            )

        return reply

    except Exception as e:
        print("❌ OpenAI error:", e)
        fallback_reply = search_csv_response(user_input)

        # Save fallback response
        if conversation:
            ChatMessage.objects.create(
                conversation=conversation,
                sender="assistant",
                message=fallback_reply,
                language=language
            )
        else:
            ChatMessage.objects.create(
                sender="assistant",
                message=fallback_reply,
                language=language
            )
        return fallback_reply

# ========================
# 🌐 AJAX Chat API Endpoint
# ========================
@csrf_exempt
def chat_api(request):
    if not settings.OPENROUTER_API_KEY:
        return JsonResponse({
            "error": "OpenRouter API key not configured",
            "message": "Service temporarily unavailable"
        }, status=503)
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid request method."}, status=405)

    try:
        data = json.loads(request.body)
        user_message = data.get("message", "").strip()
        if not user_message:
            return JsonResponse({"error": "No message provided."}, status=400)

        # Check user authentication
        user = request.user if request.user.is_authenticated else None
        if not user:
            return JsonResponse({"error": "Authentication required."}, status=401)

        # Handle chat reset commands
        if user_message.lower() in ["new chat", "restart", "reset"]:
            request.session["chat_history"] = []
            request.session["chat_language"] = None
            return JsonResponse({"message": "🤖\n👋 New chat started.", "language": "en"})

        # Get or create conversation for the authenticated user
        conversation, created = Conversation.objects.get_or_create(patient=user)

        # Language detection or header override
        language = request.headers.get('X-Language')
        if not language:
            try:
                language = detect(user_message)
            except LangDetectException:
                language = "en"

        # Manage session language state
        session_language = request.session.get("chat_language")
        if not session_language:
            session_language = language
            request.session["chat_language"] = session_language

        # First try OpenRouter AI
        try:
            client = openai.OpenAI(
                base_url="https://api.deepseek.com",
                api_key=settings.OPENROUTER_API_KEY
            )

            response = client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "MediAI Chatbot",
                },
                model="deepseek-chat",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful medical assistant. Respond concisely and professionally."
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            )
            ai_response = response.choices[0].message.content
            
            # Save the successful AI response
            ChatMessage.objects.create(
                conversation=conversation,
                sender="assistant",
                message=ai_response,
                language=session_language
            )
            
            response_message = ai_response
            
        except Exception as ai_error:
            print(f"AI service error: {ai_error}")
            # Fallback to original doctor/AI/dataset logic
            response_message = get_response_from_doctor_or_ai(request, user_message, session_language, conversation)

        # If detected language differs from session language, translate
        if language != session_language:
            translated_response = translate_text(response_message, language)
            request.session["chat_language"] = language
            return JsonResponse({
                "message": translated_response,
                "language": language,
                "conversation_id": conversation.id
            })

        return JsonResponse({
            "message": response_message,
            "language": session_language,
            "conversation_id": conversation.id
        })

    except Exception as e:
        print("❌ Chat API Error:", e)
        return JsonResponse({"error": str(e)}, status=500)

# ========================
# 🔊 Text-to-Speech API Endpoint
# ========================
@csrf_exempt
def tts_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            text = data.get("text", "").strip()
            lang = data.get("language", "en")

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
# 💬 Optional Form POST View
# ========================
@csrf_exempt
def chatbot_response_view(request):
    if request.method == 'POST':
        user_input = request.POST.get("message", "").strip()
        try:
            language = request.headers.get('X-Language')
            if not language:
                try:
                    language = detect(user_input)
                except LangDetectException:
                    language = "en"

            response = get_response_from_doctor_or_ai(request, user_input, language)
            return JsonResponse({"response": response})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method."}, status=405)

# ========================
# 🧾 Helper: Get or create conversation for user
# ========================
def get_or_create_conversation_for_user(user):
    if not user.is_authenticated:
        return None
    conversation, created = Conversation.objects.get_or_create(patient=user)
    return conversation

# ========================
# 🖥️ View to render chatbot page
# ========================
def chatbot_view(request):
    conversation = get_or_create_conversation_for_user(request.user)
    return render(request, 'chatbot/chat.html', {
        'conversation': conversation,
        'timestamp': int(time.time())
    })
