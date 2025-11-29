from django.urls import path
from . import views

app_name = "tool"

urlpatterns = [
    # /tool/  -> danh sách tool
    path("", views.tool_list, name="tool_list"),

    # /tool/new/  -> tạo tool mới
    path("new/", views.tool_create, name="tool_create"),

    # /tool/5/  -> profile chi tiết tool id=5
    path("<int:pk>/", views.tool_profile, name="tool_profile"),
]
