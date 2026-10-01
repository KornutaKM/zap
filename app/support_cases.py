from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain import CustomerOrder, OrderCase


CASE_TYPE_LABELS = {
    "availability": "Нет позиции / наличие",
    "checkout": "Проблема оформления",
    "cancellation": "Проблема отмены",
    "support": "Обращение",
    "return": "Возврат",
}

CASE_STATUS_LABELS = {
    "open": "Открыт",
    "in_review": "В работе",
    "resolved": "Решён",
}

CASE_PRIORITY_LABELS = {
    "normal": "Обычный",
    "urgent": "Срочный",
}


def case_type_label(value: str) -> str:
    return CASE_TYPE_LABELS.get(value, value)


def case_status_label(value: str) -> str:
    return CASE_STATUS_LABELS.get(value, value)


def case_priority_label(value: str) -> str:
    return CASE_PRIORITY_LABELS.get(value, value)


def can_request_return(order: CustomerOrder) -> bool:
    return order.status in {"placed", "completed"}


def normalize_case_message(value: str, *, max_length: int = 1800) -> str:
    cleaned = " ".join(value.strip().split())
    if len(cleaned) < 5:
        raise ValueError("Опишите ситуацию чуть подробнее.")
    return cleaned[:max_length]



@dataclass(frozen=True, slots=True)
class OperatorQueueStats:
    total: int
    urgent: int
    open_count: int
    in_review: int
    unassigned: int
    returns: int
    overdue: int


def _parse_case_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def case_age_hours(
    case: OrderCase,
    *,
    now: datetime | None = None,
) -> float:
    created = _parse_case_datetime(case.created_at)
    if created is None:
        return 0.0
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    seconds = max(0.0, (current.astimezone(timezone.utc) - created).total_seconds())
    return seconds / 3600.0


def case_is_overdue(
    case: OrderCase,
    *,
    urgent_hours: float = 4.0,
    normal_hours: float = 24.0,
    now: datetime | None = None,
) -> bool:
    if case.status == "resolved":
        return False
    limit = urgent_hours if case.priority == "urgent" else normal_hours
    return case_age_hours(case, now=now) >= max(0.0, limit)


def operator_queue_stats(
    cases: list[OrderCase],
    *,
    urgent_hours: float = 4.0,
    normal_hours: float = 24.0,
    now: datetime | None = None,
) -> OperatorQueueStats:
    return OperatorQueueStats(
        total=len(cases),
        urgent=sum(case.priority == "urgent" for case in cases),
        open_count=sum(case.status == "open" for case in cases),
        in_review=sum(case.status == "in_review" for case in cases),
        unassigned=sum(case.assigned_operator_user_id is None for case in cases),
        returns=sum(case.case_type == "return" for case in cases),
        overdue=sum(
            case_is_overdue(
                case,
                urgent_hours=urgent_hours,
                normal_hours=normal_hours,
                now=now,
            )
            for case in cases
        ),
    )
