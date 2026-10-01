from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class CatalogNode:
    id: str
    title: str
    parent: str | None
    children: tuple[str, ...] = ()
    query: str | None = None

CATALOG: dict[str, CatalogNode] = {
    "root": CatalogNode("root", "Каталог запчастей", None, (
        "service", "brakes", "suspension", "engine", "cooling", "electrics"
    )),
    "service": CatalogNode("service", "ТО и фильтры", "root", (
        "oil_filter", "air_filter", "cabin_filter", "fuel_filter", "spark_plugs"
    )),
    "brakes": CatalogNode("brakes", "Тормозная система", "root", (
        "front_pads", "rear_pads", "front_discs", "rear_discs", "wear_sensor"
    )),
    "suspension": CatalogNode("suspension", "Подвеска и рулевое", "root", (
        "front_shocks", "rear_shocks", "control_arms", "stabilizer_links", "wheel_bearings"
    )),
    "engine": CatalogNode("engine", "Двигатель", "root", (
        "drive_belt", "belt_tensioner", "engine_mount", "gaskets"
    )),
    "cooling": CatalogNode("cooling", "Охлаждение", "root", (
        "water_pump", "thermostat", "radiator", "coolant"
    )),
    "electrics": CatalogNode("electrics", "Электрика", "root", (
        "battery", "alternator", "starter", "sensors"
    )),

    "oil_filter": CatalogNode("oil_filter", "Масляный фильтр", "service", query="масляный фильтр"),
    "air_filter": CatalogNode("air_filter", "Воздушный фильтр", "service", query="воздушный фильтр"),
    "cabin_filter": CatalogNode("cabin_filter", "Салонный фильтр", "service", query="салонный фильтр"),
    "fuel_filter": CatalogNode("fuel_filter", "Топливный фильтр", "service", query="топливный фильтр"),
    "spark_plugs": CatalogNode("spark_plugs", "Свечи зажигания", "service", query="свечи зажигания"),

    "front_pads": CatalogNode("front_pads", "Передние колодки", "brakes", query="передние тормозные колодки"),
    "rear_pads": CatalogNode("rear_pads", "Задние колодки", "brakes", query="задние тормозные колодки"),
    "front_discs": CatalogNode("front_discs", "Передние тормозные диски", "brakes", query="передние тормозные диски"),
    "rear_discs": CatalogNode("rear_discs", "Задние тормозные диски", "brakes", query="задние тормозные диски"),
    "wear_sensor": CatalogNode("wear_sensor", "Датчики износа", "brakes", query="датчик износа колодок"),

    "front_shocks": CatalogNode("front_shocks", "Передние амортизаторы", "suspension", query="передние амортизаторы"),
    "rear_shocks": CatalogNode("rear_shocks", "Задние амортизаторы", "suspension", query="задние амортизаторы"),
    "control_arms": CatalogNode("control_arms", "Рычаги подвески", "suspension", query="рычаг подвески"),
    "stabilizer_links": CatalogNode("stabilizer_links", "Стойки стабилизатора", "suspension", query="стойка стабилизатора"),
    "wheel_bearings": CatalogNode("wheel_bearings", "Ступичные подшипники", "suspension", query="ступичный подшипник"),

    "drive_belt": CatalogNode("drive_belt", "Приводной ремень", "engine", query="приводной ремень"),
    "belt_tensioner": CatalogNode("belt_tensioner", "Натяжитель ремня", "engine", query="натяжитель ремня"),
    "engine_mount": CatalogNode("engine_mount", "Опоры двигателя", "engine", query="опора двигателя"),
    "gaskets": CatalogNode("gaskets", "Прокладки и уплотнения", "engine", query="прокладка двигателя"),

    "water_pump": CatalogNode("water_pump", "Помпа", "cooling", query="водяной насос помпа"),
    "thermostat": CatalogNode("thermostat", "Термостат", "cooling", query="термостат"),
    "radiator": CatalogNode("radiator", "Радиатор", "cooling", query="радиатор охлаждения"),
    "coolant": CatalogNode("coolant", "Охлаждающая жидкость", "cooling", query="охлаждающая жидкость"),

    "battery": CatalogNode("battery", "Аккумулятор", "electrics", query="аккумулятор"),
    "alternator": CatalogNode("alternator", "Генератор", "electrics", query="генератор"),
    "starter": CatalogNode("starter", "Стартер", "electrics", query="стартер"),
    "sensors": CatalogNode("sensors", "Датчики", "electrics", query="датчик"),
}

def get_node(node_id: str) -> CatalogNode | None:
    return CATALOG.get(node_id)

def get_children(node_id: str) -> list[CatalogNode]:
    node = CATALOG[node_id]
    return [CATALOG[child_id] for child_id in node.children]
