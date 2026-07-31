from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payments"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    API_KEY: str = "secret-api-key"

    EXCHANGE_NAME: str = "payments"
    QUEUE_NAME: str = "payments.new"
    ROUTING_KEY: str = "payments.new"
    DLQ_NAME: str = "payments.dlq"

    RETRY_QUEUES: list[str] = ["payments.retry.1s", "payments.retry.5s", "payments.retry.25s"]
    RETRY_DELAYS_MS: list[int] = [1000, 5000, 25000]
    MAX_RETRIES: int = 3

    PROCESSING_DELAY_MIN: float = 2.0
    PROCESSING_DELAY_MAX: float = 5.0
    SUCCESS_RATE: float = 0.9

    OUTBOX_POLL_INTERVAL: float = 1.0
    OUTBOX_BATCH_SIZE: int = 100

    WEBHOOK_TIMEOUT: float = 10.0


settings = Settings()
