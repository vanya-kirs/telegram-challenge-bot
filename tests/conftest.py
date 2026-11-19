from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChallengeDay
from app.services.challenge_days import challenge_day_window


@pytest.fixture
async def db_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    yield session_factory

    await engine.dispose()


@pytest.fixture
async def db_session(db_session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with db_session_factory() as session:
        yield session


@pytest.fixture
async def challenge_day(db_session: AsyncSession) -> ChallengeDay:
    from datetime import date

    starts_at, ends_at = challenge_day_window(date(2026, 10, 4))
    day = ChallengeDay(day=date(2026, 10, 4), starts_at=starts_at, ends_at=ends_at)
    db_session.add(day)
    await db_session.flush()
    return day
