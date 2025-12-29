from django.urls import path
from . import views

urlpatterns = [
    path("", views.chat_api, name="chatbot_api"),               # POST /chatbot/
    path("fuzzy/last/", views.fuzzy_last_view, name="fuzzy_last"),  # GET /chatbot/fuzzy/last/
]
