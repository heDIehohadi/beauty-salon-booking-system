from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Stylist
from .serializers import (
    StylistDetailSerializer,
    StylistListSerializer,
)


class StylistListView(generics.ListAPIView):
    serializer_class = StylistListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return (
            Stylist.objects.filter(is_active=True)
            .prefetch_related("services")
        )


class StylistDetailView(generics.RetrieveAPIView):
    serializer_class = StylistDetailSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return (
            Stylist.objects.filter(is_active=True)
            .prefetch_related(
                "services",
                "portfolio",
                "working_hours",
            )
        )