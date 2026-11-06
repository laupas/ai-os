from dependency_injector import containers, providers

from aios.web.restart_request import RestartRequest
from aios.web.routes.agent_routes import AgentRoutes
from aios.web.routes.approval_routes import ApprovalRoutes
from aios.web.routes.connector_auth_routes import ConnectorAuthRoutes
from aios.web.routes.connector_routes import ConnectorRoutes
from aios.web.routes.conversation_routes import ConversationRoutes
from aios.web.routes.git_routes import GitRoutes
from aios.web.routes.health_routes import HealthRoutes
from aios.web.routes.history_routes import HistoryRoutes
from aios.web.routes.log_routes import LogRoutes
from aios.web.routes.memory_routes import MemoryRoutes
from aios.web.routes.schedule_routes import ScheduleRoutes
from aios.web.routes.settings_routes import SettingsRoutes
from aios.web.routes.skill_routes import SkillRoutes
from aios.web.routes.variable_routes import VariableRoutes
from aios.web.web_auth import WebAuth
from aios.web.web_identity_factory import WebIdentityFactory
from aios.web.web_server import WebServer


class WebContainer(containers.DeclarativeContainer):
    """The web console. A new API area is a `WebRoutes` class plus an entry in
    `routes`."""

    app_config = providers.Dependency()
    config_file = providers.Dependency()
    users = providers.Dependency()
    roles = providers.Dependency()
    conversations = providers.Dependency()
    approvals = providers.Dependency()
    memories = providers.Dependency()
    schedules = providers.Dependency()
    authorizer = providers.Dependency()
    channels = providers.Dependency()
    web_channel = providers.Dependency()
    web_hub = providers.Dependency()
    deleter = providers.Dependency()
    senders = providers.Dependency()
    resolver = providers.Dependency()
    recorder = providers.Dependency()
    approval_service = providers.Dependency()
    schedule_timing = providers.Dependency()
    schedule_runner = providers.Dependency()
    log_reader = providers.Dependency()
    clock = providers.Dependency()
    ids = providers.Dependency()
    agents = providers.Dependency()
    skills = providers.Dependency()
    connectors = providers.Dependency()
    connector_catalog = providers.Dependency()
    connector_board = providers.Dependency()
    connector_authorizer = providers.Dependency()
    connector_tokens = providers.Dependency()
    variable_catalog = providers.Dependency()
    variable_resolver = providers.Dependency()
    connector_probe = providers.Dependency(default=None)
    secret_extractor = providers.Dependency(default=None)
    config_store = providers.Dependency()
    config_collections = providers.Dependency()
    config_branches = providers.Dependency()
    config_remote = providers.Dependency()

    identity = providers.Singleton(WebIdentityFactory.create, app_config.provided.web)
    auth = providers.Singleton(WebAuth, identity=identity, users=users, authorizer=authorizer)
    restart = providers.Singleton(RestartRequest)

    routes = providers.List(
        providers.Singleton(
            HealthRoutes,
            config=app_config,
            channels=channels,
            senders=senders,
            conversations=conversations,
            approvals=approvals,
            memories=memories,
            schedules=schedules,
            users=users,
            log_reader=log_reader,
            clock=clock,
            connectors=connector_catalog,
        ),
        providers.Singleton(LogRoutes, log_reader=log_reader, clock=clock),
        providers.Singleton(
            ConversationRoutes,
            conversations=conversations,
            users=users,
            resolver=resolver,
            recorder=recorder,
            channel=web_channel,
            hub=web_hub,
            deleter=deleter,
            agents=agents,
            approvals=approvals,
        ),
        providers.Singleton(ApprovalRoutes, approvals=approvals, service=approval_service),
        providers.Singleton(
            ScheduleRoutes,
            schedules=schedules,
            timing=schedule_timing,
            runner=schedule_runner,
            clock=clock,
            ids=ids,
            users=users,
            agents=agents,
        ),
        providers.Singleton(MemoryRoutes, memories=memories, ids=ids, clock=clock),
        providers.Singleton(
            AgentRoutes,
            agents=agents,
            skills=skills,
            connectors=connector_catalog,
            board=connector_board,
            builtin_tools=app_config.provided.agent.builtin_tools,
        ),
        providers.Singleton(SkillRoutes, skills=skills, agents=agents),
        providers.Singleton(HistoryRoutes, store=config_store, collections=config_collections),
        providers.Singleton(GitRoutes, branches=config_branches, remote=config_remote),
        providers.Singleton(
            ConnectorRoutes,
            connectors=connectors,
            catalog=connector_catalog,
            board=connector_board,
            agents=agents,
            authorizer=connector_authorizer,
            tokens=connector_tokens,
            resolver=variable_resolver,
            probe=connector_probe,
            secrets=secret_extractor,
        ),
        providers.Singleton(
            VariableRoutes,
            variables=variable_catalog,
            resolver=variable_resolver,
            connectors=connector_catalog,
        ),
        providers.Singleton(
            ConnectorAuthRoutes,
            authorizer=connector_authorizer,
            catalog=connector_catalog,
            public_url=app_config.provided.web.public_url,
        ),
        providers.Singleton(
            SettingsRoutes,
            config_file=config_file,
            users=users,
            roles=roles,
            ids=ids,
            restart=restart,
            store=config_store,
        ),
    )
    server = providers.Singleton(
        WebServer,
        auth=auth,
        routes=routes,
        restart=restart,
        port=app_config.provided.web.port,
    )
