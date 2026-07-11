from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Membership, Organization, OrganizationInvitation, UserProfile


class OrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "role"]
        read_only_fields = ["slug"]

    def get_role(self, org):
        roles = self.context.get("roles", {})
        return roles.get(org.id)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ["id", "username", "email", "first_name", "last_name"]


class MeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ["first_name", "last_name"]


class MemberSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="user.id")
    username = serializers.CharField(source="user.username")
    email = serializers.EmailField(source="user.email")
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")

    class Meta:
        model = Membership
        fields = ["id", "username", "email", "first_name", "last_name", "role", "created_at"]


class InvitationSerializer(serializers.ModelSerializer):
    invited_by = serializers.CharField(source="invited_by.username", read_only=True, default="")

    class Meta:
        model = OrganizationInvitation
        fields = ["id", "email", "role", "invited_by", "created_at", "expires_at"]
        read_only_fields = ["created_at", "expires_at"]

    def validate_role(self, value):
        if value not in Membership.Role.values:
            raise serializers.ValidationError("Invalid role.")
        return value


def me_payload(user):
    memberships = Membership.objects.filter(user=user).select_related("organization")
    roles = {m.organization_id: m.role for m in memberships}
    orgs = [m.organization for m in memberships]
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return {
        "user": UserSerializer(user).data,
        "organizations": OrganizationSerializer(orgs, many=True, context={"roles": roles}).data,
        "onboarding_complete": profile.onboarded_at is not None,
    }
