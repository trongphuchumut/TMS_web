from django.urls import path
from . import views
from .views_api import api_check_borrow_tx, api_check_return_tx
app_name = "holder_muontra"

urlpatterns = [
    path("history/", views.history_holder, name="history_holder"),
    path("borrow/<int:holder_id>/", views.borrow_for_holder, name="borrow_for_holder"),
    path("return/<int:holder_id>/", views.return_for_holder, name="return_for_holder"),
    path("api/borrow-tx/<int:tx_id>/", api_check_borrow_tx, name="api_check_borrow_tx"),
    path("api/return-tx/<int:tx_id>/", api_check_return_tx, name="api_check_return_tx"),
    path("wait/<int:tx_id>/<str:mode>/", views.wait_holder, name="wait_holder"),

]
