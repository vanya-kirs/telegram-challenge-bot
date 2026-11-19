from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.db.models import Participant, PaymentPurpose, PaymentRequest, PaymentStatus
from app.keyboards.admin import admin_menu_keyboard
from app.keyboards.participant import pay_debt_keyboard
from app.handlers.payments import entry_payment_confirmed_text, payment_confirmed_text, payment_rejected_text
from app.services.invites import create_one_time_invite, create_rejoin_invite
from app.services.payments import confirm_payment, reject_payment
from app.services.rankings import build_completion_ranking


def register_admin_handlers(
    router: Router,
    settings: Settings,
    session_factory: async_sessionmaker | None = None,
) -> None:
    @router.message(Command("admin"), F.chat.type == "private")
    @router.message(F.text == "Меню админа", F.chat.type == "private")
    async def show_admin_menu(message: Message) -> None:
        if not _is_admin(message.from_user.id if message.from_user else None, settings):
            return
        await message.answer("Админ-меню", reply_markup=admin_menu_keyboard())

    @router.message(F.text == "Платежи", F.chat.type == "private")
    async def show_payments(message: Message) -> None:
        if session_factory is None or not _is_admin(message.from_user.id if message.from_user else None, settings):
            return
        async with session_factory() as session:
            pending = await session.scalar(
                select(func.count(PaymentRequest.id)).where(PaymentRequest.status == PaymentStatus.PENDING)
            )
        await message.answer(f"Платежи на проверке: {pending or 0}")

    @router.message(F.text == "Участники", F.chat.type == "private")
    async def show_participants(message: Message) -> None:
        if session_factory is None or not _is_admin(message.from_user.id if message.from_user else None, settings):
            return
        async with session_factory() as session:
            rows = await session.execute(select(Participant).order_by(Participant.display_name).limit(30))
        text = "\n".join(
            f"{participant.display_name}: долг {participant.current_debt_rub} ₽, пропусков {participant.penalty_step}"
            for participant in rows.scalars()
        )
        await message.answer(text or "Участников пока нет.")

    @router.message(F.text == "Рейтинг", F.chat.type == "private")
    async def show_ranking(message: Message) -> None:
        if session_factory is None or not _is_admin(message.from_user.id if message.from_user else None, settings):
            return
        async with session_factory() as session:
            ranking = await build_completion_ranking(session)
        text = "\n".join(
            f"{idx}. {row.display_name}: {row.completion_percent}%"
            for idx, row in enumerate(ranking[:20], start=1)
        )
        await message.answer(text or "Рейтинг пока пуст.")

    @router.callback_query(F.data.startswith("payment:"))
    async def handle_payment_callback(callback: CallbackQuery) -> None:
        if session_factory is None or not _is_admin(callback.from_user.id, settings):
            await callback.answer("Недоступно", show_alert=True)
            return
        _, action, request_id_text = callback.data.split(":", maxsplit=2)  # type: ignore[union-attr]
        request_id = int(request_id_text)
        async with session_factory() as session:
            now = datetime.now(ZoneInfo(settings.timezone))
            if action == "confirm":
                decision = await confirm_payment(
                    session,
                    request_id,
                    callback.from_user.id,
                    now,
                    timezone=settings.timezone,
                )
            else:
                decision = await reject_payment(session, request_id, callback.from_user.id, now)
            participant = await session.get(Participant, decision.participant_id)
            invite_link: str | None = None
            if decision.changed and decision.should_send_reinvite and participant is not None:
                if decision.should_unban:
                    invite_link = await create_rejoin_invite(
                        callback.bot,
                        settings.challenge_group_id,
                        participant.telegram_user_id,
                        participant.display_name,
                    )
                else:
                    invite_link = await create_one_time_invite(
                        callback.bot,
                        settings.challenge_group_id,
                        participant.display_name,
                    )
            await session.commit()
        if not decision.changed:
            await callback.answer("Заявка уже обработана", show_alert=True)
            return
        await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]
        await callback.answer("Готово")
        if participant is not None and invite_link is not None:
            if decision.purpose == PaymentPurpose.ENTRY_FEE:
                invite_text = (
                    f"{entry_payment_confirmed_text(participant.challenge_started_at, settings.timezone)}\n\n"
                    "Перейди в группу:\n"
                )
            else:
                invite_text = "Оплата подтверждена. Можно вернуться в группу:\n"
            await callback.bot.send_message(
                participant.telegram_user_id,
                f"{invite_text}{invite_link}",
            )
        elif participant is not None and decision.status == PaymentStatus.CONFIRMED:
            await callback.bot.send_message(participant.telegram_user_id, payment_confirmed_text())
        elif participant is not None:
            await callback.bot.send_message(
                participant.telegram_user_id,
                payment_rejected_text(),
                reply_markup=pay_debt_keyboard(),
            )


def _is_admin(user_id: int | None, settings: Settings) -> bool:
    return user_id in settings.admin_ids if user_id is not None else False
