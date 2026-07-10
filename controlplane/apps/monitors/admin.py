from django.contrib import admin

from .models import CheckResult, Monitor, MonitorRegionState, Region


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "is_active"]


@admin.register(Monitor)
class MonitorAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "monitor_type", "status", "interval_seconds", "is_paused"]
    list_filter = ["monitor_type", "status", "is_paused"]
    search_fields = ["name", "url", "host"]


@admin.register(MonitorRegionState)
class MonitorRegionStateAdmin(admin.ModelAdmin):
    list_display = ["monitor", "region_code", "status", "consecutive_failures", "last_check_at"]
    list_filter = ["status", "region_code"]


@admin.register(CheckResult)
class CheckResultAdmin(admin.ModelAdmin):
    list_display = ["monitor", "region_code", "ok", "latency_ms", "status_code", "checked_at"]
    list_filter = ["ok", "region_code"]
    date_hierarchy = "checked_at"
