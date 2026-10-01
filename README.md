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
- 🛒 Закупка
- 🧰 Работы
- 📄 Расчёты
- 🔔 Цены

Команды остаются резервным интерфейсом: `/start`, `/catalog`, `/search`, `/garage`, `/garage_add`.

Бот понимает обычные запросы:

```text
передние колодки
масляный фильтр подешевле
амортизаторы срочно
GDB1956
```

Слова вроде «подешевле» и «срочно» автоматически переключают сортировку. Выдача хранит до 20 вариантов и листается по 5 деталей inline-кнопками; сортировка сохраняется при переходе между страницами.

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

В demo-справочнике есть несколько модификаций BMW X3 G01, Toyota Camry XV70 и Volkswagen Tiguan II.

### Внешний VIN / vehicle API

Добавлен отдельный `VehicleResolver`. Если при добавлении автомобиля указан VIN и внешний resolver включён, бот сначала сохраняет пользовательские данные, затем пытается уточнить автомобиль через HTTPS API. При недоступном API гараж всё равно остаётся рабочим; обновление применяется только для валидного `resolved`-ответа.

Пример запроса:

```text
GET /vehicle/vin?vin=WBA...
```

Поддерживаемый ответ:

```json
{
  "status": "resolved",
  "brand": "BMW",
  "model": "X3 G01",
  "year": 2020,
  "generation_code": "G01",
  "engine": "B47D20",
  "fuel": "diesel",
  "drive": "xDrive",
  "power_hp": 190,
  "modification_key": "bmw_x3_g01_20d_xdrive",
  "source": "partner-catalog"
}
```

Настройка:

```env
VEHICLE_API_ENABLED=true
VEHICLE_API_BASE_URL=https://vehicle.example.com
VEHICLE_API_VIN_PATH=/vehicle/vin
VEHICLE_API_KEY=...
```

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
- ведёт health-метрики по каждому provider;
- открывает circuit breaker после серии ошибок и временно перестаёт дергать нестабильный источник;
- группирует предложения по `brand + article`;
- ранжирует детали отдельно от коммерческих предложений;
- затем накладывает fitment status.

Команда `/status` показывает безопасный runtime-статус источников: `healthy / degraded / open`, число успешных/ошибочных вызовов, latency и оставшийся cooldown. URL и ключи не выводятся.

Circuit breaker настраивается:

```env
PROVIDER_CIRCUIT_FAILURE_THRESHOLD=3
PROVIDER_CIRCUIT_COOLDOWN_SECONDS=60
```

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

## Закупка и оптимизация заказа

Из карточки детали можно добавить позицию в постоянный список закупки. Список хранится в БД и поддерживает количество, удаление и повторный расчёт по актуальным предложениям.

Команда:

```text
/shopping
```

или кнопка «🛒 Закупка».

После обновления цен бот строит несколько стратегий:

- минимум цены по каждой позиции;
- самая быстрая сборка;
- всё в одном магазине, если один provider покрывает весь список;
- общий оптимум с учётом цены деталей и оценочной доставки.

Стоимость доставки имеет общий fallback:

```env
PROCUREMENT_SHIPPING_FEE=500
PROCUREMENT_FREE_SHIPPING_THRESHOLD=10000
```

Для известных providers можно задать собственные коммерческие правила одной JSON-настройкой:

```env
PROCUREMENT_PROVIDER_RULES_JSON={"Exist":{"shipping_fee":"350","free_threshold":"7000"},"Partner API":{"shipping_fee":"0","free_threshold":"0"}}
```

Если для provider есть правило, optimizer использует его; иначе применяется общий fallback. В карточке плана отдельно показываются стоимость деталей, оценочная доставка, итог, число магазинов и максимальный срок.

Если внешний provider возвращает поле `url`, бот показывает deeplink-кнопку на конкретное предложение. Ссылки принимаются только с HTTP/HTTPS scheme.

## Подбор по списку работ

Команда:

```text
/works
```

или кнопка «🧰 Работы».

Поддерживаются типовые пакеты, например:

- замена масла;
- базовое ТО;
- передние тормоза;
- свечи зажигания.

Также можно написать свободный список:

