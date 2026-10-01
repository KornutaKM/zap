import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.alert_worker import price_alert_loop
from app.bootstrap import build_app_services
from app.config import settings
from app.db import init_db
from app.observability import configure_logging, log_event


async def main() -> None:
    app_settings = settings()
    configure_logging(app_settings.log_level)
    logger = logging.getLogger("zap.worker")

    if not app_settings.price_alerts_enabled:
        log_event(
            logger,
            logging.INFO,
            "worker_disabled",
            "price alert worker is disabled",
        )
        return

    await init_db()
    services = build_app_services(app_settings)
    bot = Bot(
        app_settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    log_event(
        logger,
        logging.INFO,
        "worker_start",
        "standalone price alert worker starting",
        providers=[provider.name for provider in services.providers],
    )

    try:
        await price_alert_loop(
            bot,
            services.search_service,
            app_settings.price_alert_interval_seconds,
            run_immediately=True,
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
