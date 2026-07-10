import os
from dataclasses import dataclass, field


@dataclass
class Config:
    control_plane_url: str = ""
    worker_token: str = ""
    max_batch: int = 25
    # Max checks running concurrently in this worker.
    concurrency: int = 50
    # Sleep between claim polls when the queue was empty.
    poll_interval_seconds: float = 2.0
    heartbeat_interval_seconds: float = 30.0
    request_timeout_seconds: float = 15.0
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Config":
        url = os.environ.get("CONTROL_PLANE_URL", "").rstrip("/")
        token = os.environ.get("WORKER_TOKEN", "")
        if not url or not token:
            raise SystemExit("CONTROL_PLANE_URL and WORKER_TOKEN environment variables are required")
        return cls(
            control_plane_url=url,
            worker_token=token,
            max_batch=int(os.environ.get("WORKER_MAX_BATCH", "25")),
            concurrency=int(os.environ.get("WORKER_CONCURRENCY", "50")),
            poll_interval_seconds=float(os.environ.get("WORKER_POLL_INTERVAL", "2")),
            heartbeat_interval_seconds=float(os.environ.get("WORKER_HEARTBEAT_INTERVAL", "30")),
            request_timeout_seconds=float(os.environ.get("WORKER_REQUEST_TIMEOUT", "15")),
        )
