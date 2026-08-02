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

    def has_add_permission(self, request):
        # Issuing a token means returning the plaintext exactly once, which an
        # admin change form cannot do — saving here would only produce a row
        # with an empty hash that nobody can authenticate against. Tokens are
        # issued with `manage.py create_api_token`; this page revokes them
        # (clear `is_active`) and shows when they were last used.
        return False
