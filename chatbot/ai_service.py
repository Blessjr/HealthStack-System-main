from openai import OpenAI
import json
from django.http import JsonResponse

# Initialize OpenAI client with OpenRouter
client = OpenAI(
    base_url="https://api.deepseek.com",
    api_key="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"
)

def get_ai_response(message, language='en'):
    try:
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "http://localhost:8000",  # Update with your site URL
                "X-Title": "MediAI Chatbot",             # Update with your site name
            },
            model="deepseek-chat",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful medical assistant. Respond concisely and professionally."
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"AI service error: {e}")
        return None  # Will trigger fallback