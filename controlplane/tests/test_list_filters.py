"""Generic list filters and expansions shared by the SPA and API consumers:
`?expand=stats`, `?event_type`/`?since` on alerts, and `?page_size`.
"""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.alerts.models import AlertEvent
from apps.monitors.models import CheckResult, Monitor, MonitorRegionState, MonitorStatus

pytestmark = pytest.mark.django_db


# --- ?expand=stats ------------------------------------------------------


def test_monitor_list_omits_stats_by_default(api, monitor):
    row = api.get("/api/v1/monitors/").data["results"][0]
    assert "stats" not in row


def test_monitor_list_expands_stats(api, monitor):
    now = timezone.now()
    CheckResult.objects.create(
        monitor=monitor, region_code="eu-west", checked_at=now, ok=True, latency_ms=100
    )
    CheckResult.objects.create(
        monitor=monitor, region_code="eu-west", checked_at=now, ok=False, latency_ms=None
    )
    MonitorRegionState.objects.create(
        monitor=monitor, region_code="eu-west", status=MonitorStatus.UP
    )

    row = api.get("/api/v1/monitors/?expand=stats").data["results"][0]

    assert row["id"] == str(monitor.id)
    assert row["stats"]["uptime"]["24h"] == {
        "total_checks": 2,
        "uptime_pct": 50.0,
        "avg_latency_ms": 100.0,
    }
    assert [r["region"] for r in row["stats"]["regions"]] == ["eu-west"]


def test_expanded_stats_match_the_detail_action(api, monitor):
    CheckResult.objects.create(
        monitor=monitor, region_code="eu-west", checked_at=timezone.now(), ok=True, latency_ms=42
    )
    MonitorRegionState.objects.create(
        monitor=monitor, region_code="eu-west", status=MonitorStatus.UP
    )

    inline = api.get("/api/v1/monitors/?expand=stats").data["results"][0]["stats"]
    detail = api.get(f"/api/v1/monitors/{monitor.id}/stats/").data
    assert inline == detail


def test_expanded_stats_do_not_scale_queries_with_monitor_count(api, org):
    def build(count):
        Monitor.objects.all().delete()
        for index in range(count):
            monitor = Monitor.objects.create(
                organization=org, name=f"m{index}", url="https://example.com/", interval_seconds=60
            )
            CheckResult.objects.create(
                monitor=monitor,
                region_code="eu-west",
                checked_at=timezone.now(),
                ok=True,
                latency_ms=10,
            )
            MonitorRegionState.objects.create(
                monitor=monitor, region_code="eu-west", status=MonitorStatus.UP
            )

    def count_queries(monitors):
        build(monitors)
        with CaptureQueriesContext(connection) as captured:
            response = api.get("/api/v1/monitors/?expand=stats&page_size=1000")
        assert len(response.data["results"]) == monitors
        return len(captured)

    # Same query count for 1 and for 10 monitors: no N+1.
    assert count_queries(1) == count_queries(10)


def test_expanded_stats_stay_org_scoped(other_api, monitor):
    assert other_api.get("/api/v1/monitors/?expand=stats").data["results"] == []


# --- alert filters ------------------------------------------------------


@pytest.fixture
def alert_events(monitor):
    now = timezone.now()
    events = {
        "old_down": AlertEvent.objects.create(
            monitor=monitor, event_type=AlertEvent.Type.DOWN, summary="old down"
        ),
        "new_down": AlertEvent.objects.create(
            monitor=monitor, event_type=AlertEvent.Type.DOWN, summary="new down"
        ),
        "ssl": AlertEvent.objects.create(
            monitor=monitor, event_type=AlertEvent.Type.SSL_EXPIRY, summary="cert expiring"
        ),
    }
    # opened_at is auto_now_add, so backdate the one event explicitly.
    AlertEvent.objects.filter(pk=events["old_down"].pk).update(opened_at=now - timedelta(days=100))
    return events


def test_alerts_filter_by_event_type(api, alert_events):
    summaries = {
        row["summary"] for row in api.get("/api/v1/alerts/?event_type=down").data["results"]
    }
    assert summaries == {"old down", "new down"}


def test_alerts_filter_by_since(api, alert_events):
    since = (timezone.now() - timedelta(days=90)).isoformat()
    summaries = {row["summary"] for row in api.get("/api/v1/alerts/", {"since": since}).data["results"]}
    assert summaries == {"new down", "cert expiring"}


def test_alerts_combine_event_type_and_since(api, alert_events):
    since = (timezone.now() - timedelta(days=90)).isoformat()
    response = api.get("/api/v1/alerts/", {"event_type": "down", "since": since})
    assert [row["summary"] for row in response.data["results"]] == ["new down"]


def test_alerts_accept_a_bare_date_for_since(api, alert_events):
    since = (timezone.now() - timedelta(days=90)).date().isoformat()
    assert api.get("/api/v1/alerts/", {"since": since}).data["count"] == 2


def test_alerts_accept_an_unencoded_offset_in_since(api, alert_events):
    """A raw ISO timestamp in a query string loses its "+" to URL decoding."""
    since = (timezone.now() - timedelta(days=90)).isoformat()
    assert api.get(f"/api/v1/alerts/?since={since}").data["count"] == 2


def test_alerts_reject_an_unparseable_since(api, alert_events):
    """Ignoring it would hand back the whole history the caller was narrowing."""
    assert api.get("/api/v1/alerts/?since=last-tuesday").status_code == 400


# --- ?page_size ---------------------------------------------------------


@pytest.fixture
def many_monitors(org):
    return [
        Monitor.objects.create(
            organization=org, name=f"m{index:03d}", url="https://example.com/", interval_seconds=60
        )
        for index in range(60)
    ]


def test_page_size_is_honoured(api, many_monitors):
    response = api.get("/api/v1/monitors/?page_size=5")
    assert len(response.data["results"]) == 5
    assert response.data["count"] == 60


def test_page_size_defaults_to_fifty(api, many_monitors):
    assert len(api.get("/api/v1/monitors/").data["results"]) == 50


def test_page_size_is_capped(api, many_monitors):
    """A consumer asking for 1000 gets everything, but cannot ask for more."""
    from pulsegrid.pagination import DefaultPagination

    assert DefaultPagination.max_page_size == 1000
    response = api.get("/api/v1/monitors/?page_size=100000")
    assert len(response.data["results"]) == 60
    assert response.data["next"] is None
