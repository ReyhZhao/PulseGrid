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

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
STORAGES = {
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
