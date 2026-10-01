import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bootstrap import build_app_services
from app.config import settings
from app.db import init_db
from app.observability import configure_logging, log_event
from app.order_monitor import order_status_loop


async def main() -> None:
    app_settings = settings()
    configure_logging(app_settings.log_level)
    logger = logging.getLogger("zap.order_worker")

    if not app_settings.order_status_monitor_enabled:
        log_event(
            logger,
            logging.INFO,
            "order_worker_disabled",
            "order status monitor is disabled",
        )
        return

    if not app_settings.bot_token.strip():
        raise RuntimeError("BOT_TOKEN is required to run the order status worker")

    await init_db()
    services = build_app_services(app_settings)
    bot = Bot(
        app_settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    log_event(
        logger,
        logging.INFO,
        "order_worker_start",
        "order status worker starting",
        interval_seconds=app_settings.order_status_interval_seconds,
    )

    try:
        await order_status_loop(
            bot,
            services.checkout_registry,
            app_settings.order_status_interval_seconds,
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
