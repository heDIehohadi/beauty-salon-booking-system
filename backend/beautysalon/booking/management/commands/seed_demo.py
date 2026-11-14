from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from services.models import Services
from stylists.models import Stylist, StylistTimeOff, StylistWorkingHour

User = get_user_model()
Weekday = StylistWorkingHour.Weekday

SERVICES = [
    # name, category, price, duration in minutes, description
    ("Manicure", Services.Category.NAILS, "20.00", 45, "Classic manicure."),
    ("Gel Polish", Services.Category.NAILS, "30.00", 60, "Gel polish."),
    ("Haircut", Services.Category.HAIR, "25.00", 45, "Wash and haircut."),
    ("Hair Coloring", Services.Category.HAIR, "80.00", 120, "Full color."),
    ("Blow Dry", Services.Category.HAIR, "15.00", 30, "Wash and blow dry."),
    ("Facial Cleansing", Services.Category.SKIN, "40.00", 60, "Deep cleansing."),
]

MON_TO_SAT = [
    Weekday.MONDAY,
    Weekday.TUESDAY,
    Weekday.WEDNESDAY,
    Weekday.THURSDAY,
    Weekday.FRIDAY,
    Weekday.SATURDAY,
]

STYLISTS = [
    {
        "first_name": "Sara",
        "last_name": "Ahmadi",
        "bio": "Hair specialist.",
        "services": ["Haircut", "Hair Coloring", "Blow Dry"],
        # two intervals a day: a lunch break between 14:00 and 15:00
        "hours": [
            (day, time(10, 0), time(14, 0)) for day in MON_TO_SAT
        ]
        + [(day, time(15, 0), time(20, 0)) for day in MON_TO_SAT],
    },
    {
        "first_name": "Maryam",
        "last_name": "Karimi",
        "bio": "Nail artist.",
        "services": ["Manicure", "Gel Polish"],
        "hours": [
            (day, time(10, 0), time(18, 0)) for day in MON_TO_SAT[:5]
        ],
    },
    {
        "first_name": "Neda",
        "last_name": "Rahimi",
        "bio": "Skin care and blow dry.",
        "services": ["Facial Cleansing", "Blow Dry"],
        "hours": [
            (day, time(12, 0), time(20, 0)) for day in MON_TO_SAT[1:]
        ],
    },
]


class Command(BaseCommand):
    help = (
        "Create demo data (users, services, stylists, working hours, one "
        "leave day). Safe to run more than once; existing rows are kept."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="demo-pass-12345",
            help="Password for the demo users (default: demo-pass-12345).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]

        self.create_user("demo_admin", "09120000000", password, admin=True)
        self.create_user("demo_customer", "09120000001", password)

        services = {}
        for name, category, price, minutes, description in SERVICES:
            service, _ = Services.objects.get_or_create(
                name=name,
                defaults={
                    "category": category,
                    "price": Decimal(price),
                    "duration_minutes": minutes,
                    "description": description,
                },
            )
            services[name] = service

        stylists = []
        for data in STYLISTS:
            stylist, _ = Stylist.objects.get_or_create(
                first_name=data["first_name"],
                last_name=data["last_name"],
                defaults={"bio": data["bio"]},
            )
            stylist.services.add(*(services[n] for n in data["services"]))
            for weekday, start, end in data["hours"]:
                StylistWorkingHour.objects.get_or_create(
                    stylist=stylist,
                    weekday=weekday,
                    start_time=start,
                    defaults={"end_time": end},
                )
            stylists.append(stylist)

        # One leave day for the third stylist, three days from now.
        day = timezone.localdate() + timedelta(days=3)
        tz = timezone.get_current_timezone()
        StylistTimeOff.objects.get_or_create(
            stylist=stylists[2],
            type=StylistTimeOff.Type.LEAVE,
            start_at=timezone.make_aware(datetime.combine(day, time(0, 0)), tz),
            defaults={
                "end_at": timezone.make_aware(
                    datetime.combine(day, time(23, 59)), tz
                ),
                "reason": "Demo leave day",
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready: {len(services)} services, "
                f"{len(stylists)} stylists."
            )
        )
        self.stdout.write(
            f"Users: demo_admin and demo_customer, password: {password}"
        )

    def create_user(self, username, phone_number, password, admin=False):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "phone_number": phone_number,
                "is_phone_verified": True,
                "role": User.Role.ADMIN if admin else User.Role.CUSTOMER,
                "is_staff": admin,
                "is_superuser": admin,
            },
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user
