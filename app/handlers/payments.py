from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.db.models import Participant, PaymentPurpose
from app.keyboards.admin import payment_decision_keyboard
from app.keyboards.participant import PAY_DEBT_CALLBACK, PAY_ENTRY_CALLBACK
from app.services.payments import create_payment_request
from app.services.challenge_days import MONTHS_RU


class PaymentFlow(StatesGroup):
    waiting_for_proof = State()


def register_payment_handlers(
    router: Router,
    settings: Settings,
    session_factory: async_sessionmaker | None = None,
) -> None:
    @router.callback_query(F.data.in_({PAY_DEBT_CALLBACK, PAY_ENTRY_CALLBACK}))
    async def start_payment(callback: CallbackQuery, state: FSMContext) -> None:
        if session_factory is None:
            await callback.answer()
            return
        purpose = PaymentPurpose.ENTRY_FEE if callback.data == PAY_ENTRY_CALLBACK else PaymentPurpose.DEBT
        async with session_factory() as session:
            participant = await _get_participant(session, callback.from_user.id)
            if participant is None:
                await callback.message.answer("Сначала пройди регистрацию через /start.")  # type: ignore[union-attr]
                await callback.answer()
                return
            if purpose == PaymentPurpose.ENTRY_FEE and participant.rules_accepted_at is None:
                await callback.message.answer("Сначала прими правила через /start.")  # type: ignore[union-attr]
                await callback.answer()
                return
            if purpose == PaymentPurpose.DEBT and participant.current_debt_rub <= 0:
                await state.clear()
                await callback.message.answer("Сейчас у тебя нет долга по челленджу.")  # type: ignore[union-attr]
                await callback.answer()
                return
            if purpose == PaymentPurpose.ENTRY_FEE and participant.status.value == "active":
                await state.clear()
                await callback.message.answer("Вход уже подтверждён.")  # type: ignore[union-attr]
                await callback.answer()
                return
            await state.set_state(PaymentFlow.waiting_for_proof)
            await state.update_data(payment_purpose=purpose.value)
        await callback.message.answer(payment_prompt_text(purpose))  # type: ignore[union-attr]
        await callback.answer("Жду чек")

    @router.message(PaymentFlow.waiting_for_proof, F.chat.type == "private")
    async def handle_payment_proof(message: Message, state: FSMContext) -> None:
        if session_factory is None or message.from_user is None:
            return
        if message.text and message.text.startswith("/"):
            await state.clear()
            return
        state_data = await state.get_data()
        purpose = PaymentPurpose(state_data.get("payment_purpose", PaymentPurpose.DEBT.value))
        if not _has_payment_proof(message):
            await message.answer(payment_prompt_text(purpose))
            return

        async with session_factory() as session:
            participant = await _get_participant(session, message.from_user.id)
            if participant is None:
                await state.clear()
                await message.answer("Сначала пройди регистрацию через /start.")
                return
            blocking_message = payment_blocking_message(participant, purpose)
            if blocking_message is not None:
                await state.clear()
                await message.answer(blocking_message)
                return
            request = await create_payment_request(
                session,
                participant.id,
                message.chat.id,
                message.message_id,
                datetime.now(ZoneInfo(settings.timezone)),
                purpose=purpose,
                amount_rub=settings.entry_fee_rub if purpose == PaymentPurpose.ENTRY_FEE else None,
            )
            await session.commit()
        await state.clear()

        await notify_admins_about_payment(
            message.bot,
            admin_ids=settings.admin_ids,
            proof_chat_id=message.chat.id,
            proof_message_id=message.message_id,
            participant_display_name=participant.display_name,
            participant_telegram_user_id=participant.telegram_user_id,
            amount_rub=request.amount_rub_at_submission,
            payment_request_id=request.id,
            purpose=request.purpose,
        )
        await message.answer(payment_proof_received_text())


def _has_payment_proof(message: Message) -> bool:
    return any(
        getattr(message, attr, None) is not None
        for attr in ("photo", "document")
    )


def payment_blocking_message(participant: Participant, purpose: PaymentPurpose) -> str | None:
    if purpose == PaymentPurpose.ENTRY_FEE:
        if participant.rules_accepted_at is None:
            return "Сначала прими правила через /start."
        if participant.status.value == "active":
            return "Вход уже подтверждён."
        return None
    if participant.current_debt_rub <= 0:
        return "Сейчас у тебя нет долга по челленджу."
    return None


async def _get_participant(session, telegram_user_id: int) -> Participant | None:
    result = await session.execute(
        select(Participant).where(Participant.telegram_user_id == telegram_user_id)
    )
    return result.scalar_one_or_none()


async def notify_admins_about_payment(
    bot,
    *,
    admin_ids: tuple[int, ...],
    proof_chat_id: int,
    proof_message_id: int,
    participant_display_name: str,
    participant_telegram_user_id: int,
    amount_rub: int,
    payment_request_id: int,
    purpose: PaymentPurpose = PaymentPurpose.DEBT,
) -> None:
    for admin_id in admin_ids:
        try:
            await bot.copy_message(admin_id, proof_chat_id, proof_message_id)
            await bot.send_message(
                admin_id,
                payment_review_text(
                    participant_display_name,
                    participant_telegram_user_id,
                amount_rub,
                purpose,
            ),
                reply_markup=payment_decision_keyboard(payment_request_id),
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            continue


def payment_review_text(
    participant_display_name: str,
    participant_telegram_user_id: int,
    amount_rub: int,
    purpose: PaymentPurpose = PaymentPurpose.DEBT,
) -> str:
    title = "Новая оплата за вход на проверку." if purpose == PaymentPurpose.ENTRY_FEE else "Новая оплата долга на проверку."
    return (
        f"{title}\n"
        f"Участник: {participant_display_name}\n"
        f"Telegram ID: {participant_telegram_user_id}\n"
        f"Сумма: {amount_rub} ₽"
    )


def debt_payment_prompt_text() -> str:
    return "Пришли фото чека или файл с подтверждением оплаты одним сообщением."


def entry_payment_prompt_text() -> str:
    return "Пришли фото чека или файл с подтверждением оплаты входа одним сообщением."


def payment_prompt_text(purpose: PaymentPurpose) -> str:
    if purpose == PaymentPurpose.ENTRY_FEE:
        return entry_payment_prompt_text()
    return debt_payment_prompt_text()


def payment_proof_received_text() -> str:
    return "Чек принят и отправлен администраторам на проверку. Я напишу, когда оплату подтвердят."


def payment_confirmed_text() -> str:
    return "Оплата подтверждена. Долг закрыт, продолжаем челлендж."


def entry_payment_confirmed_text(challenge_started_at: datetime, timezone: str) -> str:
    local_start = challenge_started_at.astimezone(ZoneInfo(timezone))
    return (
        "Оплата за вход подтверждена. "
        f"Первый отчёт принимается с {local_start.day} {MONTHS_RU[local_start.month]}, "
        "с 01:00 МСК. До этого времени видео не засчитываются."
    )


def payment_rejected_text() -> str:
    return "Оплату не удалось подтвердить. Нажми кнопку и пришли корректный чек."
