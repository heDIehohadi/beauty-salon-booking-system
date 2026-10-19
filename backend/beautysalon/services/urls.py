from django.urls import path

from .views import ServicesDetailView, ServicesListView

urlpatterns = [
    path("", ServicesListView.as_view(), name="services-list"),
    path("<int:pk>/", ServicesDetailView.as_view(), name="services-detail"),
]