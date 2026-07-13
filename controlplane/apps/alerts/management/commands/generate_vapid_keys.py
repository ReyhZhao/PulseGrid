"""Generate a VAPID key pair for web push notifications.

Run once per deployment and put the two values into the environment
(secret store). The public key is also handed to browsers, so it is not
sensitive; the private key is.
"""

import base64

from cryptography.hazmat.primitives import serialization
from django.core.management.base import BaseCommand
from py_vapid import Vapid


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class Command(BaseCommand):
    help = "Generate a VAPID key pair (set the output as environment variables)."

    def handle(self, *args, **options):
        vapid = Vapid()
        vapid.generate_keys()
        public = vapid.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        private = vapid.private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.stdout.write(f"VAPID_PUBLIC_KEY={_b64url(public)}")
        self.stdout.write(f"VAPID_PRIVATE_KEY={_b64url(private)}")
        self.stdout.write("VAPID_SUBJECT=mailto:ops@your-domain.example")
