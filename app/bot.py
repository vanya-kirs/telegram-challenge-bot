from aiogram import Bot, Dispatcher
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.handlers.admin import register_admin_handlers
from app.handlers.group_reports import register_group_report_handlers
from app.handlers.payments import register_payment_handlers
from app.handlers.registration import register_registration_handlers


def create_bot(settings: Settings) -> Bot:
    return Bot(token=settings.bot_token)


def create_dispatcher(
    settings: Settings,
    session_factory: async_sessionmaker | None = None,
) -> Dispatcher:
    dispatcher = Dispatcher(settings=settings)
    register_admin_handlers(dispatcher, settings, session_factory)
    register_registration_handlers(dispatcher, settings, session_factory)
    register_group_report_handlers(dispatcher, settings, session_factory)
    register_payment_handlers(dispatcher, settings, session_factory)
    return dispatcher
