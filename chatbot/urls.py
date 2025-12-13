# chatbot/urls.py
from django.urls import path
from . import views

app_name = "chatbot"

urlpatterns = [
    path("", views.chatbot_view, name="chatbot_api"),
    path("fuzzy/last/", views.fuzzy_last_page, name="fuzzy_last_page"),
    path("api/fuzzy/last/", views.api_fuzzy_last, name="api_fuzzy_last"),

]
