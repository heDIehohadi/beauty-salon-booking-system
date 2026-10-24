from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Stylist(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    profile_image = models.ImageField(
        upload_to="stylists/profiles/",
        blank=True,
        null=True,
    )
    services = models.ManyToManyField(
        "services.Services",
        related_name="stylists",
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class StylistPortfolio(models.Model):
    stylist = models.ForeignKey(
        Stylist,
        on_delete=models.CASCADE,
        related_name="portfolio",
    )
    image = models.ImageField(upload_to="stylists/portfolio/")
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Portfolio: {self.stylist}"


class StylistWorkingHour(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    stylist = models.ForeignKey(
        Stylist,
        on_delete=models.CASCADE,
        related_name="working_hours",
    )
    weekday = models.IntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["stylist", "weekday", "start_time"],
                name="unique_stylist_working_hour",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="working_hour_end_after_start",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValidationError({
                "end_time": "End time must be later than start time."
            })

        if (
            not self.is_active
            or not self.stylist_id
            or self.weekday is None
            or self.start_time is None
            or self.end_time is None
            or self.end_time <= self.start_time
        ):
            return

        overlapping_hours = StylistWorkingHour.objects.filter(
            stylist_id=self.stylist_id,
            weekday=self.weekday,
            is_active=True,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        )

        if self.pk:
            overlapping_hours = overlapping_hours.exclude(pk=self.pk)

        if overlapping_hours.exists():
            raise ValidationError(
                "This working hour overlaps with another active working hour."
            )

    def __str__(self):
        return (
            f"{self.stylist} - {self.get_weekday_display()} "
            f"{self.start_time}-{self.end_time}"
        )
