import asyncio

from sqlalchemy import text

async def check_database(timeout_seconds: float = 2.0) -> dict[str, object]:
    try:
        from app.db import engine

        async def _query():
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        await asyncio.wait_for(_query(), timeout=timeout_seconds)
        return {"status": "ok"}
    except Exception as exc:
        return {
            "status": "error",
            "error": type(exc).__name__,
        }


async def check_redis(
    redis_url: str | None,
    timeout_seconds: float = 2.0,
) -> dict[str, object]:
    if not redis_url:
        return {"status": "disabled"}

    try:
        from redis.asyncio import Redis

        client = Redis.from_url(redis_url, decode_responses=True)
        try:
            await asyncio.wait_for(client.ping(), timeout=timeout_seconds)
        finally:
            await client.aclose()
        return {"status": "ok"}
    except Exception as exc:
        return {
            "status": "error",
            "error": type(exc).__name__,
        }


async def readiness(settings) -> tuple[bool, dict[str, object]]:
    database, redis = await asyncio.gather(
        check_database(),
        check_redis(settings.redis_url),
    )
    ready = database["status"] == "ok" and redis["status"] in {"ok", "disabled"}
    return ready, {
        "status": "ready" if ready else "not_ready",
        "database": database,
        "redis": redis,
    }