```text
замена масла, салонный фильтр, передние тормоза
```

Resolver раскладывает работы на поисковые позиции, учитывает базовое количество (например, два передних диска), выполняет поиск для активного автомобиля и добавляет найденные детали в список закупки. После этого пользователь может сразу запустить оптимизацию по магазинам.

Важно: подбор по работам не заменяет окончательную техническую проверку применимости. Перед покупкой критичные позиции должны иметь подтверждённый fitment status.

## Сохранённые расчёты

Выбранный план закупки можно сохранить кнопкой «💾 Сохранить расчёт». Сохраняется snapshot:

- состав позиций;
- выбранные providers;
- цены на момент расчёта;
- оценочная доставка;
- итоговая сумма;
- deeplink URL, если provider их передал.

Snapshot не меняется вслед за текущей корзиной или новыми ценами. Это позволяет сравнивать старый расчёт с новым.

В сохранённом расчёте есть «🔄 Пересчитать сейчас»: бот повторно запрашивает те же артикулы, строит актуальный оптимальный план и показывает изменение суммы, числа магазинов и срока. Исходный snapshot не изменяется; новый результат можно сохранить отдельным расчётом. Если хотя бы одна позиция сейчас недоступна, сравнение итоговой суммы не выполняется, чтобы неполный заказ не выглядел искусственно дешевле.

Открыть историю:

```text
/quotes
```

или кнопкой «📄 Расчёты».

## Заказы и checkout

Расчёт и заказ разделены:

- **расчёт** — snapshot цены и состава;
- **заказ** — отдельный lifecycle с повторной проверкой наличия, checkout по supplier-группам и audit trail.

Открыть заказы:

```text
/orders
```

или кнопкой «📦 Заказы».

Заказ можно создать из текущего плана закупки или сохранённого расчёта. После создания он имеет статус `draft` и ещё ничего не отправляет внешнему поставщику.

Перед оформлением пользователь запускает повторную проверку. Для каждой позиции бот ищет тот же артикул у того же provider и проверяет:

- наличие;
- актуальную цену;
- срок;
- deeplink.

Возможные промежуточные состояния:

```text
draft
ready
price_changed
needs_attention
checkout_pending
awaiting_manual_checkout
partially_placed
placed
completed
```

Если цена изменилась, заказ переходит в `price_changed`. Пользователь должен отдельно подтвердить новые цены. Если позиция отсутствует, checkout блокируется статусом `needs_attention`.

Только отдельная кнопка «🚀 Перейти к оформлению» запускает checkout. Создание заказа, revalidation и просмотр заказа не создают внешних заказов.

### Checkout adapters

Для provider без order API используется deeplink fallback. Supplier-группа получает `manual_required`, а пользователь переходит в магазин и затем может отметить «Я оформил».

Для provider с B2B/order API есть generic HTTPS adapter:

```env
CHECKOUT_API_ENABLED=true
CHECKOUT_API_PROVIDER_NAME=Partner API
CHECKOUT_API_BASE_URL=https://partner.example.com
CHECKOUT_API_CREATE_PATH=/orders
CHECKOUT_API_STATUS_PATH=/orders/{external_order_id}
CHECKOUT_API_KEY=...
CHECKOUT_API_TIMEOUT_SECONDS=10
```

Создание checkout передаёт idempotency key вида:

```text
zap:<order_id>:<supplier_group_id>
```

Adapter принимает `external_order_id`, `checkout_url` и provider status. HTTP вызовы ограничены timeout; `external_order_id` безопасно экранируется при подстановке в status URL.

Один пользовательский заказ может одновременно содержать:

- группу, оформленную через API;
- группу с ручным deeplink;
- группу, которая требует внимания.

Поэтому статус хранится и на уровне общего заказа, и отдельно по каждому provider.

### Audit trail

В БД сохраняются события:

- создание заказа;
- revalidation;
- изменение общего статуса;
- изменение supplier status;
- ручное подтверждение оформления.

Повторный polling того же статуса не создаёт дубликаты событий.

### Order status worker

Для внешних API-заказов есть отдельный worker:

```bash
python -m app.order_worker
```

Настройки:

