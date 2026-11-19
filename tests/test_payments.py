from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from aiogram.exceptions import TelegramForbiddenError

from app.db.models import ParticipantStatus, PaymentPurpose, PaymentStatus
from app.handlers.payments import (
    _has_payment_proof,
    debt_payment_prompt_text,
    notify_admins_about_payment,
    payment_confirmed_text,
    entry_payment_confirmed_text,
    payment_blocking_message,
    payment_proof_received_text,
    payment_rejected_text,
    payment_review_text,
)
from app.keyboards.participant import PAY_DEBT_CALLBACK, pay_debt_keyboard
from app.services.participants import accept_rules, upsert_registered_participant
from app.services.payments import confirm_payment, create_payment_request, reject_payment


MSK = ZoneInfo("Europe/Moscow")


@pytest.mark.asyncio
async def test_confirm_payment_clears_debt(db_session):
    participant = await upsert_registered_participant(db_session, 123, None, "Участник А.")
    await accept_rules(db_session, participant, datetime(2026, 10, 4, 1, 0, tzinfo=MSK))
    participant.current_debt_rub = 1500
    participant.debt_started_on = date(2026, 10, 1)
    request = await create_payment_request(
        db_session,
        participant.id,
        123,
        77,
        datetime(2026, 10, 4, 12, 0, tzinfo=MSK),
    )

    decision = await confirm_payment(
        db_session,
        request.id,
        admin_id=11,
        handled_at=datetime(2026, 10, 4, 12, 5, tzinfo=MSK),
    )

    assert decision.changed is True
    assert request.status == PaymentStatus.CONFIRMED
    assert participant.current_debt_rub == 0
    assert participant.debt_started_on is None


@pytest.mark.asyncio
async def test_first_admin_payment_action_wins(db_session):
    participant = await upsert_registered_participant(db_session, 123, None, "Участник А.")
    request = await create_payment_request(
        db_session,
        participant.id,
        123,
        77,
        datetime(2026, 10, 4, 12, 0, tzinfo=MSK),
    )

    first = await confirm_payment(
        db_session,
        request.id,
        admin_id=11,
        handled_at=datetime(2026, 10, 4, 12, 5, tzinfo=MSK),
    )
    second = await confirm_payment(
        db_session,
        request.id,
        admin_id=22,
        handled_at=datetime(2026, 10, 4, 12, 6, tzinfo=MSK),
    )

    assert first.changed is True
    assert second.changed is False
    assert request.handled_by_admin_id == 11


@pytest.mark.asyncio
async def test_stale_admin_payment_action_cannot_overwrite_confirm(db_session_factory):
    async with db_session_factory() as setup_session:
        participant = await upsert_registered_participant(setup_session, 123, None, "Участник А.")
        participant.current_debt_rub = 500
        request = await create_payment_request(
            setup_session,
            participant.id,
            123,
            77,
            datetime(2026, 10, 4, 12, 0, tzinfo=MSK),
        )
        request_id = request.id
        await setup_session.commit()

    async with db_session_factory() as stale_session:
        stale_request = await stale_session.get(type(request), request_id)
        assert stale_request.status == PaymentStatus.PENDING

        async with db_session_factory() as winning_session:
            first = await confirm_payment(
                winning_session,
                request_id,
                admin_id=11,
                handled_at=datetime(2026, 10, 4, 12, 5, tzinfo=MSK),
            )
            await winning_session.commit()

        second = await reject_payment(
            stale_session,
            request_id,
            admin_id=22,
            handled_at=datetime(2026, 10, 4, 12, 6, tzinfo=MSK),
        )
        await stale_session.commit()

    async with db_session_factory() as check_session:
        final_request = await check_session.get(type(request), request_id)

    assert first.changed is True
    assert second.changed is False
    assert final_request.status == PaymentStatus.CONFIRMED
    assert final_request.handled_by_admin_id == 11


@pytest.mark.asyncio
async def test_confirm_removed_participant_marks_reinvite_needed(db_session):
    participant = await upsert_registered_participant(db_session, 123, None, "Участник А.")
    participant.status = ParticipantStatus.REMOVED
    participant.current_debt_rub = 500
    request = await create_payment_request(
        db_session,
        participant.id,
        123,
        77,
        datetime(2026, 10, 4, 12, 0, tzinfo=MSK),
    )

    decision = await confirm_payment(
        db_session,
        request.id,
        admin_id=11,
        handled_at=datetime(2026, 10, 4, 12, 5, tzinfo=MSK),
    )

    assert decision.should_send_reinvite is True
    assert decision.should_unban is True
    assert participant.status == ParticipantStatus.ACTIVE


@pytest.mark.asyncio
async def test_confirm_entry_fee_activates_participant_and_sends_invite(db_session):
    participant = await upsert_registered_participant(db_session, 123, None, "Участник А.")
    participant.rules_accepted_at = datetime(2026, 10, 4, 12, 0, tzinfo=MSK)
    request = await create_payment_request(
        db_session,
        participant.id,
        123,
        77,
        datetime(2026, 10, 4, 12, 5, tzinfo=MSK),
        purpose=PaymentPurpose.ENTRY_FEE,
        amount_rub=500,
    )

    decision = await confirm_payment(
        db_session,
        request.id,
        admin_id=11,
        handled_at=datetime(2026, 10, 4, 12, 10, tzinfo=MSK),
    )

    assert decision.changed is True
    assert decision.should_send_reinvite is True
    assert decision.should_unban is False
    assert decision.purpose == PaymentPurpose.ENTRY_FEE
    assert request.amount_rub_at_submission == 500
    assert participant.status == ParticipantStatus.ACTIVE
    assert participant.challenge_started_at == datetime(2026, 10, 5, 1, 0, tzinfo=MSK)
    assert participant.current_debt_rub == 0


