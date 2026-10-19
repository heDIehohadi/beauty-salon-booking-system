from django.conf import settings
from django.db import models


class Booking(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    service = models.ForeignKey(
        "services.Services",
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    stylist = models.ForeignKey(
        "stylists.Stylist",
        on_delete=models.PROTECT,
        related_name="bookings",
    )

    start_at = models.DateTimeField()
    end_at = models.DateTimeField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    customer_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_at"]
        indexes = [
            models.Index(fields=["stylist", "start_at"]),
            models.Index(fields=["customer", "start_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return (
            f"{self.service.name} - "
            f"{self.customer.username} - "
            f"{self.start_at}"
        )