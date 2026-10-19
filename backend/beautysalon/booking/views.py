from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from stylists.models import Stylist
from .models import Booking
from .serializers import BookingSerializer


class BookingListCreateView(generics.ListCreateAPIView):
    """
    GET: لیست رزروهای کاربر واردشده
    POST: ایجاد رزرو جدید
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Booking.objects
            .filter(customer=self.request.user)
            .select_related("customer", "service", "stylist")
            .order_by("-start_at")
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        # در پایگاه داده‌هایی مانند PostgreSQL، ردیف استایلیست
        # را قفل می‌کنیم تا بررسی رزرو در یک تراکنش انجام شود.
        stylist_id = request.data.get("stylist")

        try:
            stylist_id = int(stylist_id)
        except (TypeError, ValueError):
            # اگر شناسه نامعتبر باشد، اعتبارسنجی Serializer
            # پاسخ خطای مناسب را برمی‌گرداند.
            pass
        else:
            Stylist.objects.select_for_update().filter(
                pk=stylist_id,
                is_active=True,
            ).first()

        # اعتبارسنجی و ذخیره در محدوده همین تراکنش انجام می‌شوند.
        return super().create(request, *args, **kwargs)


class BookingDetailView(generics.RetrieveAPIView):
    """
    GET: مشاهده جزئیات یک رزرو متعلق به کاربر واردشده
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Booking.objects
            .filter(customer=self.request.user)
            .select_related("customer", "service", "stylist")
        )


class BookingCancelView(generics.GenericAPIView):
    """
    PATCH: لغو رزرو متعلق به کاربر واردشده
    """
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Booking.objects.filter(customer=self.request.user)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        booking = self.get_object()

        if booking.status in [
            Booking.Status.CANCELLED,
            Booking.Status.COMPLETED,
        ]:
            return Response(
                {
                    "detail": (
                        "This booking cannot be cancelled "
                        "because it is already cancelled or completed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])

        serializer = self.get_serializer(booking)

        return Response(serializer.data, status=status.HTTP_200_OK)