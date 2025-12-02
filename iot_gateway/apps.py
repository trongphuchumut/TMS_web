# iot_gateway/apps.py
from django.apps import AppConfig

class IotGatewayConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "iot_gateway"
    verbose_name = "TMS IoT Gateway (MQTT)"
