# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required

def login_view(request):

    if request.method == "POST":
        print(">>> LOGIN POST RECEIVED")  # dòng debug
        username = request.POST.get("username")
        password = request.POST.get("password")
        remember = request.POST.get("remember_me")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            # Không tick "Ghi nhớ đăng nhập" → session hết khi đóng trình duyệt
            if not remember:
                request.session.set_expiry(0)

            return redirect('home')
        else:
            # THÔNG BÁO LỖI Ở ĐÂY
            messages.error(request, "Sai tên đăng nhập hoặc mật khẩu!")

    return render(request, "login.html")


@login_required
def home(request):
    return render(request, "home.html")


def contact(request):
    return render(request, "contact.html")


def logout_view(request):
    logout(request)
    return redirect('login')


from tool.models import Tool      # chỉnh lại nếu Tool nằm app khác
from holder.models import Holder  # chỉnh lại nếu Holder nằm app khác

def borrow_dashboard(request):
    tools = Tool.objects.all()[:200]
    holders = Holder.objects.all()[:200]

    context = {
        "tools": tools,
        "holders": holders,
    }
    return render(request, "borrow_dashboard.html", context)