from collections import defaultdict
from decimal import Decimal
from html import escape

from app.domain import PriceHistoryPoint


def summarize_price_history(
    points: list[PriceHistoryPoint],
    *,
    max_providers: int = 5,
) -> str:
    if not points:
        return "История цены пока не накоплена."

    grouped: dict[str, list[PriceHistoryPoint]] = defaultdict(list)
    for point in points:
        grouped[point.provider].append(point)

    lines = ["<b>История цены</b>", ""]
    for provider, items in list(grouped.items())[:max_providers]:
        newest = items[0]
        oldest = items[-1]
        prices = [item.price for item in items]
        minimum = min(prices)
        maximum = max(prices)

        delta = newest.price - oldest.price
        if oldest.price:
            percent = (delta / oldest.price) * Decimal("100")
        else:
            percent = Decimal("0")

        direction = "→"
        if delta < 0:
            direction = "↓"
        elif delta > 0:
            direction = "↑"

        newest_text = f"{newest.price:,.0f}".replace(",", " ")
        min_text = f"{minimum:,.0f}".replace(",", " ")
        max_text = f"{maximum:,.0f}".replace(",", " ")
        percent_text = f"{abs(percent):.1f}"

        lines.append(
            f"<b>{escape(provider)}</b>: {newest_text} ₽ {direction} {percent_text}%\n"
            f"диапазон наблюдений: {min_text}–{max_text} ₽ · точек: {len(items)}"
        )

    return "\n\n".join(lines)
