# Payment Processing Service

Асинхронный сервис процессинга платежей.

## Архитектура

- **API** (FastAPI) — приём запросов на оплату
- **Outbox Publisher** — гарантированная публикация событий в RabbitMQ
- **Consumer** — обработка платежей с эмуляцией внешнего шлюза
- **PostgreSQL** — хранение данных
- **RabbitMQ** — брокер сообщений с retry и Dead Letter Queue

## Запуск

```bash
docker-compose up --build
```

## API

Аутентификация: заголовок `X-API-Key: secret-api-key`

### Создание платежа

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "X-API-Key: secret-api-key" \
  -H "Idempotency-Key: $(uuidgen)" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 100.50,
    "currency": "RUB",
    "description": "Test payment",
    "metadata": {"order_id": "123"},
    "webhook_url": "https://example.com/webhook"
  }'
```

Ответ: `202 Accepted`
```json
{
  "payment_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "created_at": "2026-07-31T23:00:00+00:00"
}
```

### Получение платежа

```bash
curl http://localhost:8000/api/v1/payments/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: secret-api-key"
```

## RabbitMQ Management

http://localhost:15672 (guest/guest)
