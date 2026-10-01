from abc import ABC, abstractmethod
from decimal import Decimal
from app.domain import Offer, Vehicle

class PartsProvider(ABC):
    name: str

    @abstractmethod
    async def search(self, vehicle: Vehicle, query: str) -> list[Offer]:
        raise NotImplementedError

class MockProvider(PartsProvider):
    name = "DemoParts"

    async def search(self, vehicle: Vehicle, query: str) -> list[Offer]:
        q = query.casefold()
        if "колод" in q:
            data = [
                ("ATE", "13.0460-7184.2", "Тормозные колодки", "8600", 2, .95),
                ("TRW", "GDB1956", "Тормозные колодки", "6900", 3, .90),
                ("Brembo", "P06089", "Тормозные колодки", "7800", 1, .94),
                ("Stellox", "0000870SX", "Тормозные колодки", "4200", 4, .60),
            ]
        elif "фильтр" in q:
            data = [
                ("MANN-FILTER", "HU816X", "Масляный фильтр", "1450", 1, .96),
                ("Mahle", "OX404D", "Масляный фильтр", "1320", 2, .95),
                ("Bosch", "F026407123", "Масляный фильтр", "1190", 3, .90),
                ("Filtron", "OE672/2", "Масляный фильтр", "860", 2, .82),
            ]
        else:
            article = query.strip().upper() if any(c.isdigit() for c in query) else "DEMO-001"
            data = [
                ("Bosch", article, "Запчасть по запросу", "5400", 2, .90),
                ("Febi", "DEMO-002", "Запчасть по запросу", "4100", 4, .80),
                ("OE", "DEMO-OE", "Оригинальная запчасть", "8700", 3, .99),
            ]
        return [Offer(self.name, b, a, t, Decimal(p), d, ql) for b,a,t,p,d,ql in data]

class ExistProvider(PartsProvider):
    name = "Exist"
    async def search(self, vehicle: Vehicle, query: str) -> list[Offer]:
        # TODO: официальный API / партнёрский фид.
        return []

class AutodocProvider(PartsProvider):
    name = "Autodoc"
    async def search(self, vehicle: Vehicle, query: str) -> list[Offer]:
        # TODO: официальный/партнёрский API.
        return []
