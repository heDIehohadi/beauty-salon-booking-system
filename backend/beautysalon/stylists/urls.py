from django.urls import path

from .views import StylistDetailView, StylistListView

urlpatterns = [
    path("", StylistListView.as_view(), name="stylist-list"),
    path("<int:pk>/", StylistDetailView.as_view(), name="stylist-detail"),
]