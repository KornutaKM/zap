from dataclasses import dataclass
from typing import Protocol

from app.domain import Vehicle


@dataclass(frozen=True, slots=True)
class CrossReference:
    brand: str
    article: str


@dataclass(frozen=True, slots=True)
class FitmentRecord:
    query_key: str
    brand: str
    model_contains: str
    generation_code: str | None
    engine: str | None
    oe_numbers: tuple[str, ...]
    crosses: tuple[CrossReference, ...]


@dataclass(frozen=True, slots=True)
class FitmentResolution:
    status: str
    oe_numbers: tuple[str, ...] = ()
    crosses: tuple[CrossReference, ...] = ()
    reason: str = ""

    @property
    def confirmed(self) -> bool:
        return self.status == "confirmed"


class FitmentCatalog(Protocol):
    async def resolve(self, vehicle: Vehicle | None, query: str) -> FitmentResolution:
        ...


DEMO_RECORDS: tuple[FitmentRecord, ...] = (
    FitmentRecord(
        "передние тормозные колодки",
        "BMW",
        "X3",
        "G01",
        None,
        ("DEMO-OE-BMW-G01-FPAD",),
        (
            CrossReference("ATE", "13.0460-7184.2"),
            CrossReference("TRW", "GDB1956"),
            CrossReference("Brembo", "P06089"),
        ),
    ),
    FitmentRecord(
        "передние тормозные диски",
        "BMW",
        "X3",
        "G01",
        None,
        ("DEMO-OE-BMW-G01-FDISC",),
        (
            CrossReference("Zimmermann", "150.3497.20"),
            CrossReference("Brembo", "09.C394.13"),
            CrossReference("ATE", "24.0124-0237.1"),
        ),
    ),
    FitmentRecord(
        "масляный фильтр",
        "BMW",
        "X3",
        "G01",
        "B47D20",
        ("DEMO-OE-BMW-B47-OIL",),
        (
            CrossReference("MANN-FILTER", "HU816X"),
            CrossReference("Mahle", "OX404D"),
            CrossReference("Bosch", "F026407123"),
        ),
    ),
    FitmentRecord(
        "масляный фильтр",
        "Toyota",
        "Camry",
        "XV70",
        "A25A-FKS",
        ("DEMO-OE-TOYOTA-A25A-OIL",),
        (
            CrossReference("MANN-FILTER", "HU816X"),
            CrossReference("Mahle", "OX404D"),
        ),
    ),
)


def normalize_query(query: str) -> str:
    value = " ".join(query.casefold().split())
    aliases = {
        "передние колодки": "передние тормозные колодки",
        "колодки передние": "передние тормозные колодки",
        "передние диски": "передние тормозные диски",
        "диски передние": "передние тормозные диски",
        "фильтр масляный": "масляный фильтр",
    }
    return aliases.get(value, value)


class DemoFitmentCatalog:
    async def resolve(
        self,
        vehicle: Vehicle | None,
        query: str,
    ) -> FitmentResolution:
        if vehicle is None:
            return FitmentResolution(
                status="unverified",
                reason="Автомобиль не выбран.",
            )

        normalized = normalize_query(query)
        possible = [
            item
            for item in DEMO_RECORDS
            if item.query_key == normalized
            and item.brand.casefold() == vehicle.brand.casefold()
            and item.model_contains.casefold() in vehicle.model.casefold()
        ]
        if not possible:
            return FitmentResolution(
                status="unverified",
                reason="Для этого запроса нет demo-данных применимости.",
            )

        generation_matches = [
            item
            for item in possible
            if not item.generation_code
            or item.generation_code == vehicle.generation_code
            or item.generation_code.casefold() in vehicle.model.casefold()
        ]
        if not generation_matches:
            return FitmentResolution(
                status="unverified",
                reason="Поколение автомобиля не совпало с demo-каталогом.",
            )

        exact = [
            item
            for item in generation_matches
            if item.engine is None or item.engine == vehicle.engine
        ]

        if vehicle.modification_key and exact:
            selected = exact[0]
            return FitmentResolution(
                status="confirmed",
                oe_numbers=selected.oe_numbers,
                crosses=selected.crosses,
                reason="Совместимость подтверждена demo-каталогом по модификации.",
            )

        selected = generation_matches[0]
        return FitmentResolution(
            status="probable",
            oe_numbers=selected.oe_numbers,
            crosses=selected.crosses,
            reason="Подходит по модели/поколению; двигатель ещё не подтверждён.",
        )