def test_entry_payment_confirmation_mentions_first_report_date():
    text = entry_payment_confirmed_text(datetime(2026, 11, 8, 1, 0, tzinfo=MSK), "Europe/Moscow")

    assert "Первый отчёт принимается с 8 ноября" in text
    assert "01:00 МСК" in text


@pytest.mark.asyncio
async def test_payment_notification_goes_to_every_admin():
    bot = FakeBot()

    await notify_admins_about_payment(
        bot,
        admin_ids=(11, 22),
        proof_chat_id=123,
        proof_message_id=77,
        participant_display_name="Участник А.",
        participant_telegram_user_id=555,
        amount_rub=1500,
        payment_request_id=9,
    )

    assert bot.copied_messages == [(11, 123, 77), (22, 123, 77)]
    assert [message["chat_id"] for message in bot.sent_messages] == [11, 22]
    assert all("Новая оплата долга на проверку" in message["text"] for message in bot.sent_messages)
    assert all(message["reply_markup"] is not None for message in bot.sent_messages)


@pytest.mark.asyncio
async def test_payment_notification_skips_admin_who_has_not_started_bot():
    bot = FakeBot(forbidden_admin_ids={22})

    await notify_admins_about_payment(
        bot,
        admin_ids=(11, 22),
        proof_chat_id=123,
        proof_message_id=77,
        participant_display_name="Участник А.",
        participant_telegram_user_id=555,
        amount_rub=1500,
        payment_request_id=9,
    )

    assert bot.copied_messages == [(11, 123, 77)]
    assert [message["chat_id"] for message in bot.sent_messages] == [11]


def test_payment_review_text_contains_participant_and_debt():
    text = payment_review_text("Участник А.", 555, 1500)

    assert "Участник: Участник А." in text
    assert "Telegram ID: 555" in text
    assert "Сумма: 1500 ₽" in text


def test_payment_review_text_marks_entry_fee():
    text = payment_review_text("Участник А.", 555, 500, PaymentPurpose.ENTRY_FEE)

    assert text.startswith("Новая оплата за вход на проверку.")
    assert "Сумма: 500 ₽" in text


def test_debt_reminder_keyboard_has_pay_button():
    keyboard = pay_debt_keyboard()

    button = keyboard.inline_keyboard[0][0]
    assert button.text == "Оплатить долг"
    assert button.callback_data == PAY_DEBT_CALLBACK


def test_payment_prompt_text_asks_for_photo_or_file():
    text = debt_payment_prompt_text()

    assert "Пришли фото чека" in text
    assert "файл" in text


def test_participant_payment_status_texts_are_explicit():
    assert payment_proof_received_text() == "Чек принят и отправлен администраторам на проверку. Я напишу, когда оплату подтвердят."
    assert payment_confirmed_text() == "Оплата подтверждена. Долг закрыт, продолжаем челлендж."
    assert payment_rejected_text() == "Оплату не удалось подтвердить. Нажми кнопку и пришли корректный чек."


def test_payment_proof_accepts_only_photo_or_document():
    assert _has_payment_proof(SimpleMessage(photo=["photo"], document=None, video=None)) is True
    assert _has_payment_proof(SimpleMessage(photo=None, document="file", video=None)) is True
    assert _has_payment_proof(SimpleMessage(photo=None, document=None, video="video")) is False


def test_entry_fee_is_not_blocked_by_zero_debt():
    participant = SimpleMessage(current_debt_rub=0, rules_accepted_at=object(), status=ParticipantStatus.REGISTERED)

    assert payment_blocking_message(participant, PaymentPurpose.ENTRY_FEE) is None


def test_debt_payment_is_blocked_by_zero_debt():
    participant = SimpleMessage(current_debt_rub=0, rules_accepted_at=object(), status=ParticipantStatus.ACTIVE)

    assert payment_blocking_message(participant, PaymentPurpose.DEBT) == "Сейчас у тебя нет долга по челленджу."


class FakeBot:
    def __init__(self, forbidden_admin_ids=None):
        self.copied_messages = []
        self.sent_messages = []
        self.forbidden_admin_ids = forbidden_admin_ids or set()

    async def copy_message(self, chat_id, from_chat_id, message_id):
        if chat_id in self.forbidden_admin_ids:
            raise TelegramForbiddenError(method=None, message="Forbidden: bot can't initiate conversation with a user")
        self.copied_messages.append((chat_id, from_chat_id, message_id))

    async def send_message(self, chat_id, text, reply_markup=None):
        if chat_id in self.forbidden_admin_ids:
            raise TelegramForbiddenError(method=None, message="Forbidden: bot can't initiate conversation with a user")
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )


class SimpleMessage:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
