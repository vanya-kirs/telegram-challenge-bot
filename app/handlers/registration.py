from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.db.models import Participant
from app.keyboards.admin import admin_menu_keyboard
from app.keyboards.participant import ACCEPT_RULES_CALLBACK, accept_rules_keyboard, pay_entry_keyboard
from app.services.participants import record_rules_acceptance, upsert_registered_participant


RULES_TEXT = """Правила Планка-челленджа:

1. Каждый день присылай обычное видео с планкой в тему отчётов до 01:00 МСК.
2. Одно и то же видео второй раз не засчитывается.
3. Отчёт принимается только от тебя лично, без пересылок.
4. За каждый пропуск начисляется штраф. Первый пропуск — 500 ₽, следующий — 1000 ₽, дальше сумма нового пропуска растёт ещё на 500 ₽.
5. Оплата идёт переводом. Чек или скрин оплаты отправляй сюда, в личку боту.
6. Администратор подтверждает оплату вручную.
7. Если долг не закрыт 3 дня, бот предупредит об удалении. На 4-й день в 01:00 МСК участник удаляется из группы, но после оплаты может вернуться.
"""


def register_registration_handlers(
    router: Router,
    settings: Settings,
    session_factory: async_sessionmaker | None = None,
) -> None:
    @router.message(CommandStart(), F.chat.type == "private")
    async def start(message: Message) -> None:
        if message.from_user and message.from_user.id in settings.admin_ids:
            await message.answer("Админ-меню", reply_markup=admin_menu_keyboard())
            return
        await message.answer(
            "Регистрация в Планка-челлендже. Напиши имя и фамилию одним сообщением."
        )

    @router.message(StateFilter(None), F.chat.type == "private", F.text, ~F.text.startswith("/"))
    async def capture_name(message: Message) -> None:
        if session_factory is None or message.from_user is None or message.text is None:
            return
        async with session_factory() as session:
            participant = await upsert_registered_participant(
                session,
                telegram_user_id=message.from_user.id,
                username=message.from_user.username,
                display_name=message.text.strip(),
            )
            await session.commit()
        await message.answer(RULES_TEXT, reply_markup=accept_rules_keyboard())

    @router.callback_query(F.data == ACCEPT_RULES_CALLBACK)
    async def handle_accept_rules(callback: CallbackQuery) -> None:
        if session_factory is None or callback.from_user is None:
            await callback.answer()
            return
        async with session_factory() as session:
            participant = await _get_participant(session, callback.from_user.id)
            if participant is None:
                await callback.message.answer("Сначала напиши имя и фамилию одним сообщением.")  # type: ignore[union-attr]
                await callback.answer()
                return
            await record_rules_acceptance(session, participant, datetime.now(ZoneInfo(settings.timezone)))
            await session.commit()
        await callback.message.answer(  # type: ignore[union-attr]
            (
                "Правила приняты.\n\n"
                f"Для входа в челлендж нужно оплатить {settings.entry_fee_rub} ₽.\n\n"
                f"Оплата переводом:\n{settings.payment_bank}\n{settings.payment_phone}\n{settings.payment_recipient}\n\n"
                "После оплаты нажми кнопку ниже и пришли чек. После подтверждения администратором бот пришлёт ссылку в группу."
            ),
            reply_markup=pay_entry_keyboard(),
        )
        await callback.answer("Правила приняты")


async def _get_participant(session, telegram_user_id: int) -> Participant | None:
    from sqlalchemy import select

    result = await session.execute(
        select(Participant).where(Participant.telegram_user_id == telegram_user_id)
    )
    return result.scalar_one_or_none()
