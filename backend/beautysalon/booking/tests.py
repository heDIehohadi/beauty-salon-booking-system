from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from booking.models import Booking
from services.models import Services
from stylists.models import Stylist, StylistWorkingHour


User = get_user_model()


class BookingAPITests(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="booking_customer",
            password="test-password-123",
        )

        self.service = Services.objects.create(
            name="Test Service",
            price="50.00",
            duration_minutes=60,
            is_active=True,
        )

        self.stylist = Stylist.objects.create(
            first_name="Test",
            last_name="Stylist",
            is_active=True,
        )
        self.stylist.services.add(self.service)

        self.client.force_authenticate(user=self.customer)

    def create_working_hour(self, start_at):
        local_start = timezone.localtime(start_at)
        local_end = local_start + timedelta(
            minutes=self.service.duration_minutes
        )

        if local_start.date() != local_end.date():
            raise ValueError("Test booking must not cross midnight.")

        StylistWorkingHour.objects.create(
            stylist=self.stylist,
            weekday=local_start.weekday(),
            start_time=(
                local_start - timedelta(hours=1)
            ).time().replace(tzinfo=None),
            end_time=(
                local_end + timedelta(hours=1)
            ).time().replace(tzinfo=None),
            is_active=True,
        )

    def create_booking(self, start_at=None):
        if start_at is None:
            start_at = timezone.now() + timedelta(days=1)

        self.create_working_hour(start_at)

        return self.client.post(
            reverse("booking-list-create"),
            {
                "service": self.service.pk,
                "stylist": self.stylist.pk,
                "start_at": start_at.isoformat(),
                "customer_note": "Test booking",
            },
            format="json",
        )

    def test_create_valid_booking(self):
        """ایجاد رزرو معتبر و بررسی زمان پایان."""
        start_at = timezone.now() + timedelta(days=1)
        response = self.create_booking(start_at)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            msg=f"Booking API error: {response.data}",
        )

        self.assertEqual(Booking.objects.count(), 1)

        booking = Booking.objects.get()

        self.assertEqual(booking.customer, self.customer)
        self.assertEqual(booking.service, self.service)
        self.assertEqual(booking.stylist, self.stylist)
        self.assertEqual(booking.status, Booking.Status.PENDING)

        expected_end_at = start_at + timedelta(
            minutes=self.service.duration_minutes
        )
        self.assertEqual(booking.end_at, expected_end_at)

    def test_list_only_current_customer_bookings(self):
        """فهرست رزروهای کاربر واردشده."""
        create_response = self.create_booking()

        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED,
            msg=f"Booking API error: {create_response.data}",
        )

        response = self.client.get(
            reverse("booking-list-create")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["customer"],
            self.customer.pk,
        )

    def test_cancel_booking(self):
        """لغو رزرو متعلق به کاربر واردشده."""
        create_response = self.create_booking()

        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED,
            msg=f"Booking API error: {create_response.data}",
        )

        booking = Booking.objects.get()

        response = self.client.patch(
            reverse(
                "booking-cancel",
                kwargs={"pk": booking.pk},
            ),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            msg=f"Cancel API error: {response.data}",
        )

        booking.refresh_from_db()
        self.assertEqual(
            booking.status,
            Booking.Status.CANCELLED,
        )

    def test_booking_requires_authentication(self):
        """ایجاد رزرو بدون ورود باید رد شود."""
        self.client.force_authenticate(user=None)

        response = self.client.post(
            reverse("booking-list-create"),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )