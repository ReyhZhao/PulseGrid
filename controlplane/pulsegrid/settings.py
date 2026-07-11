"""
PulseGrid control plane settings.

Everything deployment-specific is driven by environment variables so the same
image runs in dev, CI and production (see deployment/chart for the mapping).
"""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-secret-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.openid_connect",
    "allauth.headless",
    "apps.accounts",
    "apps.monitors",
    "apps.alerts",
    "apps.workerapi",
    "apps.audit",
]

SITE_ID = 1

MIDDLEWARE = [
    # First: answers /healthz and /readyz before ALLOWED_HOSTS validation —
    # kube-probe uses the pod IP as Host header.
    "pulsegrid.middleware.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    # No-op unless DEBUG and DEV_AUTO_LOGIN are both enabled (local dev only).
    "apps.accounts.middleware.DevAutoLoginMiddleware",
]

# Local-dev only: auto-authenticate every request as the first superuser.
DEV_AUTO_LOGIN = env_bool("DEV_AUTO_LOGIN", False)

ROOT_URLCONF = "pulsegrid.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "pulsegrid.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=60,
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/django-static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- API ---------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# --- OpenAPI / Swagger (drf-spectacular) --------------------------------

SPECTACULAR_SETTINGS = {
    "TITLE": "PulseGrid API",
    "DESCRIPTION": (
        "Control-plane API for PulseGrid, a multi-region uptime and TLS "
        "monitoring platform.\n\n"
        "**Authentication.** Browser/SPA clients authenticate with a session "
        "cookie (obtain a CSRF token from `GET /api/v1/auth/csrf` and send it "
        "as the `X-CSRFToken` header on unsafe requests). Check-runner workers "
        "authenticate against `/api/v1/worker/*` with an "
        "`Authorization: Bearer pgw_...` token.\n\n"
        "All tenant-scoped resources are filtered to the organizations the "
        "caller belongs to."
    ),
    "VERSION": "1.0.0",
    # The browsable schema/UI views serve their own OpenAPI document; don't
    # embed the raw schema into every rendered page.
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "TAGS": [
        {"name": "monitors", "description": "Uptime/TLS monitors and their check history."},
        {"name": "regions", "description": "Regions checks can run from."},
        {"name": "alerts", "description": "Alert events and notification channels."},
        {"name": "audit", "description": "Org-scoped audit trail."},
        {"name": "organizations", "description": "Organization self-service and membership."},
        {"name": "account", "description": "Current-user profile and onboarding."},
        {"name": "worker", "description": "Endpoints polled by check-runner workers."},
    ],
}

# --- Authentication (allauth headless + Authentik OIDC) -----------------

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "email*", "password1*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGOUT_ON_GET = False

# Allow disabling interactive signup (e.g. SSO-only deployments).
ACCOUNT_ADAPTER = "apps.accounts.adapters.AccountAdapter"
PULSEGRID_ALLOW_SIGNUP = env_bool("PULSEGRID_ALLOW_SIGNUP", True)

HEADLESS_ONLY = True
# Public base URL of the SPA; used in allauth redirects and invite emails.
PULSEGRID_FRONTEND_URL = os.environ.get("PULSEGRID_FRONTEND_URL", "").rstrip("/")
_FRONTEND_URL = PULSEGRID_FRONTEND_URL
HEADLESS_FRONTEND_URLS = {
    "socialaccount_login_error": f"{_FRONTEND_URL}/login?error=social",
    "account_confirm_email": f"{_FRONTEND_URL}/verify-email/{{key}}",
    "account_reset_password_from_key": f"{_FRONTEND_URL}/reset-password/{{key}}",
    "account_signup": f"{_FRONTEND_URL}/signup",
}

SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_STORE_TOKENS = False

AUTHENTIK_CLIENT_ID = os.environ.get("AUTHENTIK_CLIENT_ID", "")
AUTHENTIK_CLIENT_SECRET = os.environ.get("AUTHENTIK_CLIENT_SECRET", "")
# Issuer URL of the Authentik OAuth2/OIDC provider, e.g.
# https://auth.example.com/application/o/pulsegrid/
AUTHENTIK_SERVER_URL = os.environ.get("AUTHENTIK_SERVER_URL", "")

# --- Authentik user provisioning (optional) ------------------------------
# With an API token configured, inviting an email address that has no
# Authentik account yet creates a single-use enrollment invitation there,
# so external users can be provisioned on demand. Requires an enrollment
# flow with an Invitation stage in Authentik (see README).


def _authentik_base() -> str:
    from urllib.parse import urlsplit

    if not AUTHENTIK_SERVER_URL:
        return ""
    parts = urlsplit(AUTHENTIK_SERVER_URL)
    return f"{parts.scheme}://{parts.netloc}"


