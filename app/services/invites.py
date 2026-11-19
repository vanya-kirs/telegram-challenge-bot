from aiogram import Bot


async def create_one_time_invite(bot: Bot, group_id: int, participant_name: str) -> str:
    invite = await bot.create_chat_invite_link(
        chat_id=group_id,
        name=f"Планка-челлендж: {participant_name}",
        member_limit=1,
    )
    return invite.invite_link


async def create_rejoin_invite(
    bot: Bot,
    group_id: int,
    telegram_user_id: int,
    participant_name: str,
) -> str:
    await bot.unban_chat_member(group_id, telegram_user_id, only_if_banned=True)
    return await create_one_time_invite(bot, group_id, participant_name)
