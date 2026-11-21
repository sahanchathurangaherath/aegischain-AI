import asyncio
import signal
from prometheus_client import start_http_server
import structlog

from config.settings import settings
from events.outbox_consumer import OutboxConsumer

logger = structlog.get_logger(__name__)


async def run_worker() -> None:
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL must be configured to run the outbox worker.")

    start_http_server(8002)
    logger.info(
        "outbox_worker_started",
        metrics_port=8002,
        poll_interval_s=settings.OUTBOX_POLL_INTERVAL_S,
    )

    consumer = OutboxConsumer(dsn=settings.DATABASE_URL)
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    try:
        while not stop_event.is_set():
            try:
                count = await consumer.process_batch()
                if count == 0:
                    await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL_S)
            except Exception as exc:
                logger.error("outbox_poll_loop_error", error=str(exc))
                await asyncio.sleep(settings.OUTBOX_POLL_INTERVAL_S)
    except KeyboardInterrupt:
        logger.info("outbox_worker_stopping")


if __name__ == "__main__":
    asyncio.run(run_worker())
