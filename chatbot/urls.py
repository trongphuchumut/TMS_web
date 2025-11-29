from django.urls import path
from chatbot.views import chatbot_view

urlpatterns = [
    path("api/chatbot/", chatbot_view, name="chatbot_api"),

]
