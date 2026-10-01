from app.domain import CustomerOrder


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
