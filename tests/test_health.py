import asyncio
from types import SimpleNamespace

from app.health import readiness


def test_readiness_accepts_disabled_redis(monkeypatch):
    async def ok_database():
        return {"status": "ok"}

    monkeypatch.setattr("app.health.check_database", ok_database)
    ready, payload = asyncio.run(readiness(SimpleNamespace(redis_url=None)))
    assert ready
    assert payload["redis"]["status"] == "disabled"
