from datetime import date

import pytest

from app.db.models import ParticipantStatus
from app.scheduler import close_challenge_day, list_topic_id, recovery_days
from app.services.participants import accept_rules, upsert_registered_participant


def test_recovery_days_iterates_every_missing_past_day():
    assert recovery_days(date(2026, 10, 1), date(2026, 10, 4)) == [
        date(2026, 10, 1),
        date(2026, 10, 2),
        date(2026, 10, 3),
    ]


def test_recovery_days_skips_current_day():
    assert recovery_days(date(2026, 10, 4), date(2026, 10, 4)) == []


def test_list_topic_id_uses_none_for_main_chat():
    class SettingsStub:
        daily_list_topic_id = 1
        report_topic_id = 2

    assert list_topic_id(SettingsStub()) is None


def test_list_topic_id_prefers_forum_topic_above_one():
    class SettingsStub:
        daily_list_topic_id = 3
        report_topic_id = 2

    assert list_topic_id(SettingsStub()) == 3


def test_list_topic_id_falls_back_to_report_topic():
    class SettingsStub:
        daily_list_topic_id = None
        report_topic_id = 2

    assert list_topic_id(SettingsStub()) == 2


@pytest.mark.asyncio
async def test_close_day_unpins_previous_daily_list_before_pinning_new(db_session, challenge_day):
    challenge_day.list_message_chat_id = -1001
    challenge_day.list_message_thread_id = None
    challenge_day.list_message_id = 77
    bot = BotStub(next_message_id=88)

    await close_challenge_day(
        db_session,
        bot,
        SchedulerSettingsStub(),
        challenge_day.day,
        challenge_day.ends_at,
    )

    assert bot.calls == [
        ("unpin", -1001, 77),
        ("send", -1001, None, bot.calls[1][3], None),
        ("pin", -1001, 88),
    ]


@pytest.mark.asyncio
async def test_close_day_notifies_participant_after_removal_for_unpaid_debt(db_session, challenge_day):
    participant = await upsert_registered_participant(db_session, 123, None, "Участник А.")
    await accept_rules(db_session, participant, challenge_day.starts_at)
    participant.current_debt_rub = 500
    participant.debt_started_on = date(2026, 10, 1)
    bot = BotStub(next_message_id=88)

    await close_challenge_day(
        db_session,
        bot,
        SchedulerSettingsStub(),
        challenge_day.day,
        challenge_day.ends_at,
    )

    assert participant.status == ParticipantStatus.REMOVED
    assert ("ban", -1001, 123) in bot.calls
    assert ("unban", -1001, 123) not in bot.calls
    removal_messages = [
        call for call in bot.calls
        if call[0] == "send" and call[1] == 123 and "удалил тебя из группы" in call[3]
    ]
    assert len(removal_messages) == 1
    assert removal_messages[0][4] is not None


class SchedulerSettingsStub:
    timezone = "Europe/Moscow"
    daily_close_time = "01:00"
    penalty_step_rub = 500
    challenge_group_id = -1001
    report_topic_id = 2
    daily_list_topic_id = 1
    payment_bank = "Название банка"
    payment_phone = "PHONE_PLACEHOLDER"
    payment_recipient = "Получатель перевода"


class BotStub:
    def __init__(self, next_message_id):
        self.next_message_id = next_message_id
        self.calls = []

    async def unpin_chat_message(self, chat_id, message_id):
        self.calls.append(("unpin", chat_id, message_id))

    async def send_message(self, chat_id, text, message_thread_id=None, reply_markup=None):
        self.calls.append(("send", chat_id, message_thread_id, text, reply_markup))
        return SentMessageStub(self.next_message_id)

    async def pin_chat_message(self, chat_id, message_id, disable_notification=True):
        self.calls.append(("pin", chat_id, message_id))

    async def ban_chat_member(self, chat_id, user_id):
        self.calls.append(("ban", chat_id, user_id))

    async def unban_chat_member(self, chat_id, user_id, only_if_banned=True):
        self.calls.append(("unban", chat_id, user_id))


class SentMessageStub:
    def __init__(self, message_id):
        self.message_id = message_id
