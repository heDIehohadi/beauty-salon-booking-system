from django.contrib import admin
from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "service",
        "stylist",
        "start_at",
        "end_at",
        "status",
    )

    list_filter = ("status", "start_at", "stylist")
    search_fields = (
        "customer__username",
        "service__name",
        "stylist__first_name",
        "stylist__last_name",
    )

    readonly_fields = ("created_at", "updated_at")
    list_per_page = 25