from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from booking.models import Booking
from services.models import Services
from stylists.models import Stylist, StylistTimeOff, StylistWorkingHour

User = get_user_model()


class BookingEdgeCaseTests(APITestCase):
    """
    Edge cases of the booking API: cancellation rules, ownership,
    exact-fit slots, time off and invalid booking requests.
    """

    def setUp(self):
        self.customer = User.objects.create_user(
            username="edge_customer",
            password="test-password-123",
            phone_number="09120000011",
        )
        self.other_customer = User.objects.create_user(
            username="edge_other_customer",
            password="test-password-123",
            phone_number="09120000012",
        )
        self.service = Services.objects.create(
            name="Edge Service",
            price="50.00",
            duration_minutes=60,
            is_active=True,
        )
        self.stylist = Stylist.objects.create(
            first_name="Edge",
            last_name="Stylist",
            is_active=True,
        )
        self.stylist.services.add(self.service)
        self.target_date = timezone.localdate() + timedelta(days=2)
        self.client.force_authenticate(user=self.customer)

    # ---------- helpers ----------

    def aware(self, hour, minute=0, day=None):
        day = day or self.target_date
        return timezone.make_aware(
            datetime.combine(day, time(hour, minute)),
            timezone.get_current_timezone(),
        )

    def add_working_hour(self, start, end, is_active=True):
        return StylistWorkingHour.objects.create(
            stylist=self.stylist,
            weekday=self.target_date.weekday(),
            start_time=start,
            end_time=end,
            is_active=is_active,
        )

    def make_booking(self, customer=None, status_value=None, hour=10):
        start_at = self.aware(hour)
        return Booking.objects.create(
            customer=customer or self.customer,
            service=self.service,
            stylist=self.stylist,
            start_at=start_at,
            end_at=start_at + timedelta(minutes=self.service.duration_minutes),
            status=status_value or Booking.Status.CONFIRMED,
        )

    def get_slots(self):
        response = self.client.get(
            reverse("available-slots"),
            {
                "stylist": self.stylist.pk,
                "service": self.service.pk,
                "date": self.target_date.isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data["available_slots"]

    def post_booking(self, start_at):
        return self.client.post(
            reverse("booking-list-create"),
            {
                "service": self.service.pk,
                "stylist": self.stylist.pk,
                "start_at": start_at.isoformat(),
            },
            format="json",
        )

    # ---------- cancellation ----------

    def test_cancel_already_cancelled_booking_returns_400(self):
        booking = self.make_booking(status_value=Booking.Status.CANCELLED)

        response = self.client.patch(
            reverse("booking-cancel", args=[booking.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_completed_booking_returns_400(self):
        booking = self.make_booking(status_value=Booking.Status.COMPLETED)

        response = self.client.patch(
            reverse("booking-cancel", args=[booking.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.COMPLETED)

    def test_cannot_cancel_another_customers_booking(self):
        booking = self.make_booking(customer=self.other_customer)

        response = self.client.patch(
            reverse("booking-cancel", args=[booking.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

    def test_cancel_requires_authentication(self):
        booking = self.make_booking()
        self.client.force_authenticate(user=None)

        response = self.client.patch(
            reverse("booking-cancel", args=[booking.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cancel_rejects_post(self):
        # قرارداد API: لغو با PATCH انجام می‌شود، نه POST.
        booking = self.make_booking()

        response = self.client.post(
            reverse("booking-cancel", args=[booking.pk])
        )

        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
        )

    def test_cancelled_booking_frees_the_slot(self):
        self.add_working_hour(time(10, 0), time(11, 0))
        booking = self.make_booking(hour=10)
        self.assertEqual(self.get_slots(), [])

        self.client.patch(reverse("booking-cancel", args=[booking.pk]))

        self.assertEqual(len(self.get_slots()), 1)

    # ---------- ownership ----------

    def test_cannot_view_another_customers_booking_detail(self):
        booking = self.make_booking(customer=self.other_customer)

        response = self.client.get(
            reverse("booking-detail", args=[booking.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ---------- available slots ----------

    def test_exact_fit_service_gives_exactly_one_slot(self):
        # سرویس ۶۰ دقیقه‌ای در بازه‌ی ۶۰ دقیقه‌ای دقیقاً یک نوبت دارد.
        self.add_working_hour(time(10, 0), time(11, 0))

        slots = self.get_slots()

        self.assertEqual(len(slots), 1)
        self.assertEqual(
            datetime.fromisoformat(slots[0]["start_at"]), self.aware(10)
        )
        self.assertEqual(
            datetime.fromisoformat(slots[0]["end_at"]), self.aware(11)
        )

    def test_available_slots_exclude_active_time_off(self):
        self.add_working_hour(time(10, 0), time(12, 0))
        StylistTimeOff.objects.create(
            stylist=self.stylist,
            start_at=self.aware(10),
            end_at=self.aware(11),
            is_active=True,
        )

        slots = self.get_slots()

        # فقط نوبت ۱۱:۰۰ تا ۱۲:۰۰ با استراحت تداخل ندارد.
        self.assertEqual(len(slots), 1)
        self.assertEqual(
            datetime.fromisoformat(slots[0]["start_at"]), self.aware(11)
        )

    def test_inactive_time_off_does_not_block_slots(self):
        self.add_working_hour(time(10, 0), time(11, 0))
        StylistTimeOff.objects.create(
            stylist=self.stylist,
            start_at=self.aware(10),
            end_at=self.aware(11),
            is_active=False,
        )

        self.assertEqual(len(self.get_slots()), 1)

    def test_available_slots_ignore_inactive_working_hours(self):
        self.add_working_hour(time(10, 0), time(12, 0), is_active=False)

        self.assertEqual(self.get_slots(), [])

    def test_available_slots_for_past_date_returns_400(self):
        response = self.client.get(
            reverse("available-slots"),
            {
                "stylist": self.stylist.pk,
                "service": self.service.pk,
                "date": (timezone.localdate() - timedelta(days=1)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---------- creating bookings ----------

    def test_overlapping_booking_is_rejected(self):
        self.add_working_hour(time(10, 0), time(13, 0))
        self.make_booking(customer=self.other_customer, hour=10)

        response = self.post_booking(self.aware(10, 30))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Booking.objects.count(), 1)

    def test_back_to_back_booking_is_allowed(self):
        self.add_working_hour(time(10, 0), time(13, 0))
        self.make_booking(customer=self.other_customer, hour=10)

        response = self.post_booking(self.aware(11))

        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED, response.data
        )

    def test_booking_outside_working_hours_is_rejected(self):
        self.add_working_hour(time(10, 0), time(11, 0))

        # ۱۰:۳۰ شروع می‌شود و ۱۱:۳۰ تمام می‌شود، یعنی بیرون از بازه.
        response = self.post_booking(self.aware(10, 30))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_during_time_off_is_rejected(self):
        self.add_working_hour(time(10, 0), time(13, 0))
        StylistTimeOff.objects.create(
            stylist=self.stylist,
            start_at=self.aware(11),
            end_at=self.aware(12),
            is_active=True,
        )

        response = self.post_booking(self.aware(11))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_booking_in_the_past_is_rejected(self):
        yesterday = self.target_date - timedelta(days=3)

        response = self.post_booking(self.aware(10, day=yesterday))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
