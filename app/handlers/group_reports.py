import asyncio
from contextlib import suppress
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.db.models import Participant
from app.services.challenge_days import render_daily_list
from app.services.reports import accept_video_report, accepted_report_names, get_or_create_challenge_day


def register_group_report_handlers(
    router: Router,
    settings: Settings,
    session_factory: async_sessionmaker | None = None,
) -> None:
    @router.message(F.chat.type.in_({"group", "supergroup"}))
    async def handle_group_message(message: Message) -> None:
        if session_factory is None or message.from_user is None:
            return
        if should_ignore_group_message(message.from_user.id, settings.admin_ids):
            return
        if message.video is None:
            return
        if is_wrong_report_topic_video(
            chat_id=message.chat.id,
            thread_id=message.message_thread_id,
            expected_chat_id=settings.challenge_group_id,
            expected_thread_id=settings.report_topic_id,
            has_video=True,
        ):
            async with session_factory() as session:
                display_name = await _participant_display_name(session, message.from_user.id)
            warning = await message.reply(wrong_topic_report_text(display_name))
            schedule_delete_messages(
                message.bot,
                chat_id=message.chat.id,
                message_ids=[message.message_id, warning.message_id],
                delay_seconds=10,
            )
            return
        if not should_process_report_message(
            message.chat.id,
            message.message_thread_id,
            settings.challenge_group_id,
            settings.report_topic_id,
            has_video=True,
        ):
            return
        if _is_forwarded(message):
            await message.reply("Пересланные видео не засчитываются. Пришли новый отчёт лично.")
            return

        submitted_at = message.date.astimezone(ZoneInfo(settings.timezone))
        async with session_factory() as session:
            decision = await accept_video_report(
                session,
                telegram_user_id=message.from_user.id,
                message_id=message.message_id,
                chat_id=message.chat.id,
                thread_id=message.message_thread_id,
                file_id=message.video.file_id,
                file_unique_id=message.video.file_unique_id,
                submitted_at=submitted_at,
                expected_thread_id=settings.report_topic_id,
            )
            if decision.accepted and decision.challenge_day is not None:
                challenge_day = await get_or_create_challenge_day(session, decision.challenge_day)
                names = await accepted_report_names(session, decision.challenge_day)
                if challenge_day.list_message_id is not None:
                    await message.bot.edit_message_text(
                        render_daily_list(decision.challenge_day, names),
                        chat_id=settings.challenge_group_id,
                        message_id=challenge_day.list_message_id,
                    )
                await session.commit()
                await message.reply("Спасибо за отчёт! Видео зачтено, ты уже в общем списке.")
                return
            await session.commit()

        rejection = await message.reply(_rejection_text(decision.reason))
        if should_auto_delete_rejected_report(decision.reason):
            schedule_delete_messages(
                message.bot,
                chat_id=message.chat.id,
                message_ids=[message.message_id, rejection.message_id],
                delay_seconds=10,
            )


def _is_forwarded(message: Message) -> bool:
    return any(
        getattr(message, attr, None) is not None
        for attr in ("forward_origin", "forward_from", "forward_from_chat", "forward_sender_name")
    )


def should_process_report_message(
    chat_id: int,
    thread_id: int | None,
    expected_chat_id: int,
    expected_thread_id: int,
    has_video: bool,
) -> bool:
    return has_video and chat_id == expected_chat_id and thread_id == expected_thread_id


def should_ignore_group_message(user_id: int | None, admin_ids: tuple[int, ...]) -> bool:
    return user_id is not None and user_id in admin_ids


def is_wrong_report_topic_video(
    *,
    chat_id: int,
    thread_id: int | None,
    expected_chat_id: int,
    expected_thread_id: int,
    has_video: bool,
) -> bool:
    return has_video and chat_id == expected_chat_id and thread_id != expected_thread_id


def wrong_topic_report_text(display_name: str | None) -> str:
    name = display_name or "Участник"
    return f"{name}, это не та тема для отчёта. Пришли видео в тему отчётов."


def should_auto_delete_rejected_report(reason: str) -> bool:
    return reason == "duplicate_video"


def schedule_delete_messages(
    bot,
    *,
    chat_id: int,
    message_ids: list[int],
    delay_seconds: int,
) -> None:
    asyncio.create_task(_delete_messages_after_delay(bot, chat_id, message_ids, delay_seconds))


async def _delete_messages_after_delay(
    bot,
    chat_id: int,
    message_ids: list[int],
    delay_seconds: int,
) -> None:
    await asyncio.sleep(delay_seconds)
    for message_id in message_ids:
        with suppress(TelegramBadRequest, TelegramForbiddenError):
            await bot.delete_message(chat_id=chat_id, message_id=message_id)


async def _participant_display_name(session, telegram_user_id: int) -> str | None:
    result = await session.execute(
        select(Participant.display_name).where(Participant.telegram_user_id == telegram_user_id)
    )
    return result.scalar_one_or_none()


def _rejection_text(reason: str) -> str:
    if reason == "duplicate_video":
        return "Это видео уже засчитывалось раньше. Пришли новое видео."
    if reason == "already_reported_today":
        return "Твой отчёт за этот день уже принят."
    if reason == "unknown_participant":
        return "Я принимаю отчёты только от зарегистрированных участников."
    if reason == "not_started_yet":
        return "Твой челлендж ещё не начался. Дата первого отчёта указана в сообщении бота после подтверждения оплаты."
    return "Не получилось принять отчёт. Проверь, что отправляешь обычное видео в нужную тему."
