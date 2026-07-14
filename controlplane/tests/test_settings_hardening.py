"""Regression tests for the fail-closed SECRET_KEY (#4) and the production
transport/cookie hardening (#7).

Both are computed at settings-module import time, so each case loads
``pulsegrid/settings.py`` fresh under a controlled environment rather than
touching the already-configured ``django.conf.settings``.
"""

import importlib.util
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "pulsegrid" / "settings.py"

# Env keys the settings module reads that these tests care about; cleared before
# each probe so ambient values (e.g. a real DJANGO_SECRET_KEY) can't leak in.
_MANAGED = [
    "DJANGO_SECRET_KEY",
    "DJANGO_SECRET_KEY_FALLBACKS",
    "DJANGO_DEBUG",
    "DJANGO_SESSION_COOKIE_SECURE",
    "DJANGO_CSRF_COOKIE_SECURE",
    "DJANGO_SECURE_SSL_REDIRECT",
    "DJANGO_SECURE_HSTS_SECONDS",
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    "DJANGO_SECURE_HSTS_PRELOAD",
    "DJANGO_TRUST_PROXY_SSL_HEADER",
]


def load_settings(monkeypatch, **env):
    for key in _MANAGED:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    spec = importlib.util.spec_from_file_location("pulsegrid._settings_probe", SETTINGS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missing_secret_key_in_production_fails_closed(monkeypatch):
    with pytest.raises(ImproperlyConfigured):
        load_settings(monkeypatch)  # DEBUG off, no key


def test_blank_secret_key_in_production_fails_closed(monkeypatch):
    with pytest.raises(ImproperlyConfigured):
        load_settings(monkeypatch, DJANGO_SECRET_KEY="")


def test_debug_falls_back_to_dev_key(monkeypatch):
    settings = load_settings(monkeypatch, DJANGO_DEBUG="1")
    assert settings.SECRET_KEY == "dev-insecure-secret-key-change-me"


def test_explicit_secret_key_and_fallbacks(monkeypatch):
    settings = load_settings(
        monkeypatch, DJANGO_SECRET_KEY="real-key", DJANGO_SECRET_KEY_FALLBACKS="old1,old2"
    )
    assert settings.SECRET_KEY == "real-key"
    assert settings.SECRET_KEY_FALLBACKS == ["old1", "old2"]


def test_production_transport_is_hardened_by_default(monkeypatch):
    settings = load_settings(monkeypatch, DJANGO_SECRET_KEY="real-key")
    assert settings.SESSION_COOKIE_SECURE is True
    assert settings.CSRF_COOKIE_SECURE is True
    assert settings.SECURE_SSL_REDIRECT is True
    assert settings.SECURE_HSTS_SECONDS == 31536000
    assert settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert settings.SECURE_HSTS_PRELOAD is True
    assert settings.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")


def test_debug_leaves_transport_open_for_local_dev(monkeypatch):
    settings = load_settings(monkeypatch, DJANGO_DEBUG="1")
    assert settings.SESSION_COOKIE_SECURE is False
    assert settings.CSRF_COOKIE_SECURE is False
    assert settings.SECURE_SSL_REDIRECT is False
    assert settings.SECURE_HSTS_SECONDS == 0
    assert not hasattr(settings, "SECURE_PROXY_SSL_HEADER")


def test_proxy_ssl_header_can_be_disabled_for_direct_exposure(monkeypatch):
    settings = load_settings(
        monkeypatch, DJANGO_SECRET_KEY="real-key", DJANGO_TRUST_PROXY_SSL_HEADER="0"
    )
    assert not hasattr(settings, "SECURE_PROXY_SSL_HEADER")


def test_secure_cookie_override(monkeypatch):
    settings = load_settings(
        monkeypatch, DJANGO_SECRET_KEY="real-key", DJANGO_SESSION_COOKIE_SECURE="0"
    )
    assert settings.SESSION_COOKIE_SECURE is False
    assert settings.CSRF_COOKIE_SECURE is True  # untouched override stays secure
