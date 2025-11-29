from django.urls import path
from . import views

app_name = "khocongcu"

urlpatterns = [
    # ...
    path("kho/", views.kho_cong_cu_view, name="kho_cong_cu"),
]
