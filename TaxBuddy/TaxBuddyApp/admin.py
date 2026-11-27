from django.contrib import admin

# Register your models here.
# Paste at the END of TaxBuddyApp/admin.py

from django.db.models import Count, Sum
from .models import AIUsage


@admin.register(AIUsage)
class AIUsageAdmin(admin.ModelAdmin):
    """TaxBuddy Umair AI cost monitor. Read-only; totals for the filtered rows show at the top."""
    list_display = ("created", "endpoint", "status", "model", "input_tokens", "output_tokens",
                    "cache_read_tokens", "cost_usd", "latency_ms", "tools")
    list_filter = ("endpoint", "status", "model", "created")
    date_hierarchy = "created"
    search_fields = ("tools",)
    change_list_template = "admin/aiusage_change_list.html"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        resp = super().changelist_view(request, extra_context=extra_context)
        try:
            qs = resp.context_data["cl"].queryset
            resp.context_data["ai_totals"] = qs.aggregate(
                answers=Count("id"), cost=Sum("cost_usd"),
                inp=Sum("input_tokens"), out=Sum("output_tokens"),
                cread=Sum("cache_read_tokens"), cwrite=Sum("cache_write_tokens"))
        except (AttributeError, KeyError):
            pass
        return resp