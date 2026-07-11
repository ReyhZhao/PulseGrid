from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify
from rest_framework import serializers

from apps.accounts.models import Membership, Organization
from apps.monitors.models import Region
from apps.workerapi.models import Worker


def unique_org_slug(name: str) -> str:
    base = slugify(name) or "org"
    slug = base
    suffix = 1
    while Organization.objects.filter(slug=slug).exists():
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


class AdminRegionSerializer(serializers.ModelSerializer):
    worker_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Region
        fields = ["id", "code", "name", "is_active", "worker_count"]

    def validate_code(self, value):
        # Monitors reference regions by code (JSON region lists) and check
        # queues are keyed by code, so renaming one would orphan them.
        if self.instance and value != self.instance.code:
            raise serializers.ValidationError(
                "Region codes are immutable. Create a new region and migrate workers instead."
            )
        return value


class AdminWorkerSerializer(serializers.ModelSerializer):
    region = serializers.SlugRelatedField(slug_field="code", queryset=Region.objects.all())

    class Meta:
        model = Worker
        fields = ["id", "name", "region", "is_active", "last_seen_at", "version", "created_at"]
        read_only_fields = ["last_seen_at", "version", "created_at"]


class AdminWorkerCreatedSerializer(AdminWorkerSerializer):
    """Creation/rotation response: includes the plaintext token exactly once."""

    token = serializers.CharField(read_only=True)

    class Meta(AdminWorkerSerializer.Meta):
        fields = AdminWorkerSerializer.Meta.fields + ["token"]


class AdminOrganizationSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)
    monitor_count = serializers.IntegerField(read_only=True)
    # Only owners can invite members, so a new org needs an initial owner
    # to be usable. Accepted on create only.
    owner_username = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "is_active",
            "created_at",
            "member_count",
            "monitor_count",
            "owner_username",
        ]
        read_only_fields = ["slug", "is_active", "created_at"]

    def validate_owner_username(self, value):
        if not value:
            return None
        try:
            return get_user_model().objects.get(username=value)
        except get_user_model().DoesNotExist:
            raise serializers.ValidationError("No user with this username.") from None

    def update(self, instance, validated_data):
        validated_data.pop("owner_username", None)
        return super().update(instance, validated_data)

    def create(self, validated_data):
        owner = validated_data.pop("owner_username", None)
        validated_data["slug"] = unique_org_slug(validated_data["name"])
        org = super().create(validated_data)
        if owner:
            Membership.objects.create(organization=org, user=owner, role=Membership.Role.OWNER)
        return org


class AdminUserSerializer(serializers.ModelSerializer):
    organizations = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
            "organizations",
        ]
        read_only_fields = ["is_superuser", "date_joined", "last_login"]

    def get_organizations(self, user) -> list[dict]:
        return [
            {
                "id": str(m.organization.id),
                "name": m.organization.name,
                "slug": m.organization.slug,
                "role": m.role,
            }
            for m in user.memberships.all()
        ]

    def validate_is_staff(self, value):
        request = self.context["request"]
        current = self.instance.is_staff if self.instance else False
        if value != current and not request.user.is_superuser:
            raise serializers.ValidationError("Only superusers can change staff status.")
        return value


class AdminUserCreateSerializer(AdminUserSerializer):
    password = serializers.CharField(write_only=True)

    class Meta(AdminUserSerializer.Meta):
        fields = AdminUserSerializer.Meta.fields + ["password"]

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = get_user_model().objects.create_user(password=password, **validated_data)
        return user


class SetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        # `user` enables the attribute-similarity validator for the target.
        validate_password(value, user=self.context.get("user"))
        return value


class OrgActiveStateSerializer(serializers.Serializer):
    """Response of the org disable/enable actions."""

    is_active = serializers.BooleanField()


# --- documentation-only response shapes ----------------------------------


class PlatformStatsSerializer(serializers.Serializer):
    """Response shape of `/api/v1/admin/stats` (documentation only)."""

    users = serializers.DictField(child=serializers.IntegerField())
    organizations = serializers.DictField(child=serializers.IntegerField())
    monitors = serializers.DictField(child=serializers.IntegerField())
    workers = serializers.DictField(child=serializers.IntegerField())
    regions = serializers.DictField(child=serializers.IntegerField())
    checks_24h = serializers.DictField(child=serializers.IntegerField())
    alerts = serializers.DictField(child=serializers.IntegerField())
    audit_24h = serializers.DictField(child=serializers.IntegerField())


class AuditSummarySerializer(serializers.Serializer):
    """Response shape of `/api/v1/admin/audit/summary/` (documentation only)."""

    days = serializers.IntegerField()
    total = serializers.IntegerField()
    by_severity = serializers.DictField(child=serializers.IntegerField())
    by_event_type = serializers.DictField(child=serializers.IntegerField())
    by_day = serializers.ListField(child=serializers.DictField())
