"""Standalone process entrypoint for durable image-generation workers."""

from __future__ import annotations

import asyncio
import logging
import signal

from backend.core.logging_config import setup_logging

setup_logging()

from backend.core import close_core_clients, warm_core_clients  # noqa: E402
from backend.core.config import settings  # noqa: E402
from backend.jobs.factory import create_image_job_manager  # noqa: E402
from backend.storylines.factory import create_storyline_manager  # noqa: E402

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    """Run queue consumers until Container Apps asks the replica to stop."""

    stop_requested = asyncio.Event()
    loop = asyncio.get_running_loop()
    installed_signals: list[signal.Signals] = []

    for shutdown_signal in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(shutdown_signal, stop_requested.set)
            installed_signals.append(shutdown_signal)
        except NotImplementedError:  # pragma: no cover - Linux supports handlers.
            pass

    manager = None
    storyline_manager = None
    try:
        await warm_core_clients()
        manager = create_image_job_manager(settings)
        await manager.start()
        storyline_manager = create_storyline_manager(settings, manager)
        await storyline_manager.start()
        logger.info(
            "Image job worker started with concurrency=%s",
            settings.IMAGE_JOB_CONCURRENCY,
        )
        await stop_requested.wait()
    finally:
        logger.info("Stopping image job worker")
        try:
            if storyline_manager is not None:
                await storyline_manager.close()
        finally:
            try:
                if manager is not None:
                    await manager.close()
            finally:
                try:
                    await close_core_clients()
                finally:
                    for shutdown_signal in installed_signals:
                        loop.remove_signal_handler(shutdown_signal)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
