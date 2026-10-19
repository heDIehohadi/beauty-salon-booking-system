from rest_framework import serializers

from .models import Services, ServicePortfolio


class ServicePortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePortfolio
        fields = ("id", "image", "caption", "created_at")


class ServicesSerializer(serializers.ModelSerializer):
    portfolio = ServicePortfolioSerializer(many=True, read_only=True)

    class Meta:
        model = Services
        fields = (
            "id",
            "name",
            "category",
            "description",
            "price",
            "is_active",
            "portfolio",
            "created_at",
            "updated_at",
        )