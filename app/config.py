from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    bot_token: str = Field(alias="BOT_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")
    admin_ids: Annotated[tuple[int, ...], NoDecode] = Field(alias="ADMIN_IDS")
    challenge_group_id: int = Field(alias="CHALLENGE_GROUP_ID")
    report_topic_id: int = Field(alias="REPORT_TOPIC_ID")
    daily_list_topic_id: int | None = Field(default=None, alias="DAILY_LIST_TOPIC_ID")
    timezone: str = Field(default="Europe/Moscow", alias="TIMEZONE")
    daily_close_time: str = Field(default="01:00", alias="DAILY_CLOSE_TIME")
    penalty_step_rub: int = Field(default=500, alias="PENALTY_STEP_RUB")
    entry_fee_rub: int = Field(default=500, alias="ENTRY_FEE_RUB")
    payment_bank: str = Field(default="Название банка", alias="PAYMENT_BANK")
    payment_phone: str = Field(default="PHONE_PLACEHOLDER", alias="PAYMENT_PHONE")
    payment_recipient: str = Field(default="Получатель перевода", alias="PAYMENT_RECIPIENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: object) -> tuple[int, ...]:
        if isinstance(value, str):
            parsed = tuple(int(part.strip()) for part in value.split(",") if part.strip())
        else:
            parsed = tuple(value)  # type: ignore[arg-type]
        if len(parsed) != 2:
            raise ValueError("ADMIN_IDS must contain exactly 2 Telegram user IDs")
        return parsed


@lru_cache
def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
