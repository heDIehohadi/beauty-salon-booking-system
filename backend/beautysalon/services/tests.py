from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from services.models import Services


class ServicesAPITests(APITestCase):
    def setUp(self):
        self.hair = Services.objects.create(
            name="Haircut",
            category=Services.Category.HAIR,
            price="25.00",
            duration_minutes=45,
            is_active=True,
        )
        self.nails = Services.objects.create(
            name="Manicure",
            category=Services.Category.NAILS,
            price="30.00",
            duration_minutes=60,
            is_active=True,
        )
        self.inactive = Services.objects.create(
            name="Retired Service",
            category=Services.Category.HAIR,
            price="10.00",
            is_active=False,
        )

    def test_list_is_public_and_hides_inactive_services(self):
        response = self.client.get(reverse("services-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data}
        self.assertEqual(ids, {self.hair.pk, self.nails.pk})

    def test_list_can_be_filtered_by_category(self):
        response = self.client.get(
            reverse("services-list"), {"category": "nails"}
        )

        ids = [item["id"] for item in response.data]
        self.assertEqual(ids, [self.nails.pk])

    def test_unknown_category_returns_empty_list(self):
        response = self.client.get(
            reverse("services-list"), {"category": "does-not-exist"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_detail_returns_service(self):
        response = self.client.get(
            reverse("services-detail", args=[self.hair.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Haircut")
        self.assertEqual(response.data["price"], "25.00")

    def test_detail_of_inactive_service_is_404(self):
        response = self.client.get(
            reverse("services-detail", args=[self.inactive.pk])
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_services_endpoints_are_read_only(self):
        payload = {"name": "X", "category": "hair", "price": "1.00"}

        create = self.client.post(reverse("services-list"), payload)
        update = self.client.put(
            reverse("services-detail", args=[self.hair.pk]), payload
        )
        delete = self.client.delete(
            reverse("services-detail", args=[self.hair.pk])
        )

        self.assertEqual(create.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(update.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(delete.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Services.objects.filter(pk=self.hair.pk).exists())
