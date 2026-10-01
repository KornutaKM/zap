from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import aiohttp

from app.domain import Vehicle
from app.vehicle_resolution import VehicleResolution


@dataclass(frozen=True, slots=True)
class HttpVehicleResolverConfig:
    base_url: str
    vin_path: str = "/vehicle/vin"
    api_key: str | None = None
    api_key_header: str = "Authorization"
    auth_scheme: str = "Bearer"
    allow_http: bool = False

    def validate(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("VEHICLE_API_BASE_URL must be an absolute HTTP(S) URL")
        if parsed.scheme != "https" and not self.allow_http:
            raise ValueError("Vehicle API must use HTTPS unless allow_http is enabled")


def parse_vehicle_payload(payload: object, vin: str) -> VehicleResolution:
    if not isinstance(payload, dict):
        return VehicleResolution(
            status="unresolved",
            source="external",
            reason="Vehicle API returned an invalid payload.",
        )

    status = str(payload.get("status") or "resolved").casefold()
    if status not in {"resolved", "unresolved"}:
        status = "unresolved"

    if status != "resolved":
        return VehicleResolution(
            status="unresolved",
            source=str(payload.get("source") or "external"),
            reason=str(payload.get("reason") or "VIN не распознан."),
        )

    try:
        brand = str(payload["brand"]).strip()
        model = str(payload["model"]).strip()
        year = int(payload["year"])
    except (KeyError, TypeError, ValueError):
        return VehicleResolution(
            status="unresolved",
            source=str(payload.get("source") or "external"),
            reason="Vehicle API не вернул обязательные brand/model/year.",
        )

    if not brand or not model or year < 1900 or year > 2100:
        return VehicleResolution(
            status="unresolved",
            source=str(payload.get("source") or "external"),
            reason="Vehicle API вернул некорректные данные автомобиля.",
        )

    power = payload.get("power_hp")
    try:
        power_hp = int(power) if power is not None else None
    except (TypeError, ValueError):
        power_hp = None

    vehicle = Vehicle(
        brand=brand,
        model=model,
        year=year,
        vin=vin,
        generation_code=str(payload["generation_code"]).strip() if payload.get("generation_code") else None,
        engine=str(payload["engine"]).strip() if payload.get("engine") else None,
        fuel=str(payload["fuel"]).strip() if payload.get("fuel") else None,
        drive=str(payload["drive"]).strip() if payload.get("drive") else None,
        power_hp=power_hp,
        modification_key=str(payload["modification_key"]).strip() if payload.get("modification_key") else None,
    )
    return VehicleResolution(
        status="resolved",
        vehicle=vehicle,
        source=str(payload.get("source") or "external"),
        reason=str(payload.get("reason") or "VIN распознан внешним каталогом."),
    )


class GenericHttpVehicleResolver:
    def __init__(self, config: HttpVehicleResolverConfig) -> None:
        config.validate()
        self.config = config

    def _headers(self) -> dict[str, str]:
        if not self.config.api_key:
            return {}
        value = self.config.api_key
        if self.config.auth_scheme:
            value = f"{self.config.auth_scheme} {value}".strip()
        return {self.config.api_key_header: value}

    async def resolve_vin(self, vin: str) -> VehicleResolution:
        normalized = vin.strip().upper()
        if len(normalized) != 17:
            return VehicleResolution(
                status="unresolved",
                source="validation",
                reason="VIN должен содержать 17 символов.",
            )

        url = urljoin(
            self.config.base_url.rstrip("/") + "/",
            self.config.vin_path.lstrip("/"),
        )
        try:
            async with aiohttp.ClientSession(
                headers=self._headers(),
                raise_for_status=True,
            ) as session:
                async with session.get(url, params={"vin": normalized}) as response:
                    payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return VehicleResolution(
                status="unavailable",
                source="external",
                reason="VIN API временно недоступен.",
            )

        return parse_vehicle_payload(payload, normalized)
