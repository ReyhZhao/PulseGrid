from django.conf import settings
from django.core.mail import send_mail
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import Severity
from apps.audit.services import record as audit

from .models import Membership, Organization, OrganizationInvitation, UserProfile
from .permissions import user_organization_ids
from .serializers import (
    InvitationSerializer,
    MemberSerializer,
    MeUpdateSerializer,
    OrganizationSerializer,
    me_payload,
)


class MeView(APIView):
    def get(self, request):
        return Response(me_payload(request.user))

    def patch(self, request):
        serializer = MeUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(me_payload(request.user))


class OnboardingCompleteView(APIView):
    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.onboarded_at is None:
            profile.onboarded_at = timezone.now()
            profile.save(update_fields=["onboarded_at"])
            audit("user.onboarded", f"User '{request.user.get_username()}' completed onboarding",
                  request=request)
        return Response(me_payload(request.user))


class CsrfView(APIView):
    """Hands the SPA a CSRF token. get_token() both marks the csrftoken
    cookie for (re)setting and returns the value, so clients that cannot
    read the cookie (races, exotic cookie policies) can fall back to the
    response body."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrftoken": get_token(request)})


class OrganizationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    """Org self-service: rename (owners), member management, invitations."""

    serializer_class = OrganizationSerializer

    def get_queryset(self):
        return Organization.objects.filter(id__in=user_organization_ids(self.request.user))

    def get_serializer_context(self):
        context = super().get_serializer_context()
        memberships = Membership.objects.filter(user=self.request.user)
        context["roles"] = {m.organization_id: m.role for m in memberships}
        return context

    def _require_owner(self, org):
        is_owner = Membership.objects.filter(
            organization=org, user=self.request.user, role=Membership.Role.OWNER
        ).exists()
        if not is_owner:
            raise PermissionDenied("Only organization owners can do this.")

    def perform_update(self, serializer):
        org = self.get_object()
        self._require_owner(org)
        old_name = org.name
        org = serializer.save()
        if org.name != old_name:
            audit(
                "org.renamed",
                f"Organization renamed from '{old_name}' to '{org.name}'",
                request=self.request,
                organization=org,
            )

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        org = self.get_object()
        memberships = org.memberships.select_related("user").order_by("created_at")
        return Response(MemberSerializer(memberships, many=True).data)

    @action(detail=True, methods=["delete"], url_path="members/(?P<user_id>[0-9]+)")
    def remove_member(self, request, pk=None, user_id=None):
        org = self.get_object()
        self._require_owner(org)
        try:
            membership = org.memberships.select_related("user").get(user_id=user_id)
        except Membership.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        owners = org.memberships.filter(role=Membership.Role.OWNER)
        if membership.role == Membership.Role.OWNER and owners.count() <= 1:
            return Response(
                {"detail": "Cannot remove the last owner of an organization."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        removed_username = membership.user.get_username()
        membership.delete()
        audit(
            "org.member_removed",
            f"'{removed_username}' was removed from organization '{org.name}'",
            severity=Severity.MEDIUM,
            request=request,
            organization=org,
            removed_user=removed_username,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def invitations(self, request, pk=None):
        org = self.get_object()
        self._require_owner(org)
        pending = [inv for inv in org.invitations.all() if inv.is_pending()]
        return Response(InvitationSerializer(pending, many=True).data)

    @action(detail=True, methods=["post"])
    def invite(self, request, pk=None):
        org = self.get_object()
        self._require_owner(org)
        serializer = InvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        already_member = Membership.objects.filter(organization=org, user__email__iexact=email).exists()
        if already_member:
            return Response(
                {"email": ["A user with this email is already a member."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitation = serializer.save(organization=org, invited_by=request.user)
        _send_invitation_email(invitation)
        audit(
            "org.member_invited",
            f"'{email}' was invited to organization '{org.name}' as {invitation.role}",
            severity=Severity.MEDIUM,
            request=request,
            organization=org,
            invited_email=email,
            role=invitation.role,
        )
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path="invitations/(?P<invitation_id>[0-9]+)")
    def revoke_invitation(self, request, pk=None, invitation_id=None):
        org = self.get_object()
        self._require_owner(org)
        try:
            invitation = org.invitations.get(pk=invitation_id, accepted_at__isnull=True)
        except OrganizationInvitation.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        audit(
            "org.invitation_revoked",
            f"Invitation for '{invitation.email}' to '{org.name}' was revoked",
            request=request,
            organization=org,
            invited_email=invitation.email,
        )
        invitation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AcceptInvitationView(APIView):
    def post(self, request):
        token = str(request.data.get("token", ""))
        invitation = (
            OrganizationInvitation.objects.select_related("organization").filter(token=token).first()
        )
        if invitation is None or not invitation.is_pending():
            return Response(
                {"detail": "This invitation is invalid, expired or already used."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        org = invitation.organization
        _membership, created = Membership.objects.get_or_create(
            organization=org, user=request.user, defaults={"role": invitation.role}
        )
        invitation.accepted_at = timezone.now()
        invitation.accepted_by = request.user
        invitation.save(update_fields=["accepted_at", "accepted_by"])
        if created:
            audit(
                "org.member_joined",
                f"'{request.user.get_username()}' joined organization '{org.name}' as {invitation.role}",
                severity=Severity.MEDIUM,
                request=request,
                organization=org,
                role=invitation.role,
            )
        return Response(
            {
                "organization": OrganizationSerializer(
                    org, context={"roles": {org.id: invitation.role}}
                ).data,
                "joined": created,
            }
        )


def _send_invitation_email(invitation: OrganizationInvitation) -> None:
    link = f"{settings.PULSEGRID_FRONTEND_URL}/invite/{invitation.token}"
    inviter = invitation.invited_by.get_username() if invitation.invited_by else "An administrator"
    send_mail(
        f"[PulseGrid] You have been invited to {invitation.organization.name}",
        (
            f"{inviter} invited you to join the organization "
            f"'{invitation.organization.name}' on PulseGrid as {invitation.role}.\n\n"
            f"Accept the invitation: {link}\n\n"
            f"This link expires on {invitation.expires_at:%Y-%m-%d %H:%M} UTC."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [invitation.email],
    )
