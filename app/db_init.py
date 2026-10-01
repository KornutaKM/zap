import asyncio
import logging

from app.config import settings
from app.db import init_db
from app.observability import configure_logging, log_event


async def main() -> None:
    app_settings = settings()
    configure_logging(app_settings.log_level)
    logger = logging.getLogger("zap.db_init")

    await init_db()
    log_event(
        logger,
        logging.INFO,
        "database_initialized",
        "database schema initialized",
    )


if __name__ == "__main__":
    asyncio.run(main())
