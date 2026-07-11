from django.contrib import admin

from .models import Membership, Organization, OrganizationInvitation, UserProfile


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "created_at"]
    search_fields = ["name", "slug"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "organization", "role"]
    list_filter = ["role"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "onboarded_at"]


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "organization", "role", "invited_by", "created_at", "accepted_at"]
    list_filter = ["role"]
    search_fields = ["email"]
