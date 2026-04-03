from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@postgres:5432/payments")
    RABBITMQ_URL: str = Field(default="amqp://guest:guest@rabbitmq:5672/")
    API_KEY: str = Field(default="secret-api-key")

    PAYMENT_QUEUE: str = "payments.new"
    PAYMENT_DLQ: str = "payments.dlq"
    PAYMENT_EXCHANGE: str = "payments"
    WEBHOOK_RETRY_ATTEMPTS: int = 3

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra='allow')


settings = Settings()
