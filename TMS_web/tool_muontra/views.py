from django.shortcuts import render, get_object_or_404
from tool.models import Tool  # hoặc khocongcu.models.Tool tùy bạn

def history_tool(request):
    # Tạm trả về trang rỗng / danh sách đơn xuất theo tool sau
    return render(request, "tool_history.html")

def request_export(request, tool_id):
    tool = get_object_or_404(Tool, pk=tool_id)
    # Tạm thời chỉ hiển thị thông tin, sau này làm form xin xuất kho
    return render(request, "tool_request_export.html", {"tool": tool})
