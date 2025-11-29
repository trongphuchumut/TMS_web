from django.urls import path
from . import views

app_name = "holder_muontra"

urlpatterns = [
    path("history/", views.history_holder, name="history_holder"),
    path("borrow/<int:holder_id>/", views.borrow_for_holder, name="borrow_for_holder"),
    path("return/<int:holder_id>/", views.return_for_holder, name="return_for_holder"),
]
