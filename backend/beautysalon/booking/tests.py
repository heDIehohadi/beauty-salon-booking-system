from datetime import datetime, time, timedelta

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

    def get_future_booking_start(self):
        tomorrow = timezone.localdate() + timedelta(days=1)
        local_start = datetime.combine(tomorrow, time(10, 0))

        return timezone.make_aware(
            local_start,
            timezone.get_current_timezone(),
        )

    def create_working_hour(self, start_at):
        local_start = timezone.localtime(start_at)
        local_end = local_start + timedelta(
            minutes=self.service.duration_minutes
        )

        if local_start.date() != local_end.date():
            raise ValueError("Test booking must not cross midnight.")

        StylistWorkingHour.objects.get_or_create(
            stylist=self.stylist,
            weekday=local_start.weekday(),
            start_time=time(9, 0),
            end_time=time(12, 0),
            defaults={"is_active": True},
        )

    def create_booking(self, start_at=None):
        if start_at is None:
            start_at = self.get_future_booking_start()

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
        start_at = self.get_future_booking_start()
        response = self.create_booking(start_at)

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            response.data,
        )
        self.assertEqual(Booking.objects.count(), 1)

        booking = Booking.objects.get()
        self.assertEqual(booking.customer, self.customer)
        self.assertEqual(booking.service, self.service)
        self.assertEqual(booking.stylist, self.stylist)

        expected_end = start_at + timedelta(
            minutes=self.service.duration_minutes
        )
        self.assertEqual(
            booking.end_at,
            expected_end,
        )

    def test_list_only_current_customer_bookings(self):
        create_response = self.create_booking()

        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED,
            create_response.data,
        )
        other_customer = User.objects.create_user(
            username="other_customer",
            password="test-password-123",
            phone_number="09120000002",
        )

        other_booking_start = self.get_future_booking_start() + timedelta(
            days=1
        )

        self.create_working_hour(other_booking_start)

        Booking.objects.create(
            customer=other_customer,
            service=self.service,
            stylist=self.stylist,
            start_at=other_booking_start,
            end_at=other_booking_start + timedelta(
                minutes=self.service.duration_minutes
            ),
        )

        response = self.client.get(reverse("booking-list-create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_ids = [item["id"] for item in response.data]
        self.assertEqual(len(returned_ids), 1)

    def test_cancel_booking(self):
        create_response = self.create_booking()

        self.assertEqual(
            create_response.status_code,
            status.HTTP_201_CREATED,
            create_response.data,
        )

        booking_id = create_response.data["id"]

        response = self.client.patch(
            reverse("booking-cancel", args=[booking_id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        booking = Booking.objects.get(pk=booking_id)
        self.assertEqual(booking.status, Booking.Status.CANCELLED)

    def test_booking_requires_authentication(self):
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

    def test_available_slots_returns_15_minute_intervals(self):
        requested_date = timezone.localdate() + timedelta(days=2)

        StylistWorkingHour.objects.create(
            stylist=self.stylist,
            weekday=requested_date.weekday(),
            start_time=time(10, 0),
            end_time=time(12, 0),
            is_active=True,
        )

        response = self.client.get(
            reverse("available-slots"),
            {
                "stylist": self.stylist.pk,
                "service": self.service.pk,
                "date": requested_date.isoformat(),
            },
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            response.data,
        )

        starts = [
            timezone.localtime(
                datetime.fromisoformat(slot["start_at"])
            ).minute
            for slot in response.data["available_slots"]
        ]

        self.assertTrue(all(minute % 15 == 0 for minute in starts))

    def test_available_slots_respect_service_duration(self):
        self.service.duration_minutes = 60
        self.service.save()

        requested_date = timezone.localdate() + timedelta(days=2)

        StylistWorkingHour.objects.create(
            stylist=self.stylist,
            weekday=requested_date.weekday(),
            start_time=time(10, 0),
            end_time=time(10, 45),
            is_active=True,
        )

        response = self.client.get(
            reverse("available-slots"),
            {
                "stylist": self.stylist.pk,
                "service": self.service.pk,
                "date": requested_date.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["available_slots"], [])

    def test_available_slots_exclude_existing_booking_conflicts(self):
        requested_date = timezone.localdate() + timedelta(days=2)

        StylistWorkingHour.objects.create(
            stylist=self.stylist,
            weekday=requested_date.weekday(),
            start_time=time(10, 0),
            end_time=time(12, 0),
            is_active=True,
        )

        booking_start = timezone.make_aware(
            datetime.combine(requested_date, time(10, 0)),
            timezone.get_current_timezone(),
        )

        Booking.objects.create(
            customer=self.customer,
            service=self.service,
            stylist=self.stylist,
            start_at=booking_start,
            end_at=booking_start + timedelta(
                minutes=self.service.duration_minutes
            ),
            status=Booking.Status.CONFIRMED,
        )

        response = self.client.get(
            reverse("available-slots"),
            {
                "stylist": self.stylist.pk,
                "service": self.service.pk,
                "date": requested_date.isoformat(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for slot in response.data["available_slots"]:
            slot_start = datetime.fromisoformat(slot["start_at"])
            slot_end = datetime.fromisoformat(slot["end_at"])

            self.assertFalse(
                slot_start < booking_start + timedelta(
                    minutes=self.service.duration_minutes
                )
                and slot_end > booking_start
            )