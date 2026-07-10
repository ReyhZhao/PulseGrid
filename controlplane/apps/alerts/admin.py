from django.contrib import admin

from .models import AlertEvent, NotificationChannel, NotificationLog


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "channel_type", "is_active"]
    list_filter = ["channel_type", "is_active"]


@admin.register(AlertEvent)
class AlertEventAdmin(admin.ModelAdmin):
    list_display = ["summary", "monitor", "event_type", "status", "opened_at", "resolved_at"]
    list_filter = ["event_type", "status"]


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ["event", "channel", "kind", "status", "created_at"]
    list_filter = ["status", "kind"]
