from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.username


class OTPBase(models.Model):
    """A single-use, expiring OTP tied to a user. The code is stored hashed
    (via make_password); compare with check_password, never equality."""

    OTP_TTL = timedelta(minutes=10)

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + self.OTP_TTL
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at


class EmailVerification(OTPBase):
    def __str__(self):
        return f"EmailVerification for {self.user}"


class PasswordReset(OTPBase):
    def __str__(self):
        return f"PasswordReset for {self.user}"
