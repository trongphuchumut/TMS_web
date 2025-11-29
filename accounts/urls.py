# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path("ajax/search-suggest/", views.search_suggest, name="search_suggest"),  # <- NEW

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('contact/', views.contact, name='contact'),
    path("borrow/", views.borrow_dashboard, name="borrow_dashboard"),
    # === QUÊN MẬT KHẨU / RESET MẬT KHẨU ===
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='password/password_reset.html'
        ),
        name='password_reset',
    ),

    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='password/password_reset_done.html'
        ),
        name='password_reset_done',
    ),

    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='password/password_reset_confirm.html'
        ),
        name='password_reset_confirm',
    ),

    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='password/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),
]
