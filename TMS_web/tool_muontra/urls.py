from django.urls import path
from . import views

app_name = "tool_muontra"

urlpatterns = [
    path("history/", views.history_tool, name="history_tool"),
    path("request-export/<int:tool_id>/", views.request_export, name="request_export"),
]
