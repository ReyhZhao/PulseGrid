from django.contrib import admin

from .models import ApiToken


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "is_active", "last_used_at", "created_at"]
    list_filter = ["organization", "is_active"]
    search_fields = ["name"]
    # The hash is the credential's only stored form; editing it here would
    # either lock the token out or install one nobody can produce.
    readonly_fields = ["token_hash", "last_used_at", "created_at"]
