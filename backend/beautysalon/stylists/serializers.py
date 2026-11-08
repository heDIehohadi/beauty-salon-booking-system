from rest_framework import serializers

from services.serializers import ServicesSerializer

from .models import (
    Stylist,
    StylistPortfolio,
    StylistWorkingHour,
)


class StylistPortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = StylistPortfolio
        fields = ("id", "image", "caption", "created_at")


class StylistWorkingHourSerializer(serializers.ModelSerializer):
    class Meta:
        model = StylistWorkingHour
        fields = ("id", "weekday", "start_time", "end_time")


class StylistListSerializer(serializers.ModelSerializer):
    services = ServicesSerializer(many=True, read_only=True)

    class Meta:
        model = Stylist
        fields = (
            "id",
            "first_name",
            "last_name",
            "bio",
            "profile_image",
            "services",
        )


class StylistDetailSerializer(StylistListSerializer):
    portfolio = StylistPortfolioSerializer(many=True, read_only=True)
    working_hours = StylistWorkingHourSerializer(many=True, read_only=True)


    class Meta(StylistListSerializer.Meta):
        fields = (
            *StylistListSerializer.Meta.fields,
            "portfolio",
            "working_hours",
        )