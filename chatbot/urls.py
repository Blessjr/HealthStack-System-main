from django.urls import path
from .views import ChatView, chat_api, chatbot_response_view, tts_api, chatbot_view

app_name = 'chatbot'

urlpatterns = [
    path('', ChatView.as_view(), name='chat'),
    path('api/chat/', chat_api, name='chat-api'),
    path('chatbot/respond/', chatbot_response_view, name='chatbot_respond'),
    path('api/tts/', tts_api, name='tts-api'),
]
