from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlparse

import aiohttp

from app.domain import Offer, Vehicle
from app.providers import PartsProvider


@dataclass(frozen=True, slots=True)
class HttpProviderConfig:
    name: str
    base_url: str
    search_path: str = "/search"
    api_key: str | None = None
    api_key_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    allow_http: bool = False

    def validate(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("EXTERNAL_PROVIDER_BASE_URL must be an absolute HTTP(S) URL")
        if parsed.scheme != "https" and not self.allow_http:
            raise ValueError("External provider must use HTTPS unless allow_http is enabled")


def parse_offer_payload(
    payload: object,
    provider_name: str,
) -> list[Offer]:
    if isinstance(payload, dict):
        raw_items = (
            payload.get("items")
            or payload.get("offers")
            or payload.get("results")
            or []
        )
    elif isinstance(payload, list):
        raw_items = payload
    else:
        return []

    if not isinstance(raw_items, list):
        return []

    offers: list[Offer] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        try:
            brand = str(item["brand"]).strip()
            article = str(item["article"]).strip()
            title = str(item.get("title") or article).strip()
            price = Decimal(str(item["price"]))
            delivery_days = int(item.get("delivery_days", 0))
        except (KeyError, TypeError, ValueError, InvalidOperation):
            continue

        if not brand or not article or price < 0 or delivery_days < 0:
            continue

        quality_raw = item.get("quality", 0.8)
        try:
            quality = min(1.0, max(0.0, float(quality_raw)))
        except (TypeError, ValueError):
            quality = 0.8

        offers.append(
            Offer(
                provider=str(item.get("provider") or provider_name),
                brand=brand,
                article=article,
                title=title,
                price=price,
                delivery_days=delivery_days,
                quality=quality,
                url=str(item["url"]) if item.get("url") else None,
                in_stock=bool(item.get("in_stock", True)),
            )
        )

    return offers


class GenericHttpProvider(PartsProvider):
    def __init__(self, config: HttpProviderConfig) -> None:
        config.validate()
        self.config = config
        self.name = config.name

    def _headers(self) -> dict[str, str]:
        if not self.config.api_key:
            return {}

        value = self.config.api_key
        if self.config.auth_scheme:
            value = f"{self.config.auth_scheme} {value}".strip()

        return {self.config.api_key_header: value}

    @staticmethod
    def _params(vehicle: Vehicle, query: str) -> dict[str, str]:
        params = {
            "query": query,
            "brand": vehicle.brand,
            "model": vehicle.model,
            "year": str(vehicle.year),
        }
        optional = {
            "vin": vehicle.vin,
            "generation": vehicle.generation_code,
            "engine": vehicle.engine,
            "fuel": vehicle.fuel,
            "drive": vehicle.drive,
            "modification_key": vehicle.modification_key,
        }
        params.update({key: value for key, value in optional.items() if value})
        return params

    async def search(self, vehicle: Vehicle, query: str) -> list[Offer]:
        url = urljoin(
            self.config.base_url.rstrip("/") + "/",
            self.config.search_path.lstrip("/"),
        )
        try:
            async with aiohttp.ClientSession(
                headers=self._headers(),
                raise_for_status=True,
            ) as session:
                async with session.get(
                    url,
                    params=self._params(vehicle, query),
                ) as response:
                    payload = await response.json(content_type=None)
        except (
            aiohttp.ClientError,
            TimeoutError,
            ValueError,
        ):
            return []

        return parse_offer_payload(payload, self.name)
