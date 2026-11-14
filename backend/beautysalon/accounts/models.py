from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    def create_superuser(
        self, username, email=None, password=None, **extra_fields
    ):
        # A superuser created from the command line is a trusted operator:
        # make them a salon admin and skip OTP verification so they can
        # use the token login and the admin-only endpoints.
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_phone_verified", True)
        return super().create_superuser(
            username, email, password, **extra_fields
        )


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        ADMIN = "admin", "Admin"

    phone_number = models.CharField(
        max_length=15,
        unique=True,
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.CUSTOMER,
    )
    is_phone_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    # phone_number is unique and has no default, so `createsuperuser` must
    # ask for it; otherwise every superuser would get "" and the second
    # one would fail with an IntegrityError.
    REQUIRED_FIELDS = ["email", "phone_number"]

    def __str__(self):
        return self.username


class OTPRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="otp_requests",
    )
    otp_code = models.CharField(max_length=128)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP for {self.user.phone_number}"    