from django.urls import path
from . import views

app_name = "tool_muontra"

urlpatterns = [
    path("history/", views.history_tool, name="history_tool"),
    path("transaction/<int:tool_id>/", views.tool_transaction_create, name="tool_transaction_create"),
]
