from rest_framework import generics
from rest_framework.permissions import AllowAny

from .models import Services
from .serializers import ServicesSerializer


class ServicesListView(generics.ListAPIView):
    serializer_class = ServicesSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Services.objects.filter(is_active=True)
        category = self.request.query_params.get("category")

        if category:
            queryset = queryset.filter(category=category)

        return queryset


class ServicesDetailView(generics.RetrieveAPIView):
    serializer_class = ServicesSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Services.objects.filter(is_active=True)