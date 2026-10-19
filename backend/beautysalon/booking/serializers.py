from django.utils import timezone
from rest_framework import serializers

from services.models import Services
from stylists.models import Stylist
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

        if start_at <= timezone.now():
            raise serializers.ValidationError({
                "start_at": "Booking must be in the future."
            })

        if not stylist.services.filter(pk=service.pk).exists():
            raise serializers.ValidationError({
                "stylist": "This stylist does not provide this service."
            })

        end_at = start_at + timezone.timedelta(
            minutes=service.duration_minutes
        )

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