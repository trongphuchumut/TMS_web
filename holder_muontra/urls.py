from django.urls import path
from . import views
from .views_api import api_check_holder_tx
app_name = "holder_muontra"

urlpatterns = [
    path("history/", views.history_holder, name="history_holder"),
    path("borrow/<int:holder_id>/", views.borrow_for_holder, name="borrow_for_holder"),
    path("return/<int:holder_id>/", views.return_for_holder, name="return_for_holder"),
    path("api/check-holder-tx/<int:tx_id>/", api_check_holder_tx, name="check_holder_tx"),
        path("wait/<int:tx_id>/", views.wait_holder, name="wait_holder"),

]
