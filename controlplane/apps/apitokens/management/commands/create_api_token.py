import uuid

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Organization
from apps.apitokens.models import ApiToken


class Command(BaseCommand):
    help = (
        "Issue a read-only, organization-scoped API token. The token is printed "
        "once; store it safely."
    )

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="Token name, e.g. 'polaris-status-page'")
        parser.add_argument("--organization", required=True, help="Organization slug or UUID")

    def handle(self, *args, **options):
        org = self._resolve_organization(options["organization"])
        api_token, plaintext = ApiToken.issue(options["name"], org)

        from apps.audit.models import Severity
        from apps.audit.services import record as audit

        audit(
            "api_token.created",
            f"Read-only API token issued for '{api_token.name}' in organization '{org.slug}'",
            severity=Severity.HIGH,
            actor="cli",
            actor_type="system",
            organization=org,
            api_token_id=api_token.id,
        )

        self.stdout.write(f"Read-only API token '{api_token.name}' created for '{org.slug}'.")
        self.stdout.write(f"PULSEGRID_API_TOKEN={plaintext}")

    @staticmethod
    def _resolve_organization(value: str) -> Organization:
        org = Organization.objects.filter(slug=value).first()
        if org is None:
            try:
                org = Organization.objects.filter(pk=uuid.UUID(value)).first()
            except ValueError:
                org = None
        if org is None:
            slugs = ", ".join(Organization.objects.values_list("slug", flat=True)[:20]) or "(none)"
            raise CommandError(
                f"Unknown organization '{value}'. Pass a slug or UUID. Known slugs: {slugs}."
            )
        return org
