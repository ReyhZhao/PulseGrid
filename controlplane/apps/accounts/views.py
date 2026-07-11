import logging

from django.conf import settings
from django.core.mail import send_mail
from django.middleware.csrf import get_token
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import Severity
from apps.audit.services import record as audit

from . import authentik
from .models import Membership, Organization, OrganizationInvitation, UserProfile
from .permissions import user_organization_ids
from .serializers import (
    AcceptInvitationRequestSerializer,
    AcceptInvitationResponseSerializer,
    CsrfSerializer,
    InvitationSerializer,
    MemberSerializer,
    MePayloadSerializer,
    MeUpdateSerializer,
    OrganizationSerializer,
    me_payload,
)


@extend_schema_view(
    get=extend_schema(
        summary="Current user and organizations",
        tags=["account"],
        responses=MePayloadSerializer,
    ),
    patch=extend_schema(
        summary="Update current user's profile",
        tags=["account"],
        request=MeUpdateSerializer,
        responses=MePayloadSerializer,
    ),
)
class MeView(APIView):
    def get(self, request):
        return Response(me_payload(request.user))

    def patch(self, request):
        serializer = MeUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(me_payload(request.user))


@extend_schema(
    summary="Mark onboarding as complete",
    tags=["account"],
    request=None,
    responses=MePayloadSerializer,
)
class OnboardingCompleteView(APIView):
    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.onboarded_at is None:
            profile.onboarded_at = timezone.now()
            profile.save(update_fields=["onboarded_at"])
            audit("user.onboarded", f"User '{request.user.get_username()}' completed onboarding",
                  request=request)
        return Response(me_payload(request.user))


@extend_schema(
    summary="Fetch a CSRF token",
    tags=["account"],
    responses=CsrfSerializer,
)
class CsrfView(APIView):
    """Hands the SPA a CSRF token. get_token() both marks the csrftoken
    cookie for (re)setting and returns the value, so clients that cannot
    read the cookie (races, exotic cookie policies) can fall back to the
    response body."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrftoken": get_token(request)})


@extend_schema(
    summary="Authentication options for this deployment",
    tags=["account"],
    responses=None,
)
class AuthConfigView(APIView):
    """Tells the (anonymous) login page which sign-in and sign-up options
    this deployment offers, so the UI never shows dead buttons."""

    permission_classes = [AllowAny]

    def get(self, request):
        ak = settings.PULSEGRID_AUTHENTIK
        signup_url = None
        if ak["PUBLIC_URL"] and ak["SIGNUP_FLOW"]:
            signup_url = f"{ak['PUBLIC_URL']}/if/flow/{ak['SIGNUP_FLOW']}/"
        return Response(
            {
                # local username/password signup (allauth headless)
                "signup_enabled": settings.PULSEGRID_ALLOW_SIGNUP,
                # "Sign in with Authentik" button
                "authentik_enabled": bool(settings.SOCIALACCOUNT_PROVIDERS),
                # "Create account" link to a public Authentik enrollment flow
                "authentik_signup_url": signup_url,
            }
        )


@extend_schema(tags=["organizations"])
class OrganizationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    """Org self-service: rename (owners), member management, invitations."""

    serializer_class = OrganizationSerializer
    queryset = Organization.objects.none()

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

    @extend_schema(summary="List organization members", responses=MemberSerializer(many=True))
    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        org = self.get_object()
        memberships = org.memberships.select_related("user").order_by("created_at")
        return Response(MemberSerializer(memberships, many=True).data)

    @extend_schema(summary="Remove a member (owners only)", responses={204: None})
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

    @extend_schema(
        summary="List pending invitations (owners only)", responses=InvitationSerializer(many=True)
    )
    @action(detail=True, methods=["get"])
    def invitations(self, request, pk=None):
        org = self.get_object()
        self._require_owner(org)
        pending = [inv for inv in org.invitations.all() if inv.is_pending()]
        return Response(InvitationSerializer(pending, many=True).data)

    @extend_schema(
        summary="Invite a user (owners only)",
        request=InvitationSerializer,
        responses={201: InvitationSerializer},
    )
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

        # On-demand IDP provisioning: users unknown to Authentik get an
        # enrollment link. Best-effort — the invite works without it.
        enrollment_url = None
        if authentik.is_enabled():
            try:
                enrollment_url = authentik.create_enrollment_link(email, invitation)
            except Exception:
                logging.getLogger(__name__).exception(
                    "Authentik provisioning for '%s' failed; sending plain invite", email
                )

        _send_invitation_email(invitation, enrollment_url)
        audit(
            "org.member_invited",
            f"'{email}' was invited to organization '{org.name}' as {invitation.role}",
            severity=Severity.MEDIUM,
            request=request,
            organization=org,
            invited_email=email,
            role=invitation.role,
            authentik_enrollment=bool(enrollment_url),
        )
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Revoke a pending invitation (owners only)", responses={204: None})
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


@extend_schema(
    summary="Accept an organization invitation",
    tags=["organizations"],
    request=AcceptInvitationRequestSerializer,
    responses=AcceptInvitationResponseSerializer,
)
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


def _send_invitation_email(invitation: OrganizationInvitation, enrollment_url: str | None = None) -> None:
    link = f"{settings.PULSEGRID_FRONTEND_URL}/invite/{invitation.token}"
    inviter = invitation.invited_by.get_username() if invitation.invited_by else "An administrator"
    if enrollment_url:
        steps = (
            f"You don't have an account yet — set one up first:\n"
            f"  1. Create your account: {enrollment_url}\n"
            f"  2. You'll be taken to the invitation automatically "
            f"(or open it yourself: {link})"
        )
    else:
        steps = f"Accept the invitation: {link}"
    send_mail(
        f"[PulseGrid] You have been invited to {invitation.organization.name}",
        (
            f"{inviter} invited you to join the organization "
            f"'{invitation.organization.name}' on PulseGrid as {invitation.role}.\n\n"
            f"{steps}\n\n"
            f"This invitation expires on {invitation.expires_at:%Y-%m-%d %H:%M} UTC."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [invitation.email],
    )
