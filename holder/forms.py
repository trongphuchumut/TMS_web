
from django import forms
from .models import Holder

class HolderForm(forms.ModelForm):
    class Meta:
        model = Holder
        fields = [
            "ma_noi_bo",
            "ten_thiet_bi",
            # thêm các field khác bạn cần
        ]

    def clean_ma_noi_bo(self):
        ma = self.cleaned_data.get("ma_noi_bo")
        if Holder.objects.filter(ma_noi_bo=ma).exists():
            raise forms.ValidationError("Mã nội bộ này đã tồn tại, vui lòng nhập mã khác.")
        return ma
