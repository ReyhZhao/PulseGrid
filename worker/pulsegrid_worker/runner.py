"""
Worker main loop.

Claims batches of check tasks from the control plane, executes them with
bounded concurrency, and posts the results back. A separate heartbeat task
keeps the control plane informed that this worker is alive. Failed submits
are retried on the next iteration so results are not lost on transient
network errors.
"""

import asyncio
import logging
import signal

import httpx

from .api import ControlPlaneClient
from .checks import run_check
from .config import Config

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, config: Config):
        self.config = config
        self.client = ControlPlaneClient(config)
        self._semaphore = asyncio.Semaphore(config.concurrency)
        self._stopping = asyncio.Event()
        self._pending_results: list[dict] = []

    def request_stop(self, *_args):
        logger.info("shutdown requested")
        self._stopping.set()

    async def _run_one(self, task: dict) -> dict:
        async with self._semaphore:
            return await run_check(task)

    async def process_batch(self) -> int:
        """One claim/execute/submit cycle. Returns number of tasks executed."""
        try:
            tasks = await self.client.claim_tasks()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("claim failed: %s", exc)
            return 0

        if tasks:
            results = await asyncio.gather(*(self._run_one(task) for task in tasks))
            self._pending_results.extend(results)

        if self._pending_results:
            try:
                accepted = await self.client.submit_results(self._pending_results)
                logger.info("submitted %d result(s), %d accepted", len(self._pending_results), accepted)
                self._pending_results = []
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("submit failed, keeping %d result(s): %s", len(self._pending_results), exc)
                # Cap the retry buffer so an extended outage can't grow memory
                # without bound; oldest results are dropped first.
                self._pending_results = self._pending_results[-1000:]

        return len(tasks)

    async def _heartbeat_loop(self):
        while not self._stopping.is_set():
            try:
                info = await self.client.heartbeat()
                logger.debug("heartbeat ok: %s", info)
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("heartbeat failed: %s", exc)
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self.config.heartbeat_interval_seconds
                )
            except TimeoutError:
                pass

    async def run(self):
        logger.info("pulsegrid worker starting against %s", self.config.control_plane_url)
        heartbeat = asyncio.create_task(self._heartbeat_loop())
        try:
            while not self._stopping.is_set():
                executed = await self.process_batch()
                if executed == 0 and not self._stopping.is_set():
                    try:
                        await asyncio.wait_for(
                            self._stopping.wait(), timeout=self.config.poll_interval_seconds
                        )
                    except TimeoutError:
                        pass
        finally:
            self._stopping.set()
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            await self.client.close()
        logger.info("pulsegrid worker stopped")


def main():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    config = Config.from_env()
    worker = Worker(config)

    loop = asyncio.new_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.request_stop)
    try:
        loop.run_until_complete(worker.run())
    finally:
        loop.close()
