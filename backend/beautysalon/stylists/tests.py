from datetime import time
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

        with self.assertRaises(Exception):
            StylistWorkingHour.objects.create(
                stylist=self.stylist,
                weekday=StylistWorkingHour.Weekday.MONDAY,
                start_time=time(9, 0),
                end_time=time(17, 0),
            )
