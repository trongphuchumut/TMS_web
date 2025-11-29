from django.urls import path
from . import views

app_name = "holder"

urlpatterns = [
    path("", views.holder_profile, name="holder_profile"),  # /holder/
    path("holders-list/", views.holder_list, name="holder_list"),  # <--- thêm dòng này
    path("holders/new/", views.holder_create, name="holder_create"),
    path("holders/<int:pk>/", views.holder_profile, name="holder_detail"),
    # ... sau này thêm holder_list, edit, v.v.
]
