from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "event_type", "severity", "actor", "source_ip", "message"]
    list_filter = ["severity", "event_type", "actor_type"]
    search_fields = ["actor", "message", "source_ip"]
    date_hierarchy = "created_at"

    # The audit trail is immutable.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
