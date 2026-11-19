from types import SimpleNamespace

import pytest

from app.services.invites import create_rejoin_invite


@pytest.mark.asyncio
async def test_rejoin_invite_unbans_participant_before_creating_link():
    bot = InviteBotStub()

    link = await create_rejoin_invite(bot, -1001, 123, "Участник А.")

    assert link == "https://example.invalid/invite"
    assert bot.calls == [
        ("unban", -1001, 123, True),
        ("invite", -1001, "Планка-челлендж: Участник А.", 1),
    ]


class InviteBotStub:
    def __init__(self):
        self.calls = []

    async def unban_chat_member(self, chat_id, user_id, only_if_banned=True):
        self.calls.append(("unban", chat_id, user_id, only_if_banned))

    async def create_chat_invite_link(self, chat_id, name, member_limit):
        self.calls.append(("invite", chat_id, name, member_limit))
        return SimpleNamespace(invite_link="https://example.invalid/invite")