```env
ORDER_STATUS_MONITOR_ENABLED=true
ORDER_STATUS_INTERVAL_SECONDS=300
```

Worker проверяет только заказы, в которых есть `external_order_id`, и отправляет Telegram-уведомление только при реальном изменении общего статуса. Ручные deeplink-заказы автоматически не помечаются оформленными.

## История цены

При пользовательском поиске, открытии каталога и пересчёте закупки бот сохраняет commercial observations для конкретного `provider + brand + article`.

Одинаковая подряд цена с тем же сроком не создаёт новую точку, поэтому таблица хранит изменения, а не каждый повторный запрос.

Из карточки детали доступна кнопка «📈 История цены». Она показывает по каждому provider:

- последнюю наблюдаемую цену;
- направление и процент изменения относительно самого старого доступного наблюдения;
- минимальную/максимальную цену;
- количество накопленных точек.

Это история наблюдений самого бота, а не официальная биржевая или магазинная история цен.

## Price alerts

Кнопка «🔔 Следить» сначала предлагает порог: текущая цена, −5%, −10% или −20%. После выбора создаётся отдельный alert для конкретного артикула и автомобиля.

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

## История, избранное и пользовательское состояние

Локально состояние хранится в SQLite, production-compose использует PostgreSQL.

В БД сохраняются:

- последние запросы;
- избранные артикулы;
- несколько автомобилей;
- выбранная модификация;
- price alerts;
- постоянный список закупки и количество позиций.

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

## Observability

Приложение пишет структурированные JSON-логи в stdout. Логируются:

- startup и выбранный runtime;
- открытие/recovery circuit breaker;
- provider failures без пользовательского запроса;
- запуск и ошибки price-alert worker;
- старт polling/webhook runtime.

Поля с `token`, `secret`, `authorization`, `api_key` и VIN автоматически редактируются как `***`.

Уровень:

```env
LOG_LEVEL=INFO
```


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
├── db.py                 SQLAlchemy persistence / order state
├── domain.py             domain models
├── vehicle_parser.py     brand/model parsing
├── vehicle_catalog.py    generation resolver
├── vehicle_resolver.py   demo modification resolver
├── vehicle_resolution.py vehicle resolver contract
├── external_vehicle.py   generic HTTPS VIN resolver
├── catalog.py            parts category tree
├── fitment.py            fitment contract + demo catalog
├── external_fitment.py   generic HTTP fitment adapter
├── providers.py          provider contract + demo market
├── external_provider.py  generic HTTP price/stock adapter
├── bootstrap.py          shared provider/service bootstrap
├── cache_backend.py      memory/Redis search cache
├── rate_limit.py         memory/Redis request limiting
├── middleware.py         Telegram middleware
├── search_service.py     aggregation/cache/timeout/ranking
├── service_kits.py       service kits
├── work_orders.py        work list → parts resolver
├── procurement.py        multi-store purchase optimizer
├── orders.py             order lifecycle / revalidation / checkout orchestration
├── checkout.py           deeplink + generic HTTPS checkout adapters
├── commercial_rules.py   provider-specific delivery rules
├── price_history.py      price trend summaries
├── price_alerts.py       price monitoring logic
├── alert_worker.py       reusable alert worker loop
├── worker.py             standalone price-alert process
├── order_monitor.py      external order status monitoring
├── order_worker.py       standalone order-status process
├── health.py             DB/Redis readiness
├── db_init.py            schema initialization process
└── observability.py      JSON logging + secret redaction
```

## Миграции БД

Схема теперь управляется Alembic. `init_db()` выполняет `upgrade head`, поэтому одинаковый механизм используется локально, в CI и в `db-init` production-container.

Текущий Alembic head:

```text
20261001_0002
```

Revisions:

```text
20261001_0001  baseline существующей схемы
20261001_0002  orders / supplier groups / order lines / audit events
```

Первый revision сделан idempotent для перехода со старого `create_all`-режима:

- на чистой БД создаёт всю текущую схему;
- на существующей схеме не пересоздаёт таблицы;
- добавляет недостающие поля старой `garage_vehicles`;
- после schema upgrade выполняется legacy data migration автомобиля.

Baseline содержит замороженное описание схемы и не импортирует текущие ORM-модели, поэтому будущие изменения должны оформляться отдельными Alembic revisions.

## Production deployment: PostgreSQL + Redis

Для локальной разработки по-прежнему достаточно:

```bash
docker compose up -d --build
```

Этот режим использует SQLite, in-memory cache/rate limiting и embedded price-alert worker.

Для серверного режима добавлен отдельный topology:

```text
PostgreSQL ─┐
            ├─ db-init ─→ bot
