from django.urls import path

from .views import (
    AvailableSlotsView,
    BookingCancelView,
    BookingDetailView,
    BookingListCreateView,
)

urlpatterns = [
    path(
        "",
        BookingListCreateView.as_view(),
        name="booking-list-create",
    ),
    path(
        "available-slots/",
        AvailableSlotsView.as_view(),
        name="available-slots",
    ),
    path(
        "<int:pk>/",
        BookingDetailView.as_view(),
        name="booking-detail",
    ),
    path(
        "<int:pk>/cancel/",
        BookingCancelView.as_view(),
        name="booking-cancel",
    ),
]