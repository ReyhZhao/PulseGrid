import httpx
import respx

from pulsegrid_worker.config import Config
from pulsegrid_worker.runner import Worker

from .conftest import make_http_task

CONTROL_PLANE = "https://control.example.com"


def make_config(**overrides):
    defaults = dict(
        control_plane_url=CONTROL_PLANE,
        worker_token="pgw_test",
        max_batch=10,
        concurrency=5,
        poll_interval_seconds=0.01,
        heartbeat_interval_seconds=60,
        request_timeout_seconds=5,
    )
    defaults.update(overrides)
    return Config(**defaults)


@respx.mock
async def test_process_batch_executes_and_submits(http_server):
    claim = respx.post(f"{CONTROL_PLANE}/api/v1/worker/claim").mock(
        return_value=httpx.Response(
            200, json={"region": "eu-west", "tasks": [make_http_task(f"{http_server}/ok")]}
        )
    )
    submit = respx.post(f"{CONTROL_PLANE}/api/v1/worker/results").mock(
        return_value=httpx.Response(200, json={"accepted": 1})
    )
    # let requests to the local test origin through
    respx.route(host="127.0.0.1").pass_through()

    worker = Worker(make_config())
    executed = await worker.process_batch()
    await worker.client.close()

    assert executed == 1
    assert claim.called
    assert submit.called
    sent = submit.calls[0].request.read()
    assert b'"ok": true' in sent or b'"ok":true' in sent


@respx.mock
async def test_results_are_kept_when_submit_fails(http_server):
    respx.post(f"{CONTROL_PLANE}/api/v1/worker/claim").mock(
        return_value=httpx.Response(
            200, json={"region": "eu-west", "tasks": [make_http_task(f"{http_server}/ok")]}
        )
    )
    respx.post(f"{CONTROL_PLANE}/api/v1/worker/results").mock(
        return_value=httpx.Response(503)
    )
    respx.route(host="127.0.0.1").pass_through()

    worker = Worker(make_config())
    await worker.process_batch()
    assert len(worker._pending_results) == 1
    await worker.client.close()


@respx.mock
async def test_claim_failure_is_survivable():
    respx.post(f"{CONTROL_PLANE}/api/v1/worker/claim").mock(side_effect=httpx.ConnectError("down"))
    worker = Worker(make_config())
    assert await worker.process_batch() == 0
    await worker.client.close()


@respx.mock
async def test_heartbeat_sends_version():
    route = respx.post(f"{CONTROL_PLANE}/api/v1/worker/heartbeat").mock(
        return_value=httpx.Response(200, json={"region": "eu-west", "queue_depth": 0})
    )
    worker = Worker(make_config())
    info = await worker.client.heartbeat()
    await worker.client.close()
    assert info["region"] == "eu-west"
    assert b"version" in route.calls[0].request.read()
