import asyncio
import logging
import time

from dataclasses import dataclass, replace

from app.domain import Offer, PartCandidate, Vehicle, group_offers, rank_parts
from app.fitment import FitmentCatalog, FitmentResolution
from app.observability import log_event
from app.providers import PartsProvider


@dataclass(slots=True)
class ProviderHealth:
    name: str
    calls: int = 0
    successes: int = 0
    failures: int = 0
    consecutive_failures: int = 0
    circuit_open_until: float = 0.0
    last_latency_ms: float | None = None
    last_error: str | None = None

    def state(self, now: float | None = None) -> str:
        current = time.monotonic() if now is None else now
        if self.circuit_open_until > current:
            return "open"
        if self.consecutive_failures > 0:
            return "degraded"
        return "healthy"


logger = logging.getLogger("zap.search")


class PartsSearchService:
    def __init__(
        self,
        providers: list[PartsProvider],
        cache_ttl_seconds: float = 60.0,
        provider_timeout_seconds: float = 5.0,
        fitment_catalog: FitmentCatalog | None = None,
        circuit_failure_threshold: int = 3,
        circuit_cooldown_seconds: float = 60.0,
    ) -> None:
        self.providers = providers
        self.cache_ttl_seconds = cache_ttl_seconds
        self.provider_timeout_seconds = provider_timeout_seconds
        self.fitment_catalog = fitment_catalog
        self.circuit_failure_threshold = max(1, circuit_failure_threshold)
        self.circuit_cooldown_seconds = max(1.0, circuit_cooldown_seconds)
        self._cache: dict[tuple, tuple[float, tuple[Offer, ...]]] = {}
        self._provider_health: dict[int, ProviderHealth] = {
            id(provider): ProviderHealth(name=provider.name)
            for provider in providers
        }

    @staticmethod
    def _cache_key(vehicle: Vehicle | None, query: str) -> tuple:
        return (
            vehicle.brand.casefold() if vehicle else None,
            vehicle.model.casefold() if vehicle else None,
            vehicle.year if vehicle else None,
            vehicle.vin if vehicle else None,
            " ".join(query.casefold().split()),
        )

    async def _provider_search(
        self,
        provider: PartsProvider,
        vehicle: Vehicle,
        query: str,
    ) -> list[Offer]:
        health = self._provider_health[id(provider)]
        now = time.monotonic()
        if health.circuit_open_until > now:
            log_event(
                logger,
                logging.WARNING,
                "provider_circuit_skip",
                "provider call skipped while circuit is open",
                provider=health.name,
                retry_after_seconds=round(health.circuit_open_until - now, 1),
            )
            return []

        health.calls += 1
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(
                provider.search(vehicle, query),
                timeout=self.provider_timeout_seconds,
            )
        except Exception as exc:
            health.failures += 1
            health.consecutive_failures += 1
            health.last_error = type(exc).__name__
            health.last_latency_ms = (time.monotonic() - started) * 1000

            log_event(
                logger,
                logging.WARNING,
                "provider_failure",
                "provider request failed",
                provider=health.name,
                error=health.last_error,
                consecutive_failures=health.consecutive_failures,
                latency_ms=round(health.last_latency_ms, 1),
            )
            if health.consecutive_failures >= self.circuit_failure_threshold:
                health.circuit_open_until = (
                    time.monotonic() + self.circuit_cooldown_seconds
                )
                log_event(
                    logger,
                    logging.ERROR,
                    "provider_circuit_open",
                    "provider circuit opened",
                    provider=health.name,
                    cooldown_seconds=self.circuit_cooldown_seconds,
                )
            return []

        was_degraded = health.consecutive_failures > 0 or health.circuit_open_until > 0
        health.successes += 1
        health.consecutive_failures = 0
        health.circuit_open_until = 0.0
        health.last_error = None
        health.last_latency_ms = (time.monotonic() - started) * 1000
        if was_degraded:
            log_event(
                logger,
                logging.INFO,
                "provider_recovered",
                "provider recovered",
                provider=health.name,
                latency_ms=round(health.last_latency_ms, 1),
            )
        return result

    async def raw_offers(self, vehicle: Vehicle | None, query: str) -> list[Offer]:
        key = self._cache_key(vehicle, query)
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached is not None and cached[0] > now:
            return list(cached[1])

        provider_vehicle = vehicle or Vehicle("Автомобиль", "не выбран", 0, None)
        batches = await asyncio.gather(
            *(
                self._provider_search(provider, provider_vehicle, query)
                for provider in self.providers
            )
        )

        offers = [offer for batch in batches for offer in batch]
        self._cache[key] = (
            now + self.cache_ttl_seconds,
            tuple(offers),
        )
        return offers

    async def parts(self, vehicle: Vehicle | None, query: str) -> list[PartCandidate]:
        offers = await self.raw_offers(vehicle, query)
        candidates = rank_parts(group_offers(offers))
        if not candidates or self.fitment_catalog is None:
            return candidates

        resolution = await self.fitment_catalog.resolve(vehicle, query)
        return self._apply_fitment(candidates, resolution)

    @staticmethod
    def _apply_fitment(
        candidates: list[PartCandidate],
        resolution: FitmentResolution,
    ) -> list[PartCandidate]:
        cross_keys = {
            (item.brand.casefold(), item.article.casefold())
            for item in resolution.crosses
        }

        enriched = []
        for candidate in candidates:
            key = (candidate.brand.casefold(), candidate.article.casefold())
            if key in cross_keys:
                enriched.append(
                    replace(
                        candidate,
                        fitment_status=resolution.status,
                        oe_numbers=resolution.oe_numbers,
                        fitment_reason=resolution.reason,
                    )
                )
            else:
                enriched.append(
                    replace(
                        candidate,
                        fitment_status="unverified",
                        oe_numbers=resolution.oe_numbers if resolution.status != "unverified" else (),
                        fitment_reason=(
                            "Артикул не найден среди cross-reference для выбранной применимости."
                            if resolution.status != "unverified"
                            else resolution.reason
                        ),
                    )
                )

        status_rank = {"confirmed": 0, "probable": 1, "unverified": 2}
        return sorted(
            enriched,
            key=lambda item: (
                status_rank.get(item.fitment_status, 3),
                item.min_price,
            ),
        )

    def clear_cache(self) -> None:
        self._cache.clear()

    def provider_statuses(self) -> list[dict[str, object]]:
        now = time.monotonic()
        rows = []
        for provider in self.providers:
            health = self._provider_health[id(provider)]
            retry_after = max(0.0, health.circuit_open_until - now)
            rows.append(
                {
                    "name": health.name,
                    "state": health.state(now),
                    "calls": health.calls,
                    "successes": health.successes,
                    "failures": health.failures,
                    "consecutive_failures": health.consecutive_failures,
                    "retry_after_seconds": round(retry_after, 1),
                    "last_latency_ms": (
                        round(health.last_latency_ms, 1)
                        if health.last_latency_ms is not None
                        else None
                    ),
                    "last_error": health.last_error,
                }
            )
        return rows


