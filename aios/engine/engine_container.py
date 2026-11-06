from dependency_injector import containers, providers

from aios.engine.agent_definitions_builder import AgentDefinitionsBuilder
from aios.engine.claude_agent_engine import ClaudeAgentEngine
from aios.engine.claude_connector_probe import ClaudeConnectorProbe
from aios.engine.claude_options_factory import ClaudeOptionsFactory
from aios.engine.progress_stream_mapper import ProgressStreamMapper
from aios.engine.system_prompt_builder import SystemPromptBuilder
from aios.engine.text_stream_mapper import TextStreamMapper
from aios.engine.tool_permission_gate import ToolPermissionGate
from aios.progress.progress_labeler import ProgressLabeler


class EngineContainer(containers.DeclarativeContainer):
    agent_config = providers.Dependency()
    repo_dir = providers.Dependency()
    timezone = providers.Dependency()
    memories = providers.Dependency()
    agents = providers.Dependency()
    connectors = providers.Dependency()
    board = providers.Dependency()
    tool_server = providers.Dependency()
    policy = providers.Dependency()
    approvals = providers.Dependency()
    clock = providers.Dependency()

    labeler = providers.Singleton(ProgressLabeler)
    mapper = providers.Singleton(ProgressStreamMapper, labeler=labeler)
    gate = providers.Singleton(ToolPermissionGate, policy=policy, approvals=approvals)
    prompts = providers.Singleton(
        SystemPromptBuilder,
        agents=agents,
        clock=clock,
        timezone=timezone,
        memories=memories,
        connectors=connectors,
    )
    definitions = providers.Singleton(
        AgentDefinitionsBuilder, agents=agents, connectors=connectors, board=board
    )
    options_factory = providers.Singleton(
        ClaudeOptionsFactory,
        agent_config=agent_config,
        repo_dir=repo_dir,
        prompts=prompts,
        tool_server=tool_server,
        gate=gate,
        agents=agents,
        connectors=connectors,
        definitions=definitions,
    )
    connector_probe = providers.Singleton(
        ClaudeConnectorProbe, connectors=connectors, board=board, repo_dir=repo_dir
    )
    engine = providers.Singleton(
        ClaudeAgentEngine,
        options_factory=options_factory,
        mapper=mapper,
        text_mapper=providers.Singleton(TextStreamMapper),
        timeout_seconds=agent_config.provided.turn_timeout_seconds,
        board=board,
    )
