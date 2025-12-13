from django.contrib import admin
from django.urls import path, include
from chatbot.views import chatbot_view
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('khocongcu/', include('khocongcu.urls')),
    path("holder/", include("holder.urls")),
    path("tool/", include("tool.urls")),
    path("tool-muontra/", include("tool_muontra.urls")),
    path("holder-muontra/", include("holder_muontra.urls")),
     path("chatbot/", include("chatbot.urls")),
]
