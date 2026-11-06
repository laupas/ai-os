from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.agent_tracker import AgentTracker
from aios.config.agent_config import AgentConfig
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.engine.agent_definitions_builder import AgentDefinitionsBuilder
from aios.engine.system_prompt_builder import SystemPromptBuilder
from aios.engine.tool_permission_gate import ToolPermissionGate
from aios.engine.turn_deadline import TurnDeadline
from aios.engine.turn_request import TurnRequest
from aios.tools.aios_tool_server import AiosToolServer
from aios.tools.tool_context import ToolContext


class ClaudeOptionsFactory:
    """Builds the SDK options for one turn.

    Agents come from the agent catalog (`agents=`), never from `.claude/agents`;
    skills load from `.claude/skills` through `setting_sources=["project"]`, filtered
    to those an enabled agent may use. `allowed_tools` stays empty on purpose: every
    tool call goes through the permission gate, which knows which agent is calling.

    The main thread is the orchestrator, or the agent the conversation was started
    with; subagents are offered only to a main agent that may delegate.

    Background tasks are switched off. The CLI runs a subagent in the background
    unless told otherwise, and a turn ends when the main thread stops writing: the
    session closes, `can_use_tool` goes with it, and every call the subagent makes
    after that fails with "Stream closed". The user is told a result will follow
    and nothing ever does.
    """

    ENV = {"CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"}

    def __init__(
        self,
        agent_config: AgentConfig,
        repo_dir: Path,
        prompts: SystemPromptBuilder,
        tool_server: AiosToolServer,
        gate: ToolPermissionGate,
        agents: AgentCatalog,
        connectors: ConnectorCatalog,
        definitions: AgentDefinitionsBuilder,
    ) -> None:
        self._config = agent_config
        self._repo_dir = Path(repo_dir)
        self._prompts = prompts
        self._tool_server = tool_server
        self._gate = gate
        self._agents = agents
        self._connectors = connectors
        self._definitions = definitions

    def create(
        self, request: TurnRequest, resume: str | None, deadline: TurnDeadline | None = None
    ) -> ClaudeAgentOptions:
        context = ToolContext(
            conversation_id=request.conversation.id, user=request.user, binding=request.binding
        )
        main = self._agents.main(request.conversation.agent)
        delegating = self._definitions.delegates_work(main)
        tracker = AgentTracker(main.name)
        return ClaudeAgentOptions(
            system_prompt=self._prompts.build(request),
            cwd=str(self._repo_dir),
            setting_sources=["project"],
            tools=list(self._config.builtin_tools),
            allowed_tools=[],
            agents=self._definitions.build() if delegating else {},
            skills=self._definitions.skills(main, delegating),
            mcp_servers={
                **self._connectors.servers(),  # type: ignore[dict-item]
                AiosToolServer.SERVER_NAME: self._tool_server.build(context),
            },
            # Only our servers: never MCP connectors of whichever account runs this.
            strict_mcp_config=True,
            hooks=tracker.hooks(),  # type: ignore[arg-type]
            can_use_tool=self._gate.for_context(context, tracker, deadline),
            permission_mode="default",
            env=dict(self.ENV),
            resume=resume,
            model=main.model or self._config.model,
            # Partial messages let a channel show the reply while it is written.
            include_partial_messages=True,
        )
