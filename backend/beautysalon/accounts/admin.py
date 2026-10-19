from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import OTPRequest
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "phone_number",
        "role",
        "is_phone_verified",
        "is_staff",
        "is_active",
    )

    list_filter = (
        "role",
        "is_phone_verified",
        "is_staff",
        "is_active",
    )

    search_fields = (
        "username",
        "phone_number",
        "first_name",
        "last_name",
    )

    fieldsets = UserAdmin.fieldsets + (
        (
            "Additional Information",
            {
                "fields": (
                    "phone_number",
                    "role",
                    "is_phone_verified",
                )
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Additional Information",
            {
                "fields": (
                    "phone_number",
                    "role",
                )
            },
        ),
    )

@admin.register(OTPRequest)
class OTPRequestAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "is_used",
        "attempts",
        "created_at",
        "expires_at",
    )
    list_filter = ("is_used", "created_at")
    search_fields = ("user__username", "user__phone_number")
    readonly_fields = (
        "user",
        "otp_code",
        "created_at",
        "expires_at",
        "attempts",
        "is_used",
    )    