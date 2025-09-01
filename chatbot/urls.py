from django.urls import path
from .views import ChatView, chat_api, csv_fallback_api,tts_api, chatbot_view

app_name = 'chatbot'

urlpatterns = [
    path('', ChatView.as_view(), name='chat'),
    path('api/chat/', chat_api, name='chat-api'),
    path('api/tts/', tts_api, name='tts-api'),
    path('api/fallback/', csv_fallback_api, name='csv-fallback'),
]
