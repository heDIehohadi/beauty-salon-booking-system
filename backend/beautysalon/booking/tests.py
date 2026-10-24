
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from services.models import Services
from stylists.models import Stylist
from booking.models import Booking


User = get_user_model()


class BookingAPITests(APITestCase):

    def setUp(self):
        """
        ساخت داده‌های اولیه برای تست‌ها.
        این متد قبل از اجرای هر تست اجرا می‌شود.
        """

        self.customer = User.objects.create_user(
            username="test_customer",
            password="TestPassword123!",
            phone_number="09120000000",
            is_phone_verified=True,
        )

        self.service = Services.objects.create(
            name="Manicure",
            category=Services.Category.NAILS,
            description="Test manicure service",
            price="500.00",
            duration_minutes=45,
            is_active=True,
        )

        self.stylist = Stylist.objects.create(
            first_name="Test",
            last_name="Stylist",
            is_active=True,
        )

        self.stylist.services.add(self.service)

        self.client.force_authenticate(user=self.customer)

    def test_create_valid_booking(self):
        """
        بررسی ایجاد رزرو معتبر و محاسبه زمان پایان.
        """

        start_at = timezone.now() + timedelta(days=1)

        response = self.client.post(
            reverse("booking-list-create"),
            {
                "service": self.service.pk,
                "stylist": self.stylist.pk,
                "start_at": start_at.isoformat(),
                "customer_note": "First test booking",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            Booking.objects.count(),
            1,
        )

        booking = Booking.objects.get()

        self.assertEqual(
            booking.customer,
            self.customer,
        )

        self.assertEqual(
            booking.end_at - booking.start_at,
            timedelta(minutes=45),
        )