from dataclasses import dataclass
from typing import Protocol

from app.domain import Vehicle


@dataclass(frozen=True, slots=True)
class VehicleResolution:
    status: str
    vehicle: Vehicle | None = None
    source: str = ""
    reason: str = ""

    @property
    def resolved(self) -> bool:
        return self.status == "resolved" and self.vehicle is not None


class VehicleResolver(Protocol):
    async def resolve_vin(self, vin: str) -> VehicleResolution:
        ...


class NullVehicleResolver:
    async def resolve_vin(self, vin: str) -> VehicleResolution:
        return VehicleResolution(
            status="unavailable",
            source="none",
            reason="Внешний VIN resolver не настроен.",
        )


def merge_vehicle_resolution(
    saved: Vehicle,
    resolution: VehicleResolution,
) -> Vehicle:
    if not resolution.resolved or resolution.vehicle is None:
        return saved

    resolved = resolution.vehicle
    return Vehicle(
        brand=resolved.brand or saved.brand,
        model=resolved.model or saved.model,
        year=resolved.year or saved.year,
        vin=saved.vin or resolved.vin,
        id=saved.id,
        generation_code=resolved.generation_code or saved.generation_code,
        engine=resolved.engine or saved.engine,
        fuel=resolved.fuel or saved.fuel,
        drive=resolved.drive or saved.drive,
        power_hp=resolved.power_hp or saved.power_hp,
        modification_key=resolved.modification_key or saved.modification_key,
    )
