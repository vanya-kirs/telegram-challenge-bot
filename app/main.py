import asyncio
import logging

from app.bot import create_bot, create_dispatcher
from app.config import load_settings
from app.db.session import create_session_factory
from app.scheduler import setup_scheduler, startup_recovery_job


async def main() -> None:
    settings = load_settings()
    logging.basicConfig(level=settings.log_level)
    bot = create_bot(settings)
    session_factory = create_session_factory(settings.database_url)
    dispatcher = create_dispatcher(settings, session_factory)
    scheduler = setup_scheduler(bot, settings, session_factory)
    await startup_recovery_job(bot, settings, session_factory)
    scheduler.start()
    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