def serialize_candidate(candidate: PartCandidate) -> dict:
    return {
        "brand": candidate.brand,
        "article": candidate.article,
        "title": candidate.title,
        "quality": candidate.quality,
        "fitment_status": candidate.fitment_status,
        "oe_numbers": list(candidate.oe_numbers),
        "fitment_reason": candidate.fitment_reason,
        "offers": [
            {
                "provider": offer.provider,
                "brand": offer.brand,
                "article": offer.article,
                "title": offer.title,
                "price": str(offer.price),
                "delivery_days": offer.delivery_days,
                "quality": offer.quality,
                "url": offer.url,
                "in_stock": offer.in_stock,
            }
            for offer in candidate.offers
        ],
    }


def deserialize_candidate(data: dict) -> PartCandidate:
    from decimal import Decimal

    offers = tuple(
        Offer(
            provider=item["provider"],
            brand=item["brand"],
            article=item["article"],
            title=item["title"],
            price=Decimal(item["price"]),
            delivery_days=item["delivery_days"],
            quality=item["quality"],
            url=item.get("url"),
            in_stock=item.get("in_stock", True),
        )
        for item in data["offers"]
    )
    return PartCandidate(
        brand=data["brand"],
        article=data["article"],
        title=data["title"],
        quality=data["quality"],
        offers=offers,
        fitment_status=data.get("fitment_status", "unverified"),
        oe_numbers=tuple(data.get("oe_numbers", ())),
        fitment_reason=data.get("fitment_reason", ""),
    )
