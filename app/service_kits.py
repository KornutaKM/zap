import asyncio
from dataclasses import dataclass
from decimal import Decimal

from app.domain import PartCandidate, Vehicle
from app.search_service import PartsSearchService


@dataclass(frozen=True, slots=True)
class ServiceKit:
    id: str
    title: str
    description: str
    queries: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class KitItem:
    query: str
    candidate: PartCandidate


@dataclass(frozen=True, slots=True)
class BuiltKit:
    kit: ServiceKit
    items: tuple[KitItem, ...]

    @property
    def total_price(self) -> Decimal:
        return sum(
            (item.candidate.min_price for item in self.items),
            start=Decimal("0"),
        )

    @property
    def max_delivery_days(self) -> int:
        return max((item.candidate.min_delivery_days for item in self.items), default=0)


SERVICE_KITS: dict[str, ServiceKit] = {
    "basic_to": ServiceKit(
        "basic_to",
        "Базовое ТО",
        "Основные фильтры для регулярного обслуживания.",
        ("масляный фильтр", "воздушный фильтр", "салонный фильтр"),
    ),
    "extended_to": ServiceKit(
        "extended_to",
        "Расширенное ТО",
        "Фильтры и дополнительные расходники.",
        (
            "масляный фильтр",
            "воздушный фильтр",
            "салонный фильтр",
            "топливный фильтр",
            "свечи зажигания",
        ),
    ),
    "front_brakes": ServiceKit(
        "front_brakes",
        "Передние тормоза",
        "Колодки и тормозные диски передней оси.",
        ("передние тормозные колодки", "передние тормозные диски"),
    ),
}


def get_service_kit(kit_id: str) -> ServiceKit | None:
    return SERVICE_KITS.get(kit_id)


async def build_service_kit(
    service: PartsSearchService,
    vehicle: Vehicle,
    kit: ServiceKit,
) -> BuiltKit:
    batches = await asyncio.gather(
        *(service.parts(vehicle, query) for query in kit.queries)
    )
    items = [
        KitItem(query=query, candidate=candidates[0])
        for query, candidates in zip(kit.queries, batches, strict=True)
        if candidates
    ]
    return BuiltKit(kit=kit, items=tuple(items))
