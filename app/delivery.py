from dataclasses import dataclass
import re

from app.domain import DeliveryProfile


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True, slots=True)
class DeliveryInput:
    full_name: str
    phone: str
    country: str
    city: str
    address_line1: str
    postal_code: str | None = None
    email: str | None = None
    address_line2: str | None = None
    comment: str | None = None


def _clean(value: str | None, *, max_length: int) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return None
    return cleaned[:max_length]


def normalize_phone(value: str) -> str:
    raw = value.strip()
    has_plus = raw.startswith("+")
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not 8 <= len(digits) <= 15:
        raise ValueError("Телефон должен содержать от 8 до 15 цифр.")
    return f"+{digits}" if has_plus else digits


def validate_delivery_input(data: DeliveryInput) -> DeliveryInput:
    full_name = _clean(data.full_name, max_length=160)
    country = _clean(data.country, max_length=100)
    city = _clean(data.city, max_length=120)
    address_line1 = _clean(data.address_line1, max_length=250)

    if not full_name or len(full_name) < 3:
        raise ValueError("Укажите имя получателя.")
    if not country:
        raise ValueError("Укажите страну.")
    if not city:
        raise ValueError("Укажите город.")
    if not address_line1 or len(address_line1) < 4:
        raise ValueError("Укажите адрес доставки.")

    phone = normalize_phone(data.phone)
    email = _clean(data.email, max_length=200)
    if email and not EMAIL_RE.match(email):
        raise ValueError("Некорректный email.")

    return DeliveryInput(
        full_name=full_name,
        phone=phone,
        email=email,
        country=country,
        city=city,
        address_line1=address_line1,
        address_line2=_clean(data.address_line2, max_length=250),
        postal_code=_clean(data.postal_code, max_length=40),
        comment=_clean(data.comment, max_length=500),
    )


def profile_to_snapshot(profile: DeliveryProfile) -> dict[str, str | None]:
    return {
        "full_name": profile.full_name,
        "phone": profile.phone,
        "email": profile.email,
        "country": profile.country,
        "city": profile.city,
        "address_line1": profile.address_line1,
        "address_line2": profile.address_line2,
        "postal_code": profile.postal_code,
        "comment": profile.comment,
    }


def delivery_snapshot_is_complete(
    snapshot: dict[str, str | None] | None,
) -> bool:
    if not snapshot:
        return False
    required = (
        "full_name",
        "phone",
        "country",
        "city",
        "address_line1",
    )
    return all(bool(snapshot.get(key)) for key in required)
