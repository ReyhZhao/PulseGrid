from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Membership, Organization


class OrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "role"]

    def get_role(self, org):
        roles = self.context.get("roles", {})
        return roles.get(org.id)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ["id", "username", "email", "first_name", "last_name"]


class MeSerializer(serializers.Serializer):
    user = UserSerializer()
    organizations = OrganizationSerializer(many=True)


def me_payload(user):
    memberships = Membership.objects.filter(user=user).select_related("organization")
    roles = {m.organization_id: m.role for m in memberships}
    orgs = [m.organization for m in memberships]
    return MeSerializer(
        {"user": user, "organizations": orgs},
        context={"roles": roles},
    ).data