PULSEGRID_AUTHENTIK = {
    # Public base URL of Authentik, e.g. https://auth.example.com
    # (derived from the OIDC issuer unless set explicitly).
    "PUBLIC_URL": (os.environ.get("AUTHENTIK_PUBLIC_URL", "") or _authentik_base()).rstrip("/"),
    # API token of an Authentik service account allowed to read users/flows
    # and create invitations.
    "TOKEN": os.environ.get("AUTHENTIK_API_TOKEN", "").strip(),
    # Slug of the enrollment flow that contains an Invitation stage.
    "ENROLLMENT_FLOW": os.environ.get("AUTHENTIK_ENROLLMENT_FLOW", "").strip(),
}

SOCIALACCOUNT_PROVIDERS = {}
if AUTHENTIK_CLIENT_ID and AUTHENTIK_SERVER_URL:
    SOCIALACCOUNT_PROVIDERS["openid_connect"] = {
        "APPS": [
            {
                "provider_id": "authentik",
                "name": os.environ.get("AUTHENTIK_PROVIDER_NAME", "Authentik"),
                "client_id": AUTHENTIK_CLIENT_ID,
                "secret": AUTHENTIK_CLIENT_SECRET,
                "settings": {"server_url": AUTHENTIK_SERVER_URL},
            }
        ]
    }

# --- PulseGrid ----------------------------------------------------------

# `or` (not a get() default) so an empty REDIS_URL env var — e.g. a blank
# Vault property synced via ExternalSecret — doesn't override the default.
REDIS_URL = os.environ.get("REDIS_URL") or "redis://localhost:6379/0"

PULSEGRID = {
    # How often the scheduler scans for due monitors (seconds).
    "SCHEDULER_TICK_SECONDS": int(os.environ.get("PULSEGRID_SCHEDULER_TICK_SECONDS", "5")),
    # Max monitors scheduled per scan; keeps transactions short under load.
    "SCHEDULER_BATCH_SIZE": int(os.environ.get("PULSEGRID_SCHEDULER_BATCH_SIZE", "1000")),
    # Max check tasks a worker may claim per request.
    "MAX_CLAIM_BATCH": int(os.environ.get("PULSEGRID_MAX_CLAIM_BATCH", "50")),
    # Raw check results older than this are purged by `manage.py purge_results`.
    "RESULT_RETENTION_DAYS": int(os.environ.get("PULSEGRID_RESULT_RETENTION_DAYS", "30")),
    # Default regions bootstrapped by `manage.py ensure_regions`.
    "DEFAULT_REGIONS": os.environ.get("PULSEGRID_REGIONS", "eu-west:Europe West,us-east:US East"),
}

# --- Audit logging / MSSP forwarding -------------------------------------
# Audit events are always stored and logged as JSON to stdout (collect with
# a Wazuh agent or your k8s log pipeline). Set MSSP_URL + MSSP_API_TOKEN to
# additionally forward events >= MSSP_MIN_SEVERITY to the vels.online
# alert-ingest API (POST /api/v2/alerts/).

PULSEGRID_MSSP = {
    # .strip(): tokens/URLs pasted into Vault often carry a trailing newline,
    # which turns into an invalid Authorization header.
    "URL": os.environ.get("MSSP_URL", "").strip(),
    "TOKEN": os.environ.get("MSSP_API_TOKEN", "").strip(),
    # Authorization header scheme, e.g. "Token" (DRF default) or "Bearer".
    "AUTH_SCHEME": os.environ.get("MSSP_AUTH_SCHEME", "Token"),
    # Organization slug on the MSSP platform that owns these alerts.
    "ORG": os.environ.get("MSSP_ORG", ""),
    "MIN_SEVERITY": os.environ.get("MSSP_MIN_SEVERITY", "medium"),
    "VERIFY_SSL": env_bool("MSSP_VERIFY_SSL", True),
    # host.name entity attached to every forwarded alert.
    "HOST_NAME": os.environ.get("MSSP_HOST_NAME", ALLOWED_HOSTS[0] if ALLOWED_HOSTS else "pulsegrid"),
}

# --- Email / notifications ----------------------------------------------

EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "pulsegrid@localhost")
if not EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# --- Cross-origin -------------------------------------------------------

CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
if DEBUG:
    CORS_ALLOWED_ORIGINS = list({*CORS_ALLOWED_ORIGINS, "http://localhost:5173", "http://127.0.0.1:5173"})
    CSRF_TRUSTED_ORIGINS = list({*CSRF_TRUSTED_ORIGINS, "http://localhost:5173", "http://127.0.0.1:5173"})

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# Enable when the reverse proxy (e.g. bunkerweb) rewrites Host and passes
# the original hostname in X-Forwarded-Host instead.
USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", False)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default"},
        # Raw JSON lines, one per audit event — ship these to Wazuh.
        "audit": {"class": "logging.StreamHandler", "formatter": "audit"},
    },
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        "pulsegrid.audit": {"handlers": ["audit"], "level": "INFO", "propagate": False},
    },
}
LOGGING["formatters"]["audit"] = {"format": "%(message)s"}
