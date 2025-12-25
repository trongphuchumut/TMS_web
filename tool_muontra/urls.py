# tool_muontra/urls.py
from django.urls import path
from . import views, views_api

app_name = "tool_muontra"

urlpatterns = [
    # ===== UI =====
    path("history/", views.history_tool, name="history_tool"),
    path("transaction/<int:tool_id>/", views.tool_transaction_create, name="tool_transaction_create"),

    # ===== API =====
    path("api/tool/<int:tool_id>/export/", views_api.api_tool_export, name="api_tool_export"),
    path("api/tool/<int:tool_id>/import/", views_api.api_tool_import, name="api_tool_import"),
    path("api/tool/<int:tool_id>/return/", views_api.api_tool_return, name="api_tool_return"),
    path("api/tool/tx/<int:tx_id>/", views_api.api_check_tool_tx, name="api_check_tool_tx"),
    path("tx/<int:tx_id>/wait/", views.tool_transaction_wait, name="tool_transaction_wait"),
]
