from django.urls import path
from . import views
from .views_api import api_check_tool_tx

app_name = "tool_muontra"

urlpatterns = [
    path("history/", views.history_tool, name="history_tool"),
    path("transaction/<int:tool_id>/", views.tool_transaction_create, name="tool_transaction_create"),
    path("api/check-tool-tx/<int:tx_id>/", api_check_tool_tx, name="check_tool_tx"),
]
