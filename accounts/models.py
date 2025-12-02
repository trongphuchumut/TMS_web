from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    rfid_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="RFID của người dùng để xác thực khi mượn/trả"
    )

    def __str__(self):
        return f"RFID {self.rfid_code} - {self.user.username}"
