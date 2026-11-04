import asyncio
import contextlib
from datetime import UTC, datetime, timedelta

from aiohttp import web

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.agent_unavailable_error import AgentUnavailableError
from aios.channels.web.web_channel import WebChannel
from aios.channels.web.web_event_hub import WebEventHub
from aios.conversations.conversation_deleter import ConversationDeleter
from aios.conversations.conversation_resolver import ConversationResolver
from aios.conversations.message_recorder import MessageRecorder
from aios.entities.conversations.channel_binding import ChannelBinding
from aios.entities.conversations.conversation import Conversation
from aios.entities.users.permission import Permission
from aios.entities.users.user import User
from aios.storage.collection import Collection
from aios.web.prune_request import PruneRequest
from aios.web.request_body import RequestBody
from aios.web.start_conversation_request import StartConversationRequest
from aios.web.text_request import TextRequest
from aios.web.web_auth import WebAuth
from aios.web.web_caller import WebCaller
from aios.web.web_routes import WebRoutes

KEEPALIVE_SECONDS = 15
PREVIEW_CHARS = 120


class ConversationRoutes(WebRoutes):
    """Lists, reads, watches and deletes conversations, and chats in the web ones.

    Everyone sees, writes in and may delete the conversations they take part in;
    administrators all of them. A conversation is the unit, not a channel: writing
    here into one that lives in a Slack thread attaches the caller's web binding to
    it, so the reply goes to both places and the message is mirrored into Slack.

    A new conversation may go straight to one agent instead of the orchestrator;
    it stays with that agent, whose grants and approvals apply as always.
    """

    def __init__(
        self,
        conversations: Collection[Conversation],
        users: Collection[User],
        resolver: ConversationResolver,
        recorder: MessageRecorder,
        channel: WebChannel,
        hub: WebEventHub,
        deleter: ConversationDeleter,
        agents: AgentCatalog,
    ) -> None:
        self._conversations = conversations
        self._users = users
        self._resolver = resolver
        self._recorder = recorder
        self._channel = channel
        self._hub = hub
        self._deleter = deleter
        self._agents = agents

    def register(self, app: web.Application) -> None:
        app.router.add_get("/api/conversations", self._list)
        app.router.add_get("/api/chat/agents", self._chat_agents)
        app.router.add_post("/api/conversations", self._start)
        app.router.add_post("/api/conversations/prune", self._prune)
        app.router.add_delete("/api/conversations/{id}", self._delete)
        app.router.add_get("/api/conversations/{id}", self._read)
        app.router.add_post("/api/conversations/{id}/messages", self._say)
        app.router.add_post("/api/conversations/{id}/stop", self._stop)
        app.router.add_get("/api/conversations/{id}/events", self._events)

    async def _list(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        visible = [c for c in self._conversations.all() if self._may_read(caller, c)]
        visible.sort(key=lambda c: c.updated_at, reverse=True)
        limit = min(int(request.query.get("limit", "100")), 500)
        rows = []
        for conversation in visible[:limit]:
            history = await self._recorder.history(conversation.id)
            first = next((m.text for m in history if m.role == "user"), "")
            rows.append(
                {
                    **self._summary(caller, conversation),
                    "preview": first[:PREVIEW_CHARS],
                    "messages": len(history),
                    "last_at": history[-1].created_at.isoformat() if history else None,
                }
            )
        rows.sort(key=lambda r: r["last_at"] or r["updated_at"], reverse=True)
        return web.json_response({"conversations": rows})

    async def _read(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        conversation = self._visible(caller, request)
        history = await self._recorder.history(conversation.id)
        names = {u.id: u.name for u in self._users.all()}
        return web.json_response(
            {
                **self._summary(caller, conversation),
                "messages": [
                    {
                        "id": m.id,
                        "role": m.role,
                        "author": names.get(m.author_user_id or "", None),
                        "channel": m.channel,
                        "text": m.text,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in history
                ],
            }
        )

    async def _start(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        self._require_chat()
        body = await RequestBody.parse(request, StartConversationRequest)
        agent = None if body.agent in (None, AgentCatalog.ORCHESTRATOR) else body.agent
        try:
            self._agents.main(agent)
        except AgentUnavailableError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from exc
        binding = self._channel.new_binding(caller.account)
        conversation = await self._resolver.resolve(binding, caller.user, agent)
        self._channel.submit(binding, caller.account, body.text)
        return web.json_response({"id": conversation.id}, status=201)

    async def _chat_agents(self, request: web.Request) -> web.Response:
        """Who a new conversation can be started with."""
        WebAuth.caller(request)
        agents = [self._agents.orchestrator(), *self._agents.delegates()]
        return web.json_response(
            {"agents": [{"name": a.name, "description": a.description} for a in agents]}
        )

    async def _say(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        self._require_chat()
        binding = await self._web_binding(caller, self._visible(caller, request))
        body = await RequestBody.parse(request, TextRequest)
        self._channel.submit(binding, caller.account, body.text)
        return web.json_response({"ok": True}, status=202)

    async def _stop(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        self._require_chat()
        binding = await self._web_binding(caller, self._visible(caller, request))
        return web.json_response({"stopped": await self._channel.cancel(binding, caller.account)})

    async def _delete(self, request: web.Request) -> web.Response:
        caller = WebAuth.caller(request)
        await self._deleter.delete(self._visible(caller, request).id)
        return web.json_response({"ok": True})

    async def _prune(self, request: web.Request) -> web.Response:
        """Deletes the caller's visible conversations with nothing new for `days`."""
        caller = WebAuth.caller(request)
        body = await RequestBody.parse(request, PruneRequest)
        cutoff = datetime.now(UTC) - timedelta(days=body.days)
        deleted = 0
        for conversation in [c for c in self._conversations.all() if self._may_read(caller, c)]:
            history = await self._recorder.history(conversation.id)
            last = history[-1].created_at if history else conversation.updated_at
            if last < cutoff:
                await self._deleter.delete(conversation.id)
                deleted += 1
        return web.json_response({"deleted": deleted})

    async def _events(self, request: web.Request) -> web.StreamResponse:
        caller = WebAuth.caller(request)
        conversation = self._visible(caller, request)
        response = web.StreamResponse(
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )
        await response.prepare(request)
        queue = self._hub.subscribe(conversation.id)
        try:
            with contextlib.suppress(ConnectionResetError):
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), KEEPALIVE_SECONDS)
                    except TimeoutError:
                        await response.write(b": keepalive\n\n")
                        continue
                    await response.write(f"data: {event.model_dump_json()}\n\n".encode())
        finally:
            self._hub.unsubscribe(conversation.id, queue)
        return response

    def _summary(self, caller: WebCaller, conversation: Conversation) -> dict[str, object]:
        names = [
            u.name for uid in conversation.participants if (u := self._users.get(uid)) is not None
        ]
        return {
            "id": conversation.id,
            "title": conversation.title,
            "channels": sorted({b.channel for b in conversation.bindings}),
            "participants": names,
            "status": conversation.status,
            "agent": conversation.agent,
            "updated_at": conversation.updated_at.isoformat(),
            "writable": self._channel.ready,
        }

    def _visible(self, caller: WebCaller, request: web.Request) -> Conversation:
        conversation = self._conversations.get(request.match_info["id"])
        if conversation is None or not self._may_read(caller, conversation):
            raise web.HTTPNotFound(text="no such conversation")
        return conversation

    @staticmethod
    def _may_read(caller: WebCaller, conversation: Conversation) -> bool:
        return caller.can(Permission.ADMINISTER) or caller.user.id in conversation.participants

    async def _web_binding(self, caller: WebCaller, conversation: Conversation) -> ChannelBinding:
        """The caller's web binding of the conversation, attached on first use."""
        binding = self._find_own_binding(caller, conversation)
        if binding is None:
            binding = ChannelBinding(
                channel=caller.account.channel,
                address=caller.account.address,
                thread=conversation.id,
            )
            await self._resolver.attach(conversation, binding)
        return binding

    @staticmethod
    def _find_own_binding(caller: WebCaller, conversation: Conversation) -> ChannelBinding | None:
        return next(
            (
                b
                for b in conversation.bindings
                if b.channel == caller.account.channel and b.address == caller.account.address
            ),
            None,
        )

    def _require_chat(self) -> None:
        if not self._channel.ready:
            raise web.HTTPServiceUnavailable(text="the web channel is not enabled in config.yaml")
