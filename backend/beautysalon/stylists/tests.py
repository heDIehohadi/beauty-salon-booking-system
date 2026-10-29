from datetime import time

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from stylists.models import Stylist, StylistWorkingHour


class StylistWorkingHourTests(TestCase):
    def setUp(self):
        self.stylist = Stylist.objects.create(
            first_name="Test",
            last_name="Stylist",
            is_active=True,
        )

    def test_create_working_hour(self):
        working_hour = StylistWorkingHour.objects.create(
            stylist=self.stylist,
            weekday=StylistWorkingHour.Weekday.MONDAY,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        self.assertEqual(working_hour.stylist, self.stylist)
        self.assertEqual(working_hour.start_time, time(9, 0))
        self.assertEqual(working_hour.end_time, time(17, 0))
        self.assertTrue(working_hour.is_active)

    def test_duplicate_working_hour_start_is_rejected(self):
        StylistWorkingHour.objects.create(
            stylist=self.stylist,
            weekday=StylistWorkingHour.Weekday.MONDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StylistWorkingHour.objects.create(
                    stylist=self.stylist,
                    weekday=StylistWorkingHour.Weekday.MONDAY,
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                )

    def test_overlapping_working_hours_are_rejected_by_clean(self):
        StylistWorkingHour.objects.create(
            stylist=self.stylist,
            weekday=StylistWorkingHour.Weekday.MONDAY,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )

        overlapping_hour = StylistWorkingHour(
            stylist=self.stylist,
            weekday=StylistWorkingHour.Weekday.MONDAY,
            start_time=time(11, 0),
            end_time=time(15, 0),
        )

        with self.assertRaises(ValidationError):
            overlapping_hour.clean()