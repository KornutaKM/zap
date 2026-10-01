# Zap — Telegram-бот для подбора автозапчастей

Zap — обычный Telegram-бот без Mini App. Пользователь выбирает автомобиль, открывает каталог или пишет деталь своими словами, а backend разделяет три независимых задачи:

```text
автомобиль → применимость → коммерческие предложения
```

Это важно: цена магазина сама по себе не считается подтверждением совместимости.

## Что уже реализовано

### Telegram UX

Главное меню:

- 🔎 Найти запчасть
- 📚 Каталог
- 🛠 ТО и обслуживание
- 🚗 Мой автомобиль
- ⭐ Избранное
- 🕘 История
- 🔔 Цены

Команды остаются резервным интерфейсом: `/start`, `/catalog`, `/search`, `/garage`, `/garage_add`.

Бот понимает обычные запросы:

```text
передние колодки
масляный фильтр подешевле
амортизаторы срочно
GDB1956
```

Слова вроде «подешевле» и «срочно» автоматически переключают сортировку.

## Автомобиль и модификация

Гараж поддерживает несколько автомобилей. Можно:

- добавлять автомобили;
- переключать активный;
- удалять;
- уточнять модификацию.

Базовые данные:

```text
марка
модель
год
VIN (опционально)
```

После этого отдельный resolver может уточнить:

```text
поколение
двигатель
топливо
привод
мощность
modification_key
```

В demo-справочнике есть несколько модификаций BMW X3 G01, Toyota Camry XV70 и Volkswagen Tiguan II. Это именно демонстрационный resolver, а не VIN decoder.

Старая SQLite-схема мигрируется автоматически: новые поля добавляются без удаления существующих автомобилей. В CI есть отдельный regression-test, который создаёт старую таблицу и проверяет upgrade.

## Каталог применимости: OE и cross-reference

Применимость вынесена в отдельный слой.

Статусы:

- ✅ `confirmed` — подтверждено каталогом по модификации;
- 🟡 `probable` — совпала модель/поколение, но не вся модификация;
- ⚪ `unverified` — подтверждения нет.

Карточка детали показывает статус, OE-reference, причину статуса и предложения магазинов.

Demo-fitment можно полностью отключить:

```env
DEMO_FITMENT_ENABLED=false
```

### Внешний fitment API

Есть универсальный HTTPS-adapter. Он ожидает GET endpoint, например:

```text
GET /fitment/resolve
?query=масляный+фильтр
&brand=BMW
&model=X3+G01
&year=2020
&generation=G01
&engine=B47D20
&drive=xDrive
&modification_key=bmw_x3_g01_20d_xdrive
```

Ожидаемый JSON:

```json
{
  "status": "confirmed",
  "oe_numbers": ["34116889570"],
  "crosses": [
    {"brand": "ATE", "article": "13.0460-7184.2"},
    {"brand": "TRW", "article": "GDB1956"}
  ],
  "reason": "Matched by vehicle modification"
}
```

Конфигурация:

```env
FITMENT_API_ENABLED=true
FITMENT_API_BASE_URL=https://catalog.example.com
FITMENT_API_RESOLVE_PATH=/fitment/resolve
FITMENT_API_KEY=...
FITMENT_API_KEY_HEADER=Authorization
FITMENT_API_AUTH_SCHEME=Bearer
DEMO_FITMENT_ENABLED=false
```

HTTP по умолчанию запрещён; adapter требует HTTPS.

## Предложения магазинов

`PartsSearchService`:

- опрашивает providers параллельно;
- ставит timeout на каждый источник;
- использует TTL-кэш;
- переживает падение одного provider;
- группирует предложения по `brand + article`;
- ранжирует детали отдельно от коммерческих предложений;
- затем накладывает fitment status.

Demo-market имитирует Exist / Autodoc / Emex, но его можно выключить:

```env
DEMO_PROVIDER_ENABLED=false
```

### Внешний price/stock API

Универсальный HTTPS provider принимает GET запрос:

```text
GET /search
?query=GDB1956
&brand=BMW
&model=X3+G01
&year=2020
&engine=B47D20
&drive=xDrive
```

Поддерживаемый ответ:

```json
{
  "items": [
    {
      "provider": "Partner warehouse",
      "brand": "TRW",
      "article": "GDB1956",
      "title": "Brake pad set",
      "price": "6890.00",
      "delivery_days": 2,
      "quality": 0.9,
      "url": "https://example.com/item/GDB1956",
      "in_stock": true
    }
  ]
}
```

