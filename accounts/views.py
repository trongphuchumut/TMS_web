# accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Q
from django.http import JsonResponse
from holder.models import Holder
from tool.models import Tool

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
    q = request.GET.get("q", "").strip()

    holder_results = []
    tool_results = []

    if q:
        holder_results = Holder.objects.filter(
            Q(ten_thiet_bi__icontains=q)
            | Q(ma_noi_bo__icontains=q)
            | Q(ma_nha_sx__icontains=q)
        )[:20]

        tool_results = Tool.objects.filter(
            Q(ten_tool__icontains=q)
            | Q(ma_tool__icontains=q)
            | Q(ma_nha_sx__icontains=q)
        )[:20]

    context = {
        "q": q,
        "holder_results": holder_results,
        "tool_results": tool_results,
    }
    return render(request, "home.html", context)

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

@login_required
def search_suggest(request):
    q = request.GET.get("q", "").strip()

    if not q:
        return JsonResponse({"tools": [], "holders": []})

    # Lấy ít thôi, ví dụ 5 kết quả mỗi loại
    tools_qs = Tool.objects.filter(
        Q(ten_tool__icontains=q) |
        Q(ma_tool__icontains=q)
    )[:5]

    holders_qs = Holder.objects.filter(
        Q(ten_thiet_bi__icontains=q) |
        Q(ma_noi_bo__icontains=q)
    )[:5]

    data = {
        "tools": [
            {
                "id": t.id,
                "label": f"{t.ten_tool} ({t.ma_tool})"
            }
            for t in tools_qs
        ],
        "holders": [
            {
                "id": h.id,
                "label": f"{h.ten_thiet_bi} ({h.ma_noi_bo})"
            }
            for h in holders_qs
        ],
    }
    return JsonResponse(data)
def my_logout(request):
    # Xóa riêng key chatbot
    request.session.pop("chat_history", None)

    # Hoặc xóa luôn cả session:
    # request.session.flush()

    logout(request)
    return redirect("login")   # đổi sang tên url trang login của bạn