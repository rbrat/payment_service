# Async Payment Processing Service

Асинхронный микросервис для обработки платежей на базе FastAPI, PostgreSQL, RabbitMQ.

## Архитектура

```
Client -> POST /api/v1/payments
           |
         API (FastAPI)
           | сохраняет Payment + OutboxEvent в PostgreSQL
           |
    Outbox Publisher (фоновая задача Consumer)
           | читает OutboxEvent, публикует в RabbitMQ
           |
    Consumer (обрабатывает сообщение из payments.new)
           | эмулирует шлюз (2-5с, 90% успех)
           | обновляет статус в БД
           | отправляет webhook (3 попытки с backoff)
           | при неудаче → Dead Letter Queue (payments.dlq)
```

## Стек технологий

- **FastAPI** + **Pydantic v2** — REST API
- **SQLAlchemy 2.0** (async) — ORM
- **PostgreSQL** — база данных
- **RabbitMQ** + **aio-pika** — брокер сообщений
- **Alembic** — миграции БД
- **Docker** + **docker-compose** — оркестрация

## Быстрый старт

### 1. Клонировать/распаковать проект

```bash
cd payment_service
```

### 2. Запустить через Docker Compose

```bash
docker-compose up --build
```

Это автоматически:
- Поднимет PostgreSQL и RabbitMQ
- Применит миграции Alembic
- Запустит API на порту `8000`
- Запустит Consumer

### 3. Проверить работу

API доступен: http://localhost:8000  
Swagger UI: http://localhost:8000/docs  
RabbitMQ Management: http://localhost:15672 (guest/guest)

## API эндпоинты

Все запросы требуют заголовок `X-API-Key: secret-api-key`.

### Создать платёж

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: secret-api-key" \
  -H "Idempotency-Key: unique-key-123" \
  -d '{
    "amount": "100.00",
    "currency": "RUB",
    "description": "Test payment",
    "metadata": {"order_id": "order-42"},
    "webhook_url": "https://webhook.site/your-token"
  }'
```

Ответ `202 Accepted`:
```json
{
  "payment_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2026-03-30T12:00:00Z"
}
```

### Получить информацию о платеже

```bash
curl http://localhost:8000/api/v1/payments/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: secret-api-key"
```

Ответ:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": "100.00",
  "currency": "RUB",
  "description": "Test payment",
  "metadata": {"order_id": "order-42"},
  "status": "succeeded",
  "idempotency_key": "unique-key-123",
  "webhook_url": "https://webhook.site/your-token",
  "created_at": "2026-03-30T12:00:00Z",
  "processed_at": "2026-03-30T12:00:04Z"
}
```

### Проверка идемпотетности

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: secret-api-key" \
  -H "Idempotency-Key: unique-key-123" \
  -d '{
    "amount": "228.00",
    "currency": "RUB",
    "description": "Test idempotency",
    "metadata": {"order_id": "should return payment_id 550e8400-e29b-41d4-a716-446655440000"},
    "webhook_url": "https://webhook.site/your-token"
  }'
```
Ответ `202 Accepted`:
```json
{
  "payment_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2026-03-30T12:00:00Z"
}
```


## Ключевые решения

### Outbox Pattern
При создании платежа в рамках **одной транзакции** записываются:
1. Запись в таблицу `payments`
2. Событие в таблицу `outbox` (published=false)

Фоновая задача в consumer раз в секунду читает неопубликованные события и публикует их в RabbitMQ. Это гарантирует, что событие будет доставлено, даже если RabbitMQ был недоступен в момент создания платежа.

### Idempotency Key
При повторном запросе с тем же `Idempotency-Key` API вернёт уже существующий платёж без создания дубликата.

### Dead Letter Queue
Очередь `payments.new` настроена с `x-delivery-limit: 3`. После 3 неудачных попыток сообщение автоматически роутится в `payments.dlq`.

### Webhook Retry
При ошибке отправки webhook выполняется до 3 попыток с экспоненциальной задержкой (1с, 2с, 4с).

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@postgres:5432/payments` | URL подключения к БД |
| `RABBITMQ_URL` | `amqp://guest:guest@rabbitmq:5672/` | URL подключения к RabbitMQ |
| `API_KEY` | `secret-api-key` | Статический API ключ |

## Структура проекта

```
payment_service/
  app/
    api/v1/payments.py      # REST эндпоинты
    core/
      config.py           # Настройки (pydantic-settings)
      security.py         # Проверка API ключа
    db/base.py              # SQLAlchemy engine и сессия
    models/
      payment.py          # ORM модель Payment
      outbox.py           # ORM модель OutboxEvent
    schemas/payment.py      # Pydantic схемы
    services/payment_service.py  # Бизнес-логика
    main.py                 # FastAPI приложение
  consumer/
    consumer.py             # RabbitMQ consumer + outbox publisher
  migrations/
    versions/0001_initial.py
    env.py
  Dockerfile
  Dockerfile.consumer
  docker-compose.yml
  alembic.ini
  requirements.txt
  requirements.consumer.txt
  README.md
```
