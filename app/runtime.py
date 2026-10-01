import asyncio

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application


def normalize_webhook_path(path: str) -> str:
    value = path.strip() or "/webhook"
    return value if value.startswith("/") else f"/{value}"


def validate_webhook_url(url: str | None) -> str:
    if not url or not url.startswith("https://"):
        raise ValueError("WEBHOOK_URL must be a public HTTPS URL in webhook mode")
    return url


async def run_polling(bot: Bot, dispatcher: Dispatcher) -> None:
    await bot.delete_webhook(drop_pending_updates=False)
    await dispatcher.start_polling(bot)


async def run_webhook(bot: Bot, dispatcher: Dispatcher, settings) -> None:
    webhook_url = validate_webhook_url(settings.webhook_url)
    webhook_path = normalize_webhook_path(settings.webhook_path)

    app = web.Application()

    async def healthz(request):
        return web.Response(text="ok")

    app.router.add_get("/healthz", healthz)

    handler = SimpleRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
        secret_token=settings.webhook_secret_token,
    )
    handler.register(app, path=webhook_path)
    setup_application(app, dispatcher, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(
        runner,
        host=settings.webhook_host,
        port=settings.webhook_port,
    )

    try:
        await site.start()
        await bot.set_webhook(
            webhook_url,
            secret_token=settings.webhook_secret_token,
            drop_pending_updates=False,
        )
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def run_bot(bot: Bot, dispatcher: Dispatcher, settings) -> None:
    mode = settings.bot_run_mode.casefold().strip()
    if mode == "polling":
        await run_polling(bot, dispatcher)
        return
    if mode == "webhook":
        await run_webhook(bot, dispatcher, settings)
        return
    raise ValueError("BOT_RUN_MODE must be 'polling' or 'webhook'")
