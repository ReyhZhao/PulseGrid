from rest_framework import serializers

from .models import ApiToken


class ApiTokenSerializer(serializers.ModelSerializer):
    """An issued token as seen by its organization. The plaintext is never a
    field here — it exists only in the create response, once."""

    class Meta:
        model = ApiToken
        fields = ["id", "name", "is_active", "last_used_at", "created_at"]
        read_only_fields = ["is_active", "last_used_at", "created_at"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Give the token a name so you can tell them apart.")
        return value


class ApiTokenCreatedSerializer(ApiTokenSerializer):
    """Create response: the issued token plus its plaintext, shown once."""

    token = serializers.CharField(read_only=True, help_text="Shown exactly once, at issue time.")

    class Meta(ApiTokenSerializer.Meta):
        fields = [*ApiTokenSerializer.Meta.fields, "token"]
