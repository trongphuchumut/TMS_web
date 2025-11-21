# Create your views here.
from django.shortcuts import render, get_object_or_404
from holder.models import Holder  # app holder của bạn

def history_holder(request):
    return render(request, "holder_muontra/history_holder.html")

def borrow_for_holder(request, holder_id):
    holder = get_object_or_404(Holder, pk=holder_id)
    return render(request, "holder_borrow.html", {"holder": holder})

def return_for_holder(request, holder_id):
    holder = get_object_or_404(Holder, pk=holder_id)
    return render(request, "holder_return.html", {"holder": holder})
