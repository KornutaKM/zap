KNOWN_BRANDS = {
    "audi", "bmw", "chevrolet", "citroen", "ford", "geely", "haval", "honda",
    "hyundai", "jeep", "kia", "lada", "lexus", "mazda", "mercedes",
    "mercedes-benz", "mitsubishi", "nissan", "opel", "peugeot", "porsche",
    "renault", "skoda", "subaru", "suzuki", "tesla", "toyota", "volkswagen",
    "volvo", "ваз", "газ", "москвич", "chery", "exeed", "omoda", "jetour",
}

MULTIWORD_BRANDS = {
    ("land", "rover"): "Land Rover",
    ("alfa", "romeo"): "Alfa Romeo",
    ("mercedes", "benz"): "Mercedes-Benz",
}


def parse_vehicle_text(text: str) -> tuple[str, str] | None:
    parts = text.strip().split()
    if len(parts) < 2:
        return None

    if len(parts) >= 3:
        pair = (parts[0].casefold().rstrip("-"), parts[1].casefold())
        multiword_brand = MULTIWORD_BRANDS.get(pair)
        if multiword_brand:
            return multiword_brand, " ".join(parts[2:])

    first = parts[0].casefold()
    if first not in KNOWN_BRANDS:
        return None

    return parts[0], " ".join(parts[1:])
