import pytest

from app.config import Settings


def test_settings_parses_admin_ids_from_csv():
    settings = Settings(
        _env_file=None,
        BOT_TOKEN="123:test",
        DATABASE_URL="postgresql+asyncpg://bot:bot@db:5432/bot",
        ADMIN_IDS="11, 22",
        CHALLENGE_GROUP_ID="-100123",
        REPORT_TOPIC_ID="7",
    )

    assert settings.admin_ids == (11, 22)
    assert settings.timezone == "Europe/Moscow"
    assert settings.daily_close_time == "01:00"
    assert settings.penalty_step_rub == 500
    assert settings.payment_bank == "Название банка"
    assert settings.payment_phone == "PHONE_PLACEHOLDER"
    assert settings.payment_recipient == "Получатель перевода"
    assert settings.entry_fee_rub == 500
    assert settings.daily_list_topic_id is None


def test_settings_requires_two_admins():
    with pytest.raises(ValueError, match="ADMIN_IDS must contain exactly 2"):
        Settings(
            _env_file=None,
            BOT_TOKEN="123:test",
            DATABASE_URL="postgresql+asyncpg://bot:bot@db:5432/bot",
            ADMIN_IDS="11",
            CHALLENGE_GROUP_ID="-100123",
            REPORT_TOPIC_ID="7",
        )


def test_settings_parses_admin_ids_from_environment(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123:test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://bot:bot@db:5432/bot")
    monkeypatch.setenv("ADMIN_IDS", "101,202")
    monkeypatch.setenv("CHALLENGE_GROUP_ID", "-100123")
    monkeypatch.setenv("REPORT_TOPIC_ID", "7")
    monkeypatch.setenv("DAILY_LIST_TOPIC_ID", "1")

    settings = Settings()

    assert settings.admin_ids == (101, 202)
    assert settings.daily_list_topic_id == 1