Настройка:

```env
EXTERNAL_PROVIDER_ENABLED=true
EXTERNAL_PROVIDER_NAME=Partner API
EXTERNAL_PROVIDER_BASE_URL=https://partner.example.com
EXTERNAL_PROVIDER_SEARCH_PATH=/search
EXTERNAL_PROVIDER_API_KEY=...
EXTERNAL_PROVIDER_API_KEY_HEADER=Authorization
EXTERNAL_PROVIDER_AUTH_SCHEME=Bearer
DEMO_PROVIDER_ENABLED=false
```

## Карточка детали

Показывает:

- бренд и артикул;
- название;
- статус применимости;
- OE-reference;
- минимальную цену;
- предложения магазинов и сроки.

Из карточки можно:

- добавить в избранное;
- включить отслеживание цены;
- вернуться к выдаче;
- начать новый поиск.

## Price alerts

Кнопка «🔔 Следить» создаёт порог по умолчанию на 5% ниже текущей цены.

Worker:

1. периодически запрашивает актуальные предложения;
2. сравнивает минимальную цену с порогом;
3. отправляет сообщение пользователю;
4. только после успешной доставки отключает alert.

Параметры:

```env
PRICE_ALERTS_ENABLED=true
PRICE_ALERT_INTERVAL_SECONDS=3600
PRICE_ALERT_DROP_PERCENT=5
```

Активные alerts можно посмотреть и удалить из меню «🔔 Цены».

## ТО и комплекты

Есть demo-наборы:

- Базовое ТО;
- Расширенное ТО;
- Передние тормоза.

Позиции комплекта ищутся параллельно. Бот показывает состав, ориентировочную общую стоимость и максимальный срок.

## История и избранное

SQLite хранит:

- последние запросы;
- избранные артикулы;
- несколько автомобилей;
- выбранную модификацию;
- price alerts.

Из истории и избранного можно повторно запустить поиск и получить свежие предложения.

## Polling и webhook

По умолчанию:

```env
BOT_RUN_MODE=polling
```

Для production можно переключить на webhook:

```env
BOT_RUN_MODE=webhook
WEBHOOK_URL=https://bot.example.com/webhook
WEBHOOK_PATH=/webhook
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8080
WEBHOOK_SECRET_TOKEN=change-me
```

Webhook mode использует `SimpleRequestHandler`, secret token и endpoint `/healthz`. Сервер начинает слушать порт до вызова Telegram `setWebhook`.

## Запуск

Python 3.12+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
python -m app.main
```

## Docker

```bash
cp .env.example .env
# заполнить BOT_TOKEN

docker compose up -d --build
```

SQLite хранится в `./data`.

В webhook mode compose публикует `WEBHOOK_PORT` (по умолчанию 8080). Перед контейнером рекомендуется reverse proxy с HTTPS.

## Архитектура

```text
app/
├── main.py               Telegram handlers / orchestration
├── ui.py                 reply + inline UI
├── runtime.py            polling / webhook
├── db.py                 SQLite / SQLAlchemy + additive migrations
├── domain.py             domain models
├── vehicle_parser.py     brand/model parsing
├── vehicle_catalog.py    generation resolver
├── vehicle_resolver.py   modification resolver
├── catalog.py            parts category tree
├── fitment.py            fitment contract + demo catalog
├── external_fitment.py   generic HTTP fitment adapter
├── providers.py          provider contract + demo market
├── external_provider.py  generic HTTP price/stock adapter
├── search_service.py     aggregation/cache/timeout/ranking
├── service_kits.py       service kits
└── price_alerts.py       price monitoring logic
```

## CI

GitHub Actions выполняет:

```text
compileall
import smoke test
clean database smoke test
pytest
Docker build
```

Отдельным тестом проверяется upgrade старой схемы гаража.

## Что пока не production-ready

Основные оставшиеся внешние зависимости:

1. реальный VIN decoder / vehicle catalog;
2. лицензированный источник применимости;
3. credentials и контракт первого настоящего магазина/дистрибьютора;
4. реальные deeplink/affiliate URL;
5. PostgreSQL/Redis при росте нагрузки;
6. observability: structured logs, metrics, error reporting.

Следующая рабочая цепочка уже поддержана архитектурой:

```text
VIN / модель
→ точная модификация
→ OE / cross
→ fitment status
→ цены и наличие нескольких providers
→ карточка детали
→ price alert / переход в магазин
```
