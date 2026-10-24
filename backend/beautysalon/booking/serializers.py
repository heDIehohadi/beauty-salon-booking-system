from django.utils import timezone
from rest_framework import serializers

from services.models import Services
from stylists.models import Stylist, StylistWorkingHour
from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(read_only=True)

    service = serializers.PrimaryKeyRelatedField(
        queryset=Services.objects.filter(is_active=True)
    )

    stylist = serializers.PrimaryKeyRelatedField(
        queryset=Stylist.objects.filter(is_active=True)
    )

    class Meta:
        model = Booking
        fields = (
            "id",
            "customer",
            "service",
            "stylist",
            "start_at",
            "end_at",
            "status",
            "customer_note",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "customer",
            "end_at",
            "status",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        service = attrs["service"]
        stylist = attrs["stylist"]
        start_at = attrs["start_at"]

        # 1. Booking must be in the future.
        if start_at <= timezone.now():
            raise serializers.ValidationError({
                "start_at": "Booking must be in the future."
            })

        # 2. The stylist must provide this service.
        if not stylist.services.filter(pk=service.pk).exists():
            raise serializers.ValidationError({
                "stylist": "This stylist does not provide this service."
            })

        # 3. Calculate the booking end time.
        end_at = start_at + timezone.timedelta(
            minutes=service.duration_minutes
        )

        # 4. Convert timestamps to the current local timezone.
        local_start = timezone.localtime(start_at)
        local_end = timezone.localtime(end_at)

        # The current model does not support bookings
        # that cross midnight.
        if local_start.date() != local_end.date():
            raise serializers.ValidationError({
                "start_at": (
                    "The booking must fit within working hours "
                    "on a single day."
                )
            })

        # 5. Check the stylist's active working hours.
        weekday = local_start.weekday()
        start_time = local_start.time().replace(tzinfo=None)
        end_time = local_end.time().replace(tzinfo=None)

        has_working_hours = StylistWorkingHour.objects.filter(
            stylist=stylist,
            weekday=weekday,
            is_active=True,
            start_time__lte=start_time,
            end_time__gte=end_time,
        ).exists()

        if not has_working_hours:
            raise serializers.ValidationError({
                "start_at": (
                    "The booking must fit within the stylist's "
                    "working hours."
                )
            })

        # 6. Reject overlapping active bookings.
        overlapping_bookings = Booking.objects.filter(
            stylist=stylist,
            start_at__lt=end_at,
            end_at__gt=start_at,
            status__in=[
                Booking.Status.PENDING,
                Booking.Status.CONFIRMED,
            ],
        )

        if self.instance:
            overlapping_bookings = overlapping_bookings.exclude(
                pk=self.instance.pk
            )

        if overlapping_bookings.exists():
            raise serializers.ValidationError({
                "start_at": "This time overlaps with another booking."
            })

        attrs["end_at"] = end_at
        return attrs

    def create(self, validated_data):
        request = self.context["request"]

        return Booking.objects.create(
            customer=request.user,
            **validated_data,
        )