"""
Redis-backed work queues.

The scheduler pushes check tasks onto one list per region; globally deployed
workers claim them over the HTTP worker API. Notification jobs go onto a
single list consumed by the dispatcher process. Lists give us at-least-once,
FIFO handoff with O(1) push/pop, which is all the MVP needs; the payloads are
self-contained JSON so workers never have to call back for monitor details.
"""

import json
from functools import lru_cache

import redis
from django.conf import settings

CHECK_QUEUE_PREFIX = "pulsegrid:queue:checks:"
NOTIFY_QUEUE = "pulsegrid:queue:notify"
AUDIT_QUEUE = "pulsegrid:queue:audit"


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def reset_redis_cache() -> None:
    """Test hook: forget the cached client so it can be re-patched."""
    get_redis.cache_clear()


def check_queue_key(region_code: str) -> str:
    return f"{CHECK_QUEUE_PREFIX}{region_code}"


def push_check_tasks(region_code: str, tasks: list[dict]) -> int:
    if not tasks:
        return 0
    conn = get_redis()
    conn.rpush(check_queue_key(region_code), *[json.dumps(task) for task in tasks])
    return len(tasks)


def pop_check_tasks(region_code: str, max_tasks: int) -> list[dict]:
    conn = get_redis()
    raw = conn.lpop(check_queue_key(region_code), max_tasks)
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    return [json.loads(item) for item in raw]


def check_queue_depth(region_code: str) -> int:
    return int(get_redis().llen(check_queue_key(region_code)))


def push_notification(event_id: int) -> None:
    get_redis().rpush(NOTIFY_QUEUE, json.dumps({"event_id": event_id}))


def pop_notification(timeout_seconds: int = 5) -> dict | None:
    # timeout 0 means "don't wait" here (BLPOP's 0 would block forever).
    if timeout_seconds <= 0:
        payload = get_redis().lpop(NOTIFY_QUEUE)
        return json.loads(payload) if payload else None
    item = get_redis().blpop(NOTIFY_QUEUE, timeout=timeout_seconds)
    if item is None:
        return None
    _key, payload = item
    return json.loads(payload)


def push_audit_job(event_id: int) -> None:
    get_redis().rpush(AUDIT_QUEUE, json.dumps({"audit_event_id": event_id}))


def pop_dispatch_job(timeout_seconds: int = 5) -> tuple[str, dict] | None:
    """Blocking pop across the dispatcher-owned queues (notifications and
    MSSP audit forwards). Returns ("notify"|"audit", payload) or None.
    timeout 0 means "don't wait" (BLPOP's 0 would block forever)."""
    if timeout_seconds <= 0:
        for key, kind in ((NOTIFY_QUEUE, "notify"), (AUDIT_QUEUE, "audit")):
            payload = get_redis().lpop(key)
            if payload:
                return kind, json.loads(payload)
        return None
    item = get_redis().blpop([NOTIFY_QUEUE, AUDIT_QUEUE], timeout=timeout_seconds)
    if item is None:
        return None
    key, payload = item
    kind = "audit" if key == AUDIT_QUEUE else "notify"
    return kind, json.loads(payload)
