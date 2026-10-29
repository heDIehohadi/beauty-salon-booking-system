from datetime import date, datetime, timedelta

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from services.models import Services
from stylists.models import Stylist, StylistTimeOff, StylistWorkingHour

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

class AvailableSlotsView(generics.GenericAPIView):
    """
    GET: نمایش زمان‌های شروع آزاد برای یک آرایشگر، سرویس و تاریخ.
    مثال:
    /api/bookings/available-slots/?stylist=3&service=2&date=2026-10-27
    فاصلهٔ زمان‌های شروع: ۱۵ دقیقه
    مدت هر نوبت: بر اساس مدت سرویس
    """
    permission_classes = [IsAuthenticated]

    SLOT_INTERVAL_MINUTES = 15

    def get(self, request, *args, **kwargs):
        stylist_id = request.query_params.get("stylist")
        service_id = request.query_params.get("service")
        date_value = request.query_params.get("date")

        if not stylist_id or not service_id or not date_value:
            return Response(
                {
                    "detail": (
                        "Parameters stylist, service and date are required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            stylist_id = int(stylist_id)
            service_id = int(service_id)
            requested_date = date.fromisoformat(date_value)
        except (TypeError, ValueError):
            return Response(
                {
                    "detail": (
                        "stylist and service must be integer IDs, "
                        "and date must use YYYY-MM-DD format."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        stylist = get_object_or_404(
            Stylist,
            pk=stylist_id,
            is_active=True,
        )
        service = get_object_or_404(
            Services,
            pk=service_id,
            is_active=True,
        )

        if not stylist.services.filter(pk=service.pk).exists():
            return Response(
                {
                    "detail": (
                        "This stylist does not offer the selected service."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        duration = service.duration_minutes

        if duration <= 0:
            return Response(
                {"detail": "Service duration must be greater than zero."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        current_tz = timezone.get_current_timezone()
        now = timezone.localtime(timezone.now(), current_tz)

        if requested_date < now.date():
            return Response(
                {"detail": "Cannot search for slots in the past."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        weekday = requested_date.weekday()

        working_hours = StylistWorkingHour.objects.filter(
            stylist=stylist,
            weekday=weekday,
            is_active=True,
        ).order_by("start_time")

        available_slots = []

        for working_hour in working_hours:
            work_start = datetime.combine(
                requested_date,
                working_hour.start_time,
            )
            work_end = datetime.combine(
                requested_date,
                working_hour.end_time,
            )

            # زمان شروع را با فاصلهٔ ۱۵ دقیقه‌ای جلو می‌بریم.
            slot_start = work_start

            while slot_start + timedelta(minutes=duration) <= work_end:
                slot_end = slot_start + timedelta(minutes=duration)

                aware_start = timezone.make_aware(
                    slot_start,
                    current_tz,
                )
                aware_end = timezone.make_aware(
                    slot_end,
                    current_tz,
                )

                # زمان‌های گذشته نباید پیشنهاد شوند.
                if aware_start <= now:
                    slot_start += timedelta(
                        minutes=self.SLOT_INTERVAL_MINUTES
                    )
                    continue

                # بررسی تداخل با رزروهای فعال.
                overlapping_booking = Booking.objects.filter(
                    stylist=stylist,
                    status__in=[
                        Booking.Status.PENDING,
                        Booking.Status.CONFIRMED,
                    ],
                    start_at__lt=aware_end,
                    end_at__gt=aware_start,
                ).exists()

                # بررسی تداخل با استراحت یا مرخصی فعال آرایشگر.
                overlapping_time_off = StylistTimeOff.objects.filter(
                    stylist=stylist,
                    is_active=True,
                    start_at__lt=aware_end,
                    end_at__gt=aware_start,
                ).exists()

                # فقط نوبتی پیشنهاد می‌شود که با هیچ‌کدام تداخل نداشته باشد.
                if not overlapping_booking and not overlapping_time_off:
                    available_slots.append(
                        {
                            "start_at": aware_start.isoformat(),
                            "end_at": aware_end.isoformat(),
                        }
                    )

                slot_start += timedelta(
                    minutes=self.SLOT_INTERVAL_MINUTES
                )

        return Response(
            {
                "stylist": stylist.pk,
                "service": service.pk,
                "date": requested_date.isoformat(),
                "timezone": str(current_tz),
                "slot_interval_minutes": self.SLOT_INTERVAL_MINUTES,
                "service_duration_minutes": duration,
                "available_slots": available_slots,
            },
            status=status.HTTP_200_OK,
        )
