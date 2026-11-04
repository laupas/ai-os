import logging

from aios.channels.channel_directory import ChannelDirectory
from aios.conversations.turn_starter import TurnStarter
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.schedules.schedule import Schedule
from aios.entities.users.user import User
from aios.storage.collection import Collection

log = logging.getLogger(__name__)


class ScheduleRunner:
    """Runs one firing as a new conversation for the schedule's user, opened on
    every enabled channel that can start one and where the user has an account (a
    Slack DM, the web console). The user can reply in any of them."""

    def __init__(
        self, users: Collection[User], channels: ChannelDirectory, turns: TurnStarter
    ) -> None:
        self._users = users
        self._channels = channels
        self._turns = turns

    async def run(self, schedule: Schedule) -> None:
        user = self._users.get(schedule.user_id)
        if user is None:
            log.error("schedule %s: user %s does not exist", schedule.name, schedule.user_id)
            return
        bindings = await self._open(schedule, user)
        if not bindings:
            log.error("schedule %s: %s cannot be reached on any channel", schedule.name, user.name)
            return
        await self._turns.start_turn(user, bindings, schedule.prompt, schedule.agent)

    async def _open(self, schedule: Schedule, user: User) -> list[ChannelBinding]:
        bindings = []
        for channel in self._channels.enabled():
            starter = self._channels.thread_starter_for(channel.name)
            account = user.account_for(channel.name)
            if starter is None or account is None:
                continue
            try:
                bindings.append(
                    await starter.start_thread(account.address, f":alarm_clock: {schedule.name}")
                )
            except Exception:
                log.exception(
                    "schedule %s: could not open a thread on %s", schedule.name, channel.name
                )
        return bindings
