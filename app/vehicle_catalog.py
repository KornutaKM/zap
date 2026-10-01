from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VehicleGeneration:
    key: str
    brand: str
    family: str
    code: str
    years: str

    @property
    def display_model(self) -> str:
        return f"{self.family} {self.code}"


GENERATIONS: tuple[VehicleGeneration, ...] = (
    VehicleGeneration("bmw_x3_e83", "BMW", "X3", "E83", "2003–2010"),
    VehicleGeneration("bmw_x3_f25", "BMW", "X3", "F25", "2010–2017"),
    VehicleGeneration("bmw_x3_g01", "BMW", "X3", "G01", "2017–2024"),
    VehicleGeneration("bmw_x3_g45", "BMW", "X3", "G45", "2024–"),
    VehicleGeneration("bmw_3_e90", "BMW", "3 Series", "E90/E91", "2005–2013"),
    VehicleGeneration("bmw_3_f30", "BMW", "3 Series", "F30/F31", "2011–2019"),
    VehicleGeneration("bmw_3_g20", "BMW", "3 Series", "G20/G21", "2018–"),
    VehicleGeneration("toyota_camry_xv50", "Toyota", "Camry", "XV50", "2011–2018"),
    VehicleGeneration("toyota_camry_xv70", "Toyota", "Camry", "XV70", "2017–2024"),
    VehicleGeneration("toyota_camry_xv80", "Toyota", "Camry", "XV80", "2024–"),
    VehicleGeneration("vw_tiguan_1", "Volkswagen", "Tiguan", "I", "2007–2016"),
    VehicleGeneration("vw_tiguan_2", "Volkswagen", "Tiguan", "II", "2016–2024"),
    VehicleGeneration("vw_tiguan_3", "Volkswagen", "Tiguan", "III", "2024–"),
    VehicleGeneration("skoda_octavia_a5", "Skoda", "Octavia", "A5", "2004–2013"),
    VehicleGeneration("skoda_octavia_a7", "Skoda", "Octavia", "A7", "2013–2020"),
    VehicleGeneration("skoda_octavia_a8", "Skoda", "Octavia", "A8", "2019–"),
)

ALIASES: dict[tuple[str, str], str] = {
    ("bmw", "3"): "3 Series",
    ("bmw", "3 series"): "3 Series",
    ("bmw", "x3"): "X3",
    ("toyota", "camry"): "Camry",
    ("volkswagen", "tiguan"): "Tiguan",
    ("vw", "tiguan"): "Tiguan",
    ("skoda", "octavia"): "Octavia",
}


def find_generations(brand: str, model: str) -> list[VehicleGeneration]:
    brand_key = brand.casefold().strip()
    model_key = " ".join(model.casefold().split())

    family = ALIASES.get((brand_key, model_key))
    if family is None:
        return []

    canonical_brand = "Volkswagen" if brand_key == "vw" else brand
    return [
        item
        for item in GENERATIONS
        if item.brand.casefold() == canonical_brand.casefold()
        and item.family.casefold() == family.casefold()
    ]


def get_generation(key: str) -> VehicleGeneration | None:
    return next((item for item in GENERATIONS if item.key == key), None)
