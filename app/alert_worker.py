import asyncio
import logging
from html import escape

from aiogram import Bot

from app.observability import log_event
from app.price_alerts import check_all_price_alerts
from app.search_service import PartsSearchService


logger = logging.getLogger("zap.alerts")


async def run_price_alert_cycle(
    bot: Bot,
    search_service: PartsSearchService,
) -> int:
    from app.db import update_price_alert

    hits = await check_all_price_alerts(search_service)
    delivered = 0

    for hit in hits:
        price = f"{hit.current_price:,.0f}".replace(",", " ")
        target = f"{hit.alert.target_price:,.0f}".replace(",", " ")
        try:
            await bot.send_message(
                hit.alert.telegram_user_id,
                "<b>Цена снизилась</b>\n\n"
                f"{escape(hit.alert.brand)} · "
                f"<code>{escape(hit.alert.article)}</code>\n"
                f"{escape(hit.alert.title)}\n\n"
                f"Сейчас: <b>{price} ₽</b>\n"
                f"Ваш порог: {target} ₽",
            )
            await update_price_alert(
                hit.alert.id,
                last_price=hit.current_price,
                triggered=True,
            )
            delivered += 1
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "price_alert_delivery_failed",
                "failed to deliver price alert",
                alert_id=hit.alert.id,
                error=type(exc).__name__,
            )

    return delivered


async def price_alert_loop(
    bot: Bot,
    search_service: PartsSearchService,
    interval_seconds: int,
    *,
    run_immediately: bool = False,
) -> None:
    interval = max(60, interval_seconds)
    log_event(
        logger,
        logging.INFO,
        "price_alert_worker_started",
        "price alert worker started",
        interval_seconds=interval,
    )

    first = True
    while True:
        if not first or not run_immediately:
            await asyncio.sleep(interval)
        first = False

        try:
            delivered = await run_price_alert_cycle(bot, search_service)
            if delivered:
                log_event(
                    logger,
                    logging.INFO,
                    "price_alerts_delivered",
                    "price alerts delivered",
                    delivered=delivered,
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "price_alert_worker_failure",
                "price alert worker iteration failed",
                error=type(exc).__name__,
            )
