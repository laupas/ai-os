import asyncio
import logging

from aios.approvals.approval_answer_handler import ApprovalAnswerHandler
from aios.approvals.approval_presenter_resolver import ApprovalPresenterResolver
from aios.common.clock import Clock
from aios.common.id_generator import IdGenerator
from aios.conversations.conversation_event import ConversationEvent
from aios.conversations.conversation_observer import ConversationObserver
from aios.entities.approvals.approval import Approval
from aios.entities.approvals.approval_status import ApprovalStatus
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.users.channel_account import ChannelAccount
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.users.authorizer import Authorizer

log = logging.getLogger(__name__)


class ApprovalService(ApprovalAnswerHandler):
    """Puts a question to a human and waits for the answer.

    The question is shown wherever its conversation is: on every channel it is
    bound to, and to the observers (the web console). The first valid answer wins.
    Approvals are stored, but the waiting turn lives only in memory: after a
    restart, pending approvals are marked expired rather than resumed.
    """

    def __init__(
        self,
        approvals: Collection[Approval],
        users: Collection[User],
        authorizer: Authorizer,
        presenters: ApprovalPresenterResolver,
        clock: Clock,
        ids: IdGenerator,
        timeout_seconds: float,
        conversations: Collection[Conversation] | None = None,
        observers: list[ConversationObserver] | None = None,
    ) -> None:
        self._approvals = approvals
        self._users = users
        self._authorizer = authorizer
        self._presenters = presenters
        self._clock = clock
        self._ids = ids
        self._timeout = timeout_seconds
        self._conversations = conversations
        self._observers = list(observers or [])
        self._waiting: dict[str, asyncio.Future[str]] = {}

    async def request(
        self,
        conversation_id: str,
        binding: ChannelBinding,
        question: str,
        options: list[str],
        approver_permission: Permission = Permission.APPROVE,
    ) -> str | None:
        """Returns the chosen option, or None if nobody answered in time."""
        approval = await self._approvals.put(
            Approval(
                id=self._ids.new_id(),
                conversation_id=conversation_id,
                binding=binding,
                question=question,
                options=options,
                approver_permission=approver_permission,
                created_at=self._clock.now(),
            )
        )
        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
        self._waiting[approval.id] = future
        try:
            await self._present(approval)
            return await asyncio.wait_for(future, self._timeout)
        except TimeoutError:
            await self._expire(approval.id)
            return None
        except asyncio.CancelledError:
            await self._expire(approval.id)
            raise
        finally:
            self._waiting.pop(approval.id, None)

    async def answer(self, approval_id: str, answer: str, sender: ChannelAccount) -> bool:
        approval = self._approvals.get(approval_id)
        if approval is None or approval.status is not ApprovalStatus.PENDING:
            return False
        option = approval.option_matching(answer)
        if option is None:
            return False
        user = self._users.find(lambda u: u.has_account(sender.channel, sender.address))
        if not self._authorizer.has(user, approval.approver_permission):
            log.warning("approval %s: %s may not answer", approval_id, sender.address)
            return False
        assert user is not None
        await self._approvals.put(
            approval.model_copy(
                update={
                    "status": ApprovalStatus.ANSWERED,
                    "answer": option,
                    "answered_by": user.id,
                    "answered_at": self._clock.now(),
                }
            )
        )
        future = self._waiting.get(approval_id)
        if future is not None and not future.done():
            future.set_result(option)
        return True

    async def answer_from_text(
        self, conversation_id: str, sender: ChannelAccount, text: str
    ) -> bool:
        """Treats a chat message as an answer when it matches a pending approval of
        its conversation, whichever channel the question was shown on."""
        candidates = self._approvals.filter(
            lambda a: (
                a.status is ApprovalStatus.PENDING
                and a.conversation_id == conversation_id
                and a.option_matching(text) is not None
            )
        )
        if not candidates:
            return False
        latest = max(candidates, key=lambda a: a.created_at)
        return await self.answer(latest.id, text, sender)

    async def _present(self, approval: Approval) -> None:
        conversation = (
            self._conversations.get(approval.conversation_id) if self._conversations else None
        )
        bindings = list(conversation.bindings) if conversation else []
        if not any(b.same_place(approval.binding) for b in bindings):
            bindings = [approval.binding, *bindings]
        for binding in bindings:
            try:
                presenter = self._presenters.presenter_for(binding.channel)
                await presenter.present(approval.model_copy(update={"binding": binding}))
            except KeyError:
                continue  # a channel no longer enabled
            except Exception:
                log.exception("could not show approval %s on %s", approval.id, binding.channel)
        event = ConversationEvent(
            conversation_id=approval.conversation_id,
            kind="approval",
            text=approval.question,
            approval_id=approval.id,
            options=approval.options,
        )
        for observer in self._observers:
            observer.notify(event)

    async def expire_pending(self) -> None:
        for approval in self._approvals.filter(lambda a: a.status is ApprovalStatus.PENDING):
            await self._expire(approval.id)

    async def _expire(self, approval_id: str) -> None:
        approval = self._approvals.get(approval_id)
        if approval is not None and approval.status is ApprovalStatus.PENDING:
            await self._approvals.put(
                approval.model_copy(update={"status": ApprovalStatus.EXPIRED})
            )
