"""HTTP client for the control-plane worker API."""

import logging

import httpx

from . import __version__
from .config import Config

logger = logging.getLogger(__name__)


class ControlPlaneClient:
    def __init__(self, config: Config):
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.control_plane_url,
            headers={
                "Authorization": f"Bearer {config.worker_token}",
                "User-Agent": f"pulsegrid-worker/{__version__}",
            },
            timeout=config.request_timeout_seconds,
        )

    async def close(self):
        await self._client.aclose()

    async def claim_tasks(self) -> list[dict]:
        response = await self._client.post(
            "/api/v1/worker/claim", json={"max_tasks": self._config.max_batch}
        )
        response.raise_for_status()
        return response.json().get("tasks", [])

    async def submit_results(self, results: list[dict]) -> int:
        if not results:
            return 0
        response = await self._client.post("/api/v1/worker/results", json={"results": results})
        response.raise_for_status()
        return response.json().get("accepted", 0)

    async def heartbeat(self) -> dict:
        response = await self._client.post("/api/v1/worker/heartbeat", json={"version": __version__})
        response.raise_for_status()
        return response.json()
