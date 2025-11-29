from django import forms
from .models import ChatbotConfig


class ChatbotConfigForm(forms.ModelForm):
    class Meta:
        model = ChatbotConfig
        fields = [
            "bot_name",
            "enable_smalltalk",
            "max_search_results",
            "max_fuzzy_suggestions",
            "search_auto_show_threshold",
            "fuzzy_need_more_info_threshold",
            "enable_debug_block",
            "tone",
        ]
        widgets = {
            "search_auto_show_threshold": forms.NumberInput(attrs={"step": "0.05", "min": "0", "max": "1"}),
            "fuzzy_need_more_info_threshold": forms.NumberInput(attrs={"step": "0.05", "min": "0", "max": "1"}),
        }