Redis ──────┤             ├─→ price worker
            └─────────────└─→ order-status worker
```

Запуск:

```bash
cp .env.production.example .env
# заполнить BOT_TOKEN, POSTGRES_PASSWORD и реальные API credentials

docker compose -f docker-compose.prod.yml up -d --build
```

В `docker-compose.prod.yml`:

- `postgres` — постоянное пользовательское состояние;
- `redis` — общий search cache и rate limiting;
- `db-init` — инициализирует схему до запуска приложений;
- `bot` — Telegram polling/webhook процесс;
- `worker` — независимая проверка price alerts;
- `order-worker` — polling внешних order API и уведомления о смене статуса.

Production compose автоматически выставляет:

```env
SEARCH_CACHE_BACKEND=redis
RATE_LIMIT_BACKEND=redis
PRICE_ALERT_WORKER_MODE=external
```

Bot и worker-процессы используют общую PostgreSQL/Redis инфраструктуру. Price worker отвечает только за price alerts, order-worker — только за внешние статусы заказов.

### Redis cache

Search cache имеет два backend-а:

```env
SEARCH_CACHE_BACKEND=memory
# или
SEARCH_CACHE_BACKEND=redis
REDIS_URL=redis://redis:6379/0
```

Cache key учитывает автомобиль, модификацию и нормализованный запрос. Redis payload содержит только коммерческие offers; применимость накладывается после чтения кэша.

### Rate limiting

Telegram messages и callbacks проходят общий middleware:

```env
RATE_LIMIT_BACKEND=memory
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60
```

В production используется Redis backend, поэтому лимит общий для нескольких экземпляров приложения.

### Price worker

Локально:

```env
PRICE_ALERT_WORKER_MODE=embedded
```

На сервере:

```env
PRICE_ALERT_WORKER_MODE=external
```

и запускается:

```bash
python -m app.worker
```

Это исключает двойную проверку одних и тех же alerts при горизонтальном масштабировании Telegram-процесса.

### Health / readiness

Webhook HTTP server предоставляет:

```text
GET /healthz  — процесс жив
GET /readyz   — доступны БД и Redis
```

`/readyz` возвращает HTTP 503, если критичная инфраструктура недоступна.

Команда Telegram `/status` также показывает DB/Redis readiness, backend кэша, worker mode и health каждого provider без вывода credentials.

## CI

GitHub Actions выполняет:

```text
compileall
import smoke
SQLite schema smoke
PostgreSQL schema smoke
Alembic revision check
Redis cache roundtrip
production bootstrap
pytest
Docker build
```

Отдельно проверяются upgrade старой схемы гаража, Alembic head `0002`, shopping list, procurement optimizer, work resolver, order lifecycle, checkout fallback, rate limiting и production-compose topology.

## Что пока не production-ready

Основные оставшиеся внешние зависимости:

1. credentials и контракт реального VIN/vehicle catalog для уже готового adapter-а;
2. лицензированный production-источник применимости;
3. credentials и контракт первого настоящего магазина/дистрибьютора;
4. реальные deeplink/affiliate URL и подтверждённые коммерческие правила поставщиков;
5. credentials и реальные checkout/order API конкретных providers для уже готового adapter-а;
6. внешние metrics/error reporting и production dashboards.

Следующая рабочая цепочка уже поддержана архитектурой:

```text
VIN / модель
→ точная модификация
→ OE / cross
→ fitment status
→ цены и наличие нескольких providers
→ карточка детали
→ список закупки / работы
→ оптимизация по магазинам
→ сохранённый расчёт
→ order draft
→ revalidation цены/наличия
→ API checkout / deeplink
→ status monitoring
```
