from django.contrib import admin

from .models import Worker


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ["name", "region", "is_active", "last_seen_at", "version"]
    list_filter = ["region", "is_active"]
