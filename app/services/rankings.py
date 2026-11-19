from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Miss, Participant, Report
from app.services.challenge_days import challenge_day_for


@dataclass(frozen=True)
class RankingRow:
    participant_id: int
    display_name: str
    reports_count: int
    participation_days: int
    completion_percent: float


def completion_percent(reports: int, days: int) -> float:
    if days <= 0:
        return 0.0
    return round((reports / days) * 100, 2)


async def build_completion_ranking(session: AsyncSession, today: date | None = None) -> list[RankingRow]:
    report_counts = (
        select(Report.participant_id, func.count(Report.id).label("reports_count"))
        .group_by(Report.participant_id)
        .subquery()
    )
    miss_counts = (
        select(Miss.participant_id, func.count(Miss.id).label("misses_count"))
        .group_by(Miss.participant_id)
        .subquery()
    )
    result = await session.execute(
        select(
            Participant,
            func.coalesce(report_counts.c.reports_count, 0).label("reports_count"),
            func.coalesce(miss_counts.c.misses_count, 0).label("misses_count"),
        )
        .outerjoin(report_counts, report_counts.c.participant_id == Participant.id)
        .outerjoin(miss_counts, miss_counts.c.participant_id == Participant.id)
        .order_by(func.coalesce(report_counts.c.reports_count, 0).desc(), Participant.display_name)
    )
    rows: list[RankingRow] = []
    for participant, reports_count, misses_count in result:
        evaluated_days = int(reports_count) + int(misses_count)
        rows.append(
            RankingRow(
                participant_id=participant.id,
                display_name=participant.display_name,
                reports_count=int(reports_count),
                participation_days=evaluated_days,
                completion_percent=completion_percent(int(reports_count), evaluated_days),
            )
        )
    return rows


def participation_days(participant: Participant, today: date) -> int:
    if participant.challenge_started_at is None:
        return 0
    started_on = challenge_day_for(participant.challenge_started_at)
    return max((today - started_on).days + 1, 0)
