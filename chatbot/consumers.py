import json, asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ObjectDoesNotExist
from .models import ChatSession, ChatMessage  # Changed from Message to ChatMessage
from .ai_service import get_ai_response
from .utils import search_csv_response
from django.conf import settings

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user', AnonymousUser())
        if user.is_anonymous:
            await self.close()
            return

        # Expect URL kwargs: .../ws/chat/<session_id>/<role>/
        self.role = self.scope['url_route']['kwargs'].get('role', 'user')
        session_id = self.scope['url_route']['kwargs'].get('session_id')

        if self.role == 'doctor':
            # Doctor must connect to an existing assigned session
            if not session_id:
                await self.close()
                return
            try:
                self.session = await asyncio.to_thread(ChatSession.objects.get, id=session_id)
            except ObjectDoesNotExist:
                await self.close()
                return

            # Security: only assigned doctor can join
            if not self.session.doctor_id or str(self.session.doctor_id) != str(user.id):
                await self.close()
                return

            self.room_group_name = f"doctor_{self.session.id}"
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()

            # Send any messages not yet forwarded
            messages = await asyncio.to_thread(
                lambda: list(self.session.messages.filter(forwarded_to_doctor=False).order_by('timestamp'))
            )
            for msg in messages:
                await self.send(text_data=json.dumps({
                    'sender': msg.sender,
                    'message': msg.message,  # Changed from msg.content to msg.message
                    'timestamp': msg.timestamp.strftime("%H:%M"),
                    'language': msg.language
                }))
                msg.forwarded_to_doctor = True
                await asyncio.to_thread(msg.save)

        else:
            # Patient connection: create a new session on first connect
            if session_id:
                try:
                    self.session = await asyncio.to_thread(ChatSession.objects.get, id=session_id)
                except ObjectDoesNotExist:
                    self.session = await asyncio.to_thread(ChatSession.objects.create, user=user)
            else:
                self.session = await asyncio.to_thread(ChatSession.objects.create, user=user)

            self.room_group_name = f"chat_{self.session.id}"
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
            await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        if hasattr(self, "session") and self.role == "user":
            await asyncio.to_thread(self.session.messages.create, sender='bot', message='Conversation closed.', language='en')  # Changed content to message

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            content = data.get('message', '').strip()
            role = data.get('role', self.role or 'user')
            language = data.get('language', 'en')

            if not content:
                return

            # Persist incoming message
            msg = await asyncio.to_thread(
                self.session.messages.create, 
                sender=role, 
                message=content,  # Changed content to message
                language=language
            )

            if role == 'user':
                # Use the centralized AI service
                bot_reply = await asyncio.to_thread(
                    get_ai_response, content, language
                )
                
                # Fallback to CSV if AI fails
                if not bot_reply:
                    bot_reply = await asyncio.to_thread(
                        search_csv_response, content, language
                    )
                
                if not bot_reply:
                    if language == 'fr':
                        bot_reply = "Désolé, je rencontre des difficultés techniques. Veuillez réessayer plus tard."
                    else:
                        bot_reply = "Sorry, I'm experiencing technical difficulties. Please try again later."
                
                # Save bot reply
                bot_msg = await asyncio.to_thread(
                    self.session.messages.create, 
                    sender='bot', 
                    message=bot_reply,  # Changed content to message
                    language=language
                )

                # Send bot reply to patient
                await self.channel_layer.group_send(
                    f"chat_{self.session.id}",
                    {
                        'type': 'chat_message', 
                        'message': bot_reply, 
                        'sender': 'bot',
                        'timestamp': bot_msg.timestamp.strftime("%H:%M"),
                        'language': language
                    }
                )

                # Forward patient's message to doctor (if connected)
                await self.channel_layer.group_send(
                    f"doctor_{self.session.id}",
                    {
                        'type': 'chat_message', 
                        'message': content, 
                        'sender': 'user',
                        'timestamp': msg.timestamp.strftime("%H:%M"),
                        'language': language
                    }
                )
                msg.forwarded_to_doctor = True
                await asyncio.to_thread(msg.save)

                # Forward bot reply to doctor
                await self.channel_layer.group_send(
                    f"doctor_{self.session.id}",
                    {
                        'type': 'chat_message', 
                        'message': bot_reply, 
                        'sender': 'bot',
                        'timestamp': bot_msg.timestamp.strftime("%H:%M"),
                        'language': language
                    }
                )
                bot_msg.forwarded_to_doctor = True
                await asyncio.to_thread(bot_msg.save)

            elif role == 'doctor':
                # Doctor sends message -> deliver to patient
                await self.channel_layer.group_send(
                    f"chat_{self.session.id}",
                    {
                        'type': 'chat_message', 
                        'message': content, 
                        'sender': 'doctor',
                        'timestamp': msg.timestamp.strftime("%H:%M"),
                        'language': language
                    }
                )

        except Exception as e:
            print(f"Error in receive: {e}")

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))