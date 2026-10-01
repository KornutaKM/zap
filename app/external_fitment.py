from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import aiohttp

from app.domain import Vehicle
from app.fitment import CrossReference, FitmentResolution


@dataclass(frozen=True, slots=True)
class HttpFitmentConfig:
    base_url: str
    resolve_path: str = "/fitment/resolve"
    api_key: str | None = None
    api_key_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    allow_http: bool = False

    def validate(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("FITMENT_API_BASE_URL must be an absolute HTTP(S) URL")
        if parsed.scheme != "https" and not self.allow_http:
            raise ValueError("Fitment API must use HTTPS unless allow_http is enabled")


def parse_fitment_payload(payload: object) -> FitmentResolution:
    if not isinstance(payload, dict):
        return FitmentResolution(
            status="unverified",
            reason="Fitment API returned an invalid payload.",
        )

    status = str(payload.get("status") or "unverified").casefold()
    if status not in {"confirmed", "probable", "unverified"}:
        status = "unverified"

    raw_oe = payload.get("oe_numbers") or []
    oe_numbers = tuple(
        str(item).strip()
        for item in raw_oe
        if str(item).strip()
    ) if isinstance(raw_oe, list) else ()

    crosses: list[CrossReference] = []
    raw_crosses = payload.get("crosses") or []
    if isinstance(raw_crosses, list):
        for item in raw_crosses:
            if not isinstance(item, dict):
                continue
            brand = str(item.get("brand") or "").strip()
            article = str(item.get("article") or "").strip()
            if brand and article:
                crosses.append(CrossReference(brand=brand, article=article))

    return FitmentResolution(
        status=status,
        oe_numbers=oe_numbers,
        crosses=tuple(crosses),
        reason=str(payload.get("reason") or "").strip(),
    )


class GenericHttpFitmentCatalog:
    def __init__(self, config: HttpFitmentConfig) -> None:
        config.validate()
        self.config = config

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
        params.update({key: str(value) for key, value in optional.items() if value})
        return params

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

        url = urljoin(
            self.config.base_url.rstrip("/") + "/",
            self.config.resolve_path.lstrip("/"),
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
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return FitmentResolution(
                status="unverified",
                reason="Внешний каталог применимости временно недоступен.",
            )

        return parse_fitment_payload(payload)
