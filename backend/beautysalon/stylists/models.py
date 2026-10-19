from django.db import models


class Stylist(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    bio = models.TextField(blank=True)
    profile_image = models.ImageField(
        upload_to="stylists/profiles/",
        blank=True,
        null=True,
    )
    services = models.ManyToManyField(
        "services.Services",
        related_name="stylists",
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class StylistPortfolio(models.Model):
    stylist = models.ForeignKey(
        Stylist,
        on_delete=models.CASCADE,
        related_name="portfolio",
    )
    image = models.ImageField(upload_to="stylists/portfolio/")
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Portfolio: {self.stylist}"