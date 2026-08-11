# ════════════════════════════════════════════════════════════════
#  ADD to TaxBuddyApp/admin.py  (lets you add future notifications /
#  edit rates & rules without touching code).
# ════════════════════════════════════════════════════════════════
from django.contrib import admin
from .models import PropertyFMVRateVersion, PropertyFMVArea, PropertyFMVRule


@admin.register(PropertyFMVRateVersion)
class PropertyFMVRateVersionAdmin(admin.ModelAdmin):
    list_display = ('version_name', 'city', 'notification_number', 'amendment_number',
                    'effective_from', 'status', 'is_active')
    list_filter = ('city', 'status', 'is_active')
    search_fields = ('version_name', 'notification_number', 'amendment_number')


@admin.register(PropertyFMVArea)
class PropertyFMVAreaAdmin(admin.ModelAdmin):
    list_display = ('fbr_no', 'area_name', 'version', 'residential_open_rate',
                    'commercial_open_rate', 'flat_rate', 'is_dha', 'is_flagged')
    list_filter = ('version', 'city', 'is_dha', 'is_flagged')
    search_fields = ('area_name', 'fbr_no')
    list_select_related = ('version',)
    ordering = ('version', 'fbr_no')


@admin.register(PropertyFMVRule)
class PropertyFMVRuleAdmin(admin.ModelAdmin):
    list_display = ('rule_code', 'rule_name', 'property_type', 'min_age', 'max_age',
                    'adjustment_type', 'adjustment_percentage', 'is_active')
    list_filter = ('property_type', 'adjustment_type', 'is_active', 'version')
    search_fields = ('rule_code', 'rule_name', 'description')
