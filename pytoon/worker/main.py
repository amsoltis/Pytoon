"""Worker entry point — polls the queue and processes jobs."""

from __future__ import annotations

import asyncio
import signal
import sys

from pytoon.db import init_db, get_session_factory, JobRow
from pytoon.log import setup_logging, get_logger
from pytoon.metrics import QUEUE_DEPTH
from pytoon.models import JobStatus
from pytoon.queue import dequeue_job, queue_depth
from pytoon.worker.runner import run_job

logger = get_logger(__name__)

_shutdown = False


def _handle_signal(sig, frame):
    global _shutdown
    logger.info("shutdown_signal", signal=sig)
    _shutdown = True


async def worker_loop():
    """Main loop: dequeue jobs and run them sequentially."""
    setup_logging(json_output=True)
    init_db()

    # Resume interrupted jobs
    await _resume_interrupted()

    logger.info("worker_started")

    while not _shutdown:
        QUEUE_DEPTH.set(queue_depth())
        msg = dequeue_job(timeout=3)
        if msg is None:
            continue

        job_id = msg.get("job_id")
        if not job_id:
            logger.warning("invalid_queue_message", msg=msg)
            continue

        logger.info("job_dequeued", job_id=job_id)
        try:
            await run_job(job_id)
        except Exception as exc:
            logger.exception("job_unhandled_error", job_id=job_id, error=str(exc))

    logger.info("worker_stopped")


async def _resume_interrupted():
    """On startup, find jobs that were mid-flight and re-run them."""
    factory = get_session_factory()
    db = factory()
    try:
        stuck = (
            db.query(JobRow)
            .filter(JobRow.status.in_([
                JobStatus.PLANNING.value,
                JobStatus.RENDERING_SEGMENTS.value,
                JobStatus.ASSEMBLING.value,
            ]))
            .all()
        )
        for job in stuck:
            logger.info("resuming_interrupted_job", job_id=job.id, status=job.status)
            await run_job(job.id)
    finally:
        db.close()


def main():
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
