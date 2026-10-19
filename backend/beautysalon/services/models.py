from django.db import models


class Services(models.Model):

    class Category(models.TextChoices):
        NAILS = "nails", "Nails"
        HAIR = "hair", "Hair"
        SKIN = "skin", "Skin"
        TATTOO = "tattoo", "Tattoo"

    name = models.CharField(max_length=100)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
    )
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class ServicePortfolio(models.Model):
    service = models.ForeignKey(
        Services,
        on_delete=models.CASCADE,
        related_name="portfolio",
    )
    image = models.ImageField(upload_to="services/portfolio/")
    caption = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    duration_minutes = models.PositiveSmallIntegerField(
    default=60,
    help_text="Service duration in minutes",
)

    def __str__(self):
        return f"Portfolio: {self.service.name}"    
    