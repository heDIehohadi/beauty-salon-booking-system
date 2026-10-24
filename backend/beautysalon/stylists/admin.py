from django.contrib import admin
from .models import Stylist, StylistPortfolio, StylistWorkingHour


class StylistPortfolioInline(admin.TabularInline):
    model = StylistPortfolio
    extra = 1


@admin.register(Stylist)
class StylistAdmin(admin.ModelAdmin):
    list_display = (
        "first_name",
        "last_name",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("first_name", "last_name")
    list_editable = ("is_active",)
    filter_horizontal = ("services",)
    inlines = [StylistPortfolioInline]


@admin.register(StylistPortfolio)
class StylistPortfolioAdmin(admin.ModelAdmin):
    list_display = ("stylist", "caption", "created_at")
    search_fields = (
        "stylist__first_name",
        "stylist__last_name",
        "caption",
    )
@admin.register(StylistWorkingHour)
class StylistWorkingHourAdmin(admin.ModelAdmin):
    list_display = (
        "stylist",
        "weekday",
        "start_time",
        "end_time",
        "is_active",
    )
    list_filter = ("weekday", "is_active", "stylist")
    list_select_related = ("stylist",)    