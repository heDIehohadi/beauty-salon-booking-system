from django.contrib import admin

from .models import Services, ServicePortfolio


class ServicePortfolioInline(admin.TabularInline):
    model = ServicePortfolio
    extra = 1


@admin.register(Services)
class ServicesAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "price",
        "is_active",
        "created_at",
    )
    list_filter = ("category", "is_active")
    search_fields = ("name", "description")
    list_editable = ("price", "is_active")
    inlines = [ServicePortfolioInline]


@admin.register(ServicePortfolio)
class ServicePortfolioAdmin(admin.ModelAdmin):
    list_display = ("service", "caption", "created_at")
    list_filter = ("service",)
    search_fields = ("service__name", "caption")