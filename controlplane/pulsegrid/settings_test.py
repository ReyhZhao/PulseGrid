"""Settings used by the test suite: sqlite, fast hashing, locmem email."""

import os

# settings.py now fails closed when DJANGO_SECRET_KEY is unset and DEBUG is off
# (the test default). Provide a throwaway key before importing it so the suite
# runs without leaning on the production fail-open path.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-insecure-secret-key")

from .settings import *  # noqa: E402,F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Keep the SSRF guard off by default so monitor/webhook fixtures using public
# example.com hostnames don't hit real DNS; the guard's own tests flip it on
# with override_settings and a patched resolver.
PULSEGRID_BLOCK_PRIVATE_TARGETS = False

# Production transport hardening (DEBUG is off in tests) would 301-redirect the
# plain-HTTP test client and mark cookies Secure. Turn it off for the suite; the
# hardening itself is covered by test_settings_hardening.py, which loads
# settings.py fresh under a production-like environment.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
STORAGES = {
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
