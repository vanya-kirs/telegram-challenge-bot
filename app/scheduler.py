from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.models import ChallengeDay, Participant, ParticipantStatus
from app.keyboards.participant import pay_debt_keyboard
from app.services.challenge_days import challenge_day_for, challenge_day_window, render_daily_list
from app.services.penalties import charge_missing_reports_for_day, debt_age_days, is_removal_due
from app.services.reports import accepted_report_names, get_or_create_challenge_day


@dataclass(frozen=True)
class CloseDayResult:
    day: date
    charged_count: int
    removed_count: int


def setup_scheduler(
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    close_time = _parse_time(settings.daily_close_time)
    scheduler.add_job(
        close_day_job,
        "cron",
        hour=close_time.hour,
        minute=close_time.minute,
        args=[bot, settings, session_factory],
        id="close_day_job",
        replace_existing=True,
    )
    return scheduler


async def close_day_job(
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime.now(ZoneInfo(settings.timezone))
    day_to_close = challenge_day_for(now - timedelta(minutes=1), settings.timezone, _parse_time(settings.daily_close_time))
    async with session_factory() as session:
        await close_challenge_day(session, bot, settings, day_to_close, now)
        await session.commit()


async def close_challenge_day(
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
    day: date,
    now: datetime,
) -> CloseDayResult:
    await get_or_create_challenge_day(session, day)
    result = await session.execute(
        select(ChallengeDay).where(ChallengeDay.day == day).with_for_update()
    )
    challenge_day = result.scalar_one()
    if challenge_day.closed_at is not None:
        return CloseDayResult(day=day, charged_count=0, removed_count=0)

    charge_result = await charge_missing_reports_for_day(session, challenge_day, settings.penalty_step_rub)
    removed_count = await _send_debt_reminders_and_remove_due(session, bot, settings, now.date())
    challenge_day.closed_at = now
    await _unpin_daily_list(bot, challenge_day)
    await _create_and_pin_next_day_list(session, bot, settings, day + timedelta(days=1))
    await session.flush()
    return CloseDayResult(day=day, charged_count=charge_result.charged_count, removed_count=removed_count)


async def startup_recovery_job(
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime.now(ZoneInfo(settings.timezone))
    current_day = challenge_day_for(now, settings.timezone, _parse_time(settings.daily_close_time))
    async with session_factory() as session:
        first_unclosed_day = await session.scalar(
            select(ChallengeDay.day)
            .where(ChallengeDay.day < current_day)
            .where(ChallengeDay.closed_at.is_(None))
            .order_by(ChallengeDay.day)
            .limit(1)
        )
        if first_unclosed_day is not None:
            for day in recovery_days(first_unclosed_day, current_day):
                await close_challenge_day(session, bot, settings, day, now)
        current_challenge_day = await get_or_create_challenge_day(session, current_day)
        if current_challenge_day.list_message_id is None:
            await _create_and_pin_next_day_list(session, bot, settings, current_day)
        await session.commit()


async def _send_debt_reminders_and_remove_due(
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
    today: date,
) -> int:
    result = await session.execute(
        select(Participant)
        .where(Participant.status == ParticipantStatus.ACTIVE)
        .where(Participant.current_debt_rub > 0)
    )
    removed_count = 0
    for participant in result.scalars():
        age = debt_age_days(participant, today)
        if is_removal_due(participant, today):
            await bot.ban_chat_member(settings.challenge_group_id, participant.telegram_user_id)
            participant.status = ParticipantStatus.REMOVED
            participant.removed_at = datetime.now(ZoneInfo(settings.timezone))
            await _send_removal_notice(bot, participant, settings)
            removed_count += 1
            continue
        warning = "\n\nЭто третий день просрочки. Завтра в 01:00 МСК бот удалит тебя из группы, если оплата не будет подтверждена." if age == 3 else ""
        await bot.send_message(
            participant.telegram_user_id,
            (
                f"У тебя долг по Планка-челленджу: {participant.current_debt_rub} ₽.\n\n"
                f"Оплата переводом:\n{settings.payment_bank}\n{settings.payment_phone}\n{settings.payment_recipient}\n\n"
                f"После оплаты нажми кнопку ниже и пришли чек или скрин сюда в личку боту.{warning}"
            ),
            reply_markup=pay_debt_keyboard(),
        )
    return removed_count


async def _create_and_pin_next_day_list(
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
    next_day: date,
) -> None:
    challenge_day = await get_or_create_challenge_day(session, next_day)
    names = await accepted_report_names(session, next_day)
    topic_id = list_topic_id(settings)
    message = await bot.send_message(
        settings.challenge_group_id,
        render_daily_list(next_day, names),
        message_thread_id=topic_id,
    )
    await bot.pin_chat_message(settings.challenge_group_id, message.message_id, disable_notification=True)
    challenge_day.list_message_chat_id = settings.challenge_group_id
    challenge_day.list_message_thread_id = topic_id
    challenge_day.list_message_id = message.message_id


async def _send_removal_notice(bot: Bot, participant: Participant, settings: Settings) -> None:
    try:
        await bot.send_message(
            participant.telegram_user_id,
            removal_notice_text(participant.current_debt_rub, settings),
            reply_markup=pay_debt_keyboard(),
        )
    except (TelegramBadRequest, TelegramForbiddenError):
        return


def removal_notice_text(amount_rub: int, settings: Settings) -> str:
    return (
        "Бот удалил тебя из группы за неоплаченный долг по Планка-челленджу.\n\n"
        f"Сейчас долг: {amount_rub} ₽.\n\n"
        f"Оплата переводом:\n{settings.payment_bank}\n{settings.payment_phone}\n{settings.payment_recipient}\n\n"
        "После оплаты нажми кнопку ниже и пришли чек. После подтверждения администратором бот пришлёт новую ссылку в группу."
    )


async def _unpin_daily_list(bot: Bot, challenge_day: ChallengeDay) -> None:
    if challenge_day.list_message_chat_id is None or challenge_day.list_message_id is None:
        return
    try:
        await bot.unpin_chat_message(
            chat_id=challenge_day.list_message_chat_id,
            message_id=challenge_day.list_message_id,
        )
    except (TelegramBadRequest, TelegramForbiddenError):
        return


def _parse_time(value: str) -> time:
    hour, minute = value.split(":", maxsplit=1)
    return time(int(hour), int(minute))


def recovery_days(first_day: date, current_day: date) -> list[date]:
    days: list[date] = []
    cursor = first_day
    while cursor < current_day:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def list_topic_id(settings) -> int | None:
    if settings.daily_list_topic_id is None:
        return settings.report_topic_id
    if settings.daily_list_topic_id <= 1:
        return None
    return settings.daily_list_topic_id
