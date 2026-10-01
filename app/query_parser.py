from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class ParsedSearchQuery:
    raw: str
    part_query: str
    sort_mode: str = "recommended"


PRICE_HINTS = (
    "подешевле",
    "дешев",
    "недорог",
    "бюджет",
    "не самые дорог",
    "цена",
)

SPEED_HINTS = (
    "побыстрее",
    "быстр",
    "срочно",
    "как можно скорее",
    "сегодня",
    "завтра",
)


def parse_search_query(text: str) -> ParsedSearchQuery:
    raw = " ".join(text.strip().split())
    lowered = raw.casefold()

    sort_mode = "recommended"
    if any(hint in lowered for hint in SPEED_HINTS):
        sort_mode = "speed"
    elif any(hint in lowered for hint in PRICE_HINTS):
        sort_mode = "price"

    cleaned = raw
    removable = (
        "подешевле",
        "побыстрее",
        "срочно",
        "бюджетные",
        "бюджетный",
        "недорогие",
        "недорогой",
        "как можно скорее",
        "не самые дорогие",
    )
    for phrase in removable:
        cleaned = re.sub(
            re.escape(phrase),
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
    cleaned = " ".join(cleaned.split()) or raw

    return ParsedSearchQuery(
        raw=raw,
        part_query=cleaned,
        sort_mode=sort_mode,
    )
