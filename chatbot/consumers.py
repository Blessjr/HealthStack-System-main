import json
from channels.generic.websocket import AsyncWebsocketConsumer
from openai import OpenAI

from healthstack import settings
from .ai_service import get_ai_response

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        await super().disconnect(close_code)

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json.get('content', '')
            language = text_data_json.get('language', 'en')
        
            client = OpenAI(
                base_url="https://api.deepseek.com",
                api_key=settings.OPENROUTER_API_KEY
            )

            try:
                response = client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "http://localhost:8000",
                        "X-Title": "MediAI Chatbot",
                    },
                    model="deepseek-chat",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a medical assistant."
                        },
                        {
                            "role": "user",
                            "content": message
                        }
                    ]
                )
                ai_response = response.choices[0].message.content
            except Exception as e:
                print(f"AI error: {e}")
                ai_response = "I'm having technical difficulties. Please try again later."

            await self.send(text_data=json.dumps({
                'message': ai_response,
                'sender': 'bot'
            }))

        except Exception as e:
            await self.send(text_data=json.dumps({
                'error': str(e),
                'sender': 'system'
            }))