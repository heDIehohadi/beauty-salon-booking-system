from datetime import time

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from services.models import Services
from stylists.models import Stylist, StylistWorkingHour


class PublicStylistAPITests(APITestCase):
    def setUp(self):
        self.active_service = Services.objects.create(
            name="Active Service",
            price="50.00",
            duration_minutes=60,
            is_active=True,
        )
        self.inactive_service = Services.objects.create(
            name="Inactive Service",
            price="30.00",
            duration_minutes=30,
            is_active=False,
        )
        self.stylist = Stylist.objects.create(
            first_name="Active",
            last_name="Stylist",
            is_active=True,
        )
        self.stylist.services.add(self.active_service, self.inactive_service)

    def test_list_is_public(self):
        # بدون authenticate هم باید کار کند (کاتالوگ عمومی است).
        response = self.client.get(reverse("stylist-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_excludes_inactive_stylists(self):
        Stylist.objects.create(
            first_name="Hidden",
            last_name="Stylist",
            is_active=False,
        )

        response = self.client.get(reverse("stylist-list"))

        ids = [item["id"] for item in response.data]
        self.assertEqual(ids, [self.stylist.pk])

    def test_list_excludes_inactive_services(self):
        response = self.client.get(reverse("stylist-list"))

        service_ids = [s["id"] for s in response.data[0]["services"]]
        self.assertEqual(service_ids, [self.active_service.pk])

    def test_list_query_count_does_not_grow_with_stylists(self):
        url = reverse("stylist-list")

        with CaptureQueriesContext(connection) as one_stylist:
            self.client.get(url)

        for index in range(3):
            extra = Stylist.objects.create(
                first_name=f"Extra{index}",
                last_name="Stylist",
                is_active=True,
            )
            extra.services.add(self.active_service)

        with CaptureQueriesContext(connection) as four_stylists:
            self.client.get(url)

        self.assertEqual(len(four_stylists), len(one_stylist))

    def test_detail_returns_stylist(self):
        response = self.client.get(
            reverse("stylist-detail", args=[self.stylist.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.stylist.pk)
        self.assertIn("working_hours", response.data)
        self.assertIn("portfolio", response.data)

    def test_detail_hides_inactive_working_hours(self):
        active_hour = StylistWorkingHour.objects.create(
            stylist=self.stylist,
            weekday=StylistWorkingHour.Weekday.MONDAY,
            start_time=time(10, 0),
            end_time=time(14, 0),
            is_active=True,
        )
        StylistWorkingHour.objects.create(
            stylist=self.stylist,
            weekday=StylistWorkingHour.Weekday.TUESDAY,
            start_time=time(10, 0),
            end_time=time(14, 0),
            is_active=False,
        )

        response = self.client.get(
            reverse("stylist-detail", args=[self.stylist.pk])
        )

        hour_ids = [h["id"] for h in response.data["working_hours"]]
        self.assertEqual(hour_ids, [active_hour.pk])

    def test_detail_of_inactive_stylist_is_404(self):
        hidden = Stylist.objects.create(
            first_name="Hidden",
            last_name="Stylist",
            is_active=False,
        )

        response = self.client.get(reverse("stylist-detail", args=[hidden.pk]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
