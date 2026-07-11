import pytest

from pulsegrid_worker import checks
from pulsegrid_worker.checks import check_traceroute, parse_traceroute_output, run_check

LINUX_OUTPUT = """\
traceroute to example.com (93.184.216.34), 30 hops max, 60 byte packets
 1  192.168.1.1  1.234 ms
 2  *
 3  10.10.0.1  5.678 ms
 4  93.184.216.34  20.100 ms
"""

# BSD/macOS traceroute prints the header on stderr; run_traceroute joins the
# streams, so the parser sees the same shape either way.
UNREACHED_OUTPUT = """\
traceroute to example.com (93.184.216.34), 5 hops max, 60 byte packets
 1  192.168.1.1  1.234 ms
 2  *
 3  *
 4  *
 5  *
"""


def make_traceroute_task(**overrides):
    task = {
        "task_id": "t1",
        "monitor_id": "m1",
        "region": "eu-west",
        "type": "traceroute",
        "host": "example.com",
        "timeout": 10,
        "hop_threshold_min": None,
        "hop_threshold_max": None,
        "required_asn": None,
    }
    task.update(overrides)
    return task


def test_parse_traceroute_output():
    dest_ip, hops = parse_traceroute_output(LINUX_OUTPUT)
    assert dest_ip == "93.184.216.34"
    assert hops == [
        {"ttl": 1, "ip": "192.168.1.1", "rtt_ms": 1.234},
        {"ttl": 2, "ip": None, "rtt_ms": None},
        {"ttl": 3, "ip": "10.10.0.1", "rtt_ms": 5.678},
        {"ttl": 4, "ip": "93.184.216.34", "rtt_ms": 20.1},
    ]


def test_parse_traceroute_output_empty():
    assert parse_traceroute_output("") == (None, [])


@pytest.fixture
def fake_traceroute(monkeypatch):
    """Stub the traceroute binary and ASN lookups with canned data."""

    async def run(host, max_hops, timeout):
        return fake_traceroute.output

    async def asns(ips, timeout=10.0):
        return fake_traceroute.asn_by_ip

    fake_traceroute.output = LINUX_OUTPUT
    fake_traceroute.asn_by_ip = {"10.10.0.1": 3320, "93.184.216.34": 15133}
    monkeypatch.setattr(checks, "run_traceroute", run)
    monkeypatch.setattr(checks, "lookup_asns", asns)
    return fake_traceroute


async def test_traceroute_success(fake_traceroute):
    result = await run_check(make_traceroute_task())
    assert result["ok"] is True
    assert result["hop_count"] == 4
    assert result["latency_ms"] == 20.1
    assert result["error"] == ""


async def test_traceroute_destination_not_reached(fake_traceroute):
    fake_traceroute.output = UNREACHED_OUTPUT
    result = await check_traceroute(make_traceroute_task())
    assert result["ok"] is False
    assert result["hop_count"] is None
    assert "not reached" in result["error"]


async def test_traceroute_hop_thresholds(fake_traceroute):
    below = await check_traceroute(make_traceroute_task(hop_threshold_min=5))
    assert below["ok"] is False
    assert "below the minimum" in below["error"]

    above = await check_traceroute(make_traceroute_task(hop_threshold_max=3))
    assert above["ok"] is False
    assert "above the maximum" in above["error"]

    within = await check_traceroute(
        make_traceroute_task(hop_threshold_min=2, hop_threshold_max=6)
    )
    assert within["ok"] is True
    assert within["hop_count"] == 4


async def test_traceroute_required_asn(fake_traceroute):
    present = await check_traceroute(make_traceroute_task(required_asn=3320))
    assert present["ok"] is True
    assert [hop.get("asn") for hop in present["hops"]] == [None, None, 3320, 15133]

    missing = await check_traceroute(make_traceroute_task(required_asn=64512))
    assert missing["ok"] is False
    assert "AS64512" in missing["error"]


async def test_traceroute_asn_not_looked_up_without_threshold(fake_traceroute):
    result = await check_traceroute(make_traceroute_task())
    assert all("asn" not in hop for hop in result["hops"])


async def test_traceroute_binary_failure(monkeypatch):
    async def boom(host, max_hops, timeout):
        raise RuntimeError("example.com: Name or service not known")

    monkeypatch.setattr(checks, "run_traceroute", boom)
    result = await check_traceroute(make_traceroute_task())
    assert result["ok"] is False
    assert "Name or service not known" in result["error"]
