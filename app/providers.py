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
                ("ATE", "13.0460-7184.2", "Комплект тормозных колодок", "8600", 2, .95),
                ("TRW", "GDB1956", "Комплект тормозных колодок", "6900", 3, .90),
                ("Brembo", "P06089", "Комплект тормозных колодок", "7800", 1, .94),
                ("Stellox", "0000870SX", "Комплект тормозных колодок", "4200", 4, .60),
            ]
        elif "тормозн" in q and "диск" in q:
            data = [
                ("Zimmermann", "150.3497.20", "Тормозной диск", "9200", 2, .95),
                ("Brembo", "09.C394.13", "Тормозной диск", "8700", 1, .94),
                ("ATE", "24.0124-0237.1", "Тормозной диск", "9900", 3, .96),
                ("TRW", "DF6508", "Тормозной диск", "7600", 2, .89),
            ]
        elif "маслян" in q and "фильтр" in q:
            data = [
                ("MANN-FILTER", "HU816X", "Масляный фильтр", "1450", 1, .96),
                ("Mahle", "OX404D", "Масляный фильтр", "1320", 2, .95),
                ("Bosch", "F026407123", "Масляный фильтр", "1190", 3, .90),
                ("Filtron", "OE672/2", "Масляный фильтр", "860", 2, .82),
            ]
        elif "воздуш" in q and "фильтр" in q:
            data = [
                ("MANN-FILTER", "C30005", "Воздушный фильтр", "1900", 2, .96),
                ("Mahle", "LX2046", "Воздушный фильтр", "1720", 3, .94),
                ("Bosch", "1457433714", "Воздушный фильтр", "1510", 1, .90),
            ]
        elif "салон" in q and "фильтр" in q:
            data = [
                ("MANN-FILTER", "CUK23014", "Салонный фильтр", "2100", 1, .96),
                ("Mahle", "LAK675", "Салонный фильтр", "1980", 2, .94),
                ("Filtron", "K1311A", "Салонный фильтр", "1490", 2, .84),
            ]
        elif "топлив" in q and "фильтр" in q:
            data = [
                ("MANN-FILTER", "WK5008", "Топливный фильтр", "4300", 2, .96),
                ("Mahle", "KL169/4D", "Топливный фильтр", "3990", 3, .94),
                ("Bosch", "F026402836", "Топливный фильтр", "3650", 1, .90),
            ]
        elif "свеч" in q:
            data = [
                ("NGK", "97506", "Свеча зажигания", "2200", 1, .97),
                ("Bosch", "0242145515", "Свеча зажигания", "1950", 2, .93),
                ("Denso", "IKH20TT", "Свеча зажигания", "1680", 3, .91),
            ]
        elif "амортиз" in q:
            data = [
                ("Sachs", "318204", "Амортизатор", "11400", 2, .96),
                ("Bilstein", "22-238245", "Амортизатор", "12800", 3, .97),
                ("KYB", "339763", "Амортизатор", "9800", 1, .90),
            ]
        elif "рычаг" in q or "стабилиз" in q:
            data = [
                ("Lemforder", "3890901", "Деталь подвески", "8400", 2, .97),
                ("TRW", "JTC1437", "Деталь подвески", "7200", 1, .91),
                ("Febi", "102763", "Деталь подвески", "5900", 3, .82),
            ]
        elif "подшипник" in q:
            data = [
                ("FAG", "713649560", "Ступичный подшипник", "9800", 2, .97),
                ("SKF", "VKBA6780", "Ступичный подшипник", "10300", 1, .96),
                ("SNR", "R150.48", "Ступичный подшипник", "8600", 3, .91),
            ]
        elif "помп" in q or "водяной насос" in q or "термостат" in q:
            data = [
                ("Pierburg", "7.02851.20.0", "Компонент системы охлаждения", "9700", 2, .96),
                ("Mahle", "TM14100", "Компонент системы охлаждения", "8200", 3, .93),
                ("Gates", "TH48297G1", "Компонент системы охлаждения", "6900", 1, .88),
            ]
        elif "аккумулятор" in q:
            data = [
                ("Varta", "A7", "Аккумулятор AGM", "18900", 1, .96),
                ("Bosch", "S5A08", "Аккумулятор AGM", "17600", 2, .94),
                ("Exide", "EK700", "Аккумулятор AGM", "15800", 2, .90),
            ]
        elif "генератор" in q or "стартер" in q:
            data = [
                ("Bosch", "0986048080", "Электрооборудование", "28500", 3, .95),
                ("Valeo", "440357", "Электрооборудование", "26400", 2, .93),
                ("AS-PL", "A3147PR", "Электрооборудование", "19800", 1, .82),
            ]
        else:
            article = query.strip().upper() if any(c.isdigit() for c in query) else "DEMO-001"
            data = [
                ("Bosch", article, query.strip().capitalize() or "Запчасть по запросу", "5400", 2, .90),
                ("Febi", "DEMO-002", query.strip().capitalize() or "Запчасть по запросу", "4100", 4, .80),
                ("OE", "DEMO-OE", query.strip().capitalize() or "Оригинальная запчасть", "8700", 3, .99),
            ]

        return [
            Offer(self.name, brand, article, title, Decimal(price), days, quality)
            for brand, article, title, price, days, quality in data
        ]


class ExistProvider(PartsProvider):
    name = "Exist"

    async def search(self, vehicle: Vehicle, query: str) -> list[Offer]:
        # TODO: подключить официальный API / партнёрский фид.
        return []


class AutodocProvider(PartsProvider):
    name = "Autodoc"

    async def search(self, vehicle: Vehicle, query: str) -> list[Offer]:
        # TODO: подключить официальный/партнёрский API.
        return []
