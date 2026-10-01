from dataclasses import dataclass

from app.domain import Vehicle


@dataclass(frozen=True, slots=True)
class VehicleModification:
    key: str
    brand: str
    model_contains: str
    year_from: int
    year_to: int | None
    generation_code: str
    engine: str
    fuel: str
    drive: str
    power_hp: int

    @property
    def label(self) -> str:
        return (
            f"{self.generation_code} · {self.engine} · {self.fuel} · "
            f"{self.drive} · {self.power_hp} л.с."
        )

    def matches(self, vehicle: Vehicle) -> bool:
        if vehicle.brand.casefold() != self.brand.casefold():
            return False
        if self.model_contains.casefold() not in vehicle.model.casefold():
            return False
        if vehicle.year < self.year_from:
            return False
        if self.year_to is not None and vehicle.year > self.year_to:
            return False
        return True


MODIFICATIONS: tuple[VehicleModification, ...] = (
    VehicleModification(
        "bmw_x3_g01_20d_xdrive",
        "BMW",
        "X3",
        2017,
        2024,
        "G01",
        "B47D20",
        "дизель",
        "xDrive",
        190,
    ),
    VehicleModification(
        "bmw_x3_g01_30d_xdrive",
        "BMW",
        "X3",
        2017,
        2024,
        "G01",
        "B57D30",
        "дизель",
        "xDrive",
        249,
    ),
    VehicleModification(
        "bmw_x3_g01_20i_xdrive",
        "BMW",
        "X3",
        2017,
        2024,
        "G01",
        "B48B20",
        "бензин",
        "xDrive",
        184,
    ),
    VehicleModification(
        "toyota_camry_xv70_25_fwd",
        "Toyota",
        "Camry",
        2017,
        2024,
        "XV70",
        "A25A-FKS",
        "бензин",
        "FWD",
        200,
    ),
    VehicleModification(
        "toyota_camry_xv70_35_fwd",
        "Toyota",
        "Camry",
        2017,
        2024,
        "XV70",
        "2GR-FKS",
        "бензин",
        "FWD",
        249,
    ),
    VehicleModification(
        "vw_tiguan_2_14_tsi",
        "Volkswagen",
        "Tiguan",
        2016,
        2024,
        "II",
        "CZDA",
        "бензин",
        "FWD",
        150,
    ),
    VehicleModification(
        "vw_tiguan_2_20_tsi_4motion",
        "Volkswagen",
        "Tiguan",
        2016,
        2024,
        "II",
        "CHHB",
        "бензин",
        "4Motion",
        220,
    ),
)


def find_modifications(vehicle: Vehicle) -> list[VehicleModification]:
    return [item for item in MODIFICATIONS if item.matches(vehicle)]


def get_modification(key: str) -> VehicleModification | None:
    return next((item for item in MODIFICATIONS if item.key == key), None)


def apply_modification(
    vehicle: Vehicle,
    modification: VehicleModification,
) -> Vehicle:
    return Vehicle(
        brand=vehicle.brand,
        model=vehicle.model,
        year=vehicle.year,
        vin=vehicle.vin,
        id=vehicle.id,
        generation_code=modification.generation_code,
        engine=modification.engine,
        fuel=modification.fuel,
        drive=modification.drive,
        power_hp=modification.power_hp,
        modification_key=modification.key,
    )


def vehicle_is_precise(vehicle: Vehicle) -> bool:
    return bool(
        vehicle.modification_key
        and vehicle.engine
        and vehicle.generation_code
    )
