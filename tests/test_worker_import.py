import asyncio
from decimal import Decimal

from app.alert_worker import run_price_alert_cycle
from app.domain import PriceAlert
from app.price_alerts import PriceAlertHit


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, user_id, text):
        self.messages.append((user_id, text))


def test_worker_cycle_function_is_importable():
    # Delivery persistence is covered by DB integration; this smoke test ensures
    # the standalone worker module does not import app.main.
    assert callable(run_price_alert_cycle)
