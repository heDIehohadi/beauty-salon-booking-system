from django.db.models import Prefetch
from rest_framework import generics
from rest_framework.permissions import AllowAny

from services.models import Services

from .models import Stylist, StylistWorkingHour
from .serializers import (
    StylistDetailSerializer,
    StylistListSerializer,
)


def active_services_prefetch():
    # فقط سرویس‌های فعال نمایش داده شوند (سرویس غیرفعال قابل رزرو نیست)
    # و portfolio هر سرویس هم یک‌جا لود شود تا N+1 ایجاد نشود.
    return Prefetch(
        "services",
        queryset=Services.objects.filter(is_active=True).prefetch_related(
            "portfolio"
        ),
    )


class StylistListView(generics.ListAPIView):
    serializer_class = StylistListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Stylist.objects.filter(is_active=True).prefetch_related(
            active_services_prefetch()
        )


class StylistDetailView(generics.RetrieveAPIView):
    serializer_class = StylistDetailSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Stylist.objects.filter(is_active=True).prefetch_related(
            active_services_prefetch(),
            "portfolio",
            # ساعت کاری غیرفعال نباید به مشتری نشان داده شود؛
            # AvailableSlotsView هم فقط ساعت‌های is_active=True را می‌بیند.
            Prefetch(
                "working_hours",
                queryset=StylistWorkingHour.objects.filter(is_active=True),
            ),
        )
