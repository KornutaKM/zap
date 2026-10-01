from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkPart:
    query: str
    quantity: int = 1
    label: str | None = None


@dataclass(frozen=True, slots=True)
class WorkPackage:
    id: str
    title: str
    description: str
    parts: tuple[WorkPart, ...]


WORK_PACKAGES: dict[str, WorkPackage] = {
    "oil_service": WorkPackage(
        "oil_service",
        "Замена масла",
        "Масляный фильтр и базовые расходники.",
        (
            WorkPart("масляный фильтр", 1, "Масляный фильтр"),
        ),
    ),
    "basic_to": WorkPackage(
        "basic_to",
        "Базовое ТО",
        "Основные фильтры.",
        (
            WorkPart("масляный фильтр", 1),
            WorkPart("воздушный фильтр", 1),
            WorkPart("салонный фильтр", 1),
        ),
    ),
    "front_brakes": WorkPackage(
        "front_brakes",
        "Передние тормоза",
        "Колодки и два передних тормозных диска.",
        (
            WorkPart("передние тормозные колодки", 1, "Передние колодки"),
            WorkPart("передние тормозные диски", 2, "Передние диски"),
        ),
    ),
    "ignition": WorkPackage(
        "ignition",
        "Свечи зажигания",
        "Комплект свечей. Количество нужно уточнять по двигателю.",
        (
            WorkPart("свечи зажигания", 4, "Свечи зажигания"),
        ),
    ),
}


CUSTOM_RULES: tuple[tuple[tuple[str, ...], WorkPart], ...] = (
    (("замена масла", "масло"), WorkPart("масляный фильтр", 1, "Масляный фильтр")),
    (("масляный фильтр",), WorkPart("масляный фильтр", 1)),
    (("воздушный фильтр",), WorkPart("воздушный фильтр", 1)),
    (("салонный фильтр", "фильтр салона"), WorkPart("салонный фильтр", 1)),
    (("топливный фильтр",), WorkPart("топливный фильтр", 1)),
    (
        ("передние тормоза", "тормоза передние"),
        WorkPart("передние тормозные колодки", 1, "Передние колодки"),
    ),
    (
        ("передние тормоза", "тормоза передние"),
        WorkPart("передние тормозные диски", 2, "Передние диски"),
    ),
    (("передние колодки",), WorkPart("передние тормозные колодки", 1)),
    (("передние диски",), WorkPart("передние тормозные диски", 2)),
    (("свеч",), WorkPart("свечи зажигания", 4)),
    (("амортиз",), WorkPart("амортизаторы", 2)),
    (("подшипник", "ступич"), WorkPart("ступичный подшипник", 1)),
)


def get_work_package(package_id: str) -> WorkPackage | None:
    return WORK_PACKAGES.get(package_id)


def parse_work_text(text: str) -> list[WorkPart]:
    lowered = " ".join(text.casefold().split())
    result: list[WorkPart] = []
    seen: set[str] = set()

    for needles, part in CUSTOM_RULES:
        if any(needle in lowered for needle in needles):
            key = part.query.casefold()
            if key not in seen:
                result.append(part)
                seen.add(key)

    return result
