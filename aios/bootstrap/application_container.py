from dependency_injector import containers, providers

from aios.agents.agents_container import AgentsContainer
from aios.approvals.approval_policy_container import ApprovalPolicyContainer
from aios.approvals.approvals_container import ApprovalsContainer
from aios.bootstrap.application import Application
from aios.bootstrap.startup_notice import StartupNotice
from aios.channels.channels_container import ChannelsContainer
from aios.common.common_container import CommonContainer
from aios.config.config_container import ConfigContainer
from aios.config_repo.config_repo_container import ConfigRepoContainer
from aios.connectors.connectors_container import ConnectorsContainer
from aios.conversations.conversations_container import ConversationsContainer
from aios.conversations.gateway_container import GatewayContainer
from aios.engine.engine_container import EngineContainer
from aios.logs.log_reader import LogReader
from aios.messaging.messaging_container import MessagingContainer
from aios.scheduler.scheduler_container import SchedulerContainer
from aios.storage.storage_container import StorageContainer
from aios.tools.tools_container import ToolsContainer
from aios.transcription.transcription_container import TranscriptionContainer
from aios.users.users_container import UsersContainer
from aios.variables.variables_container import VariablesContainer
from aios.web.web_container import WebContainer


class ApplicationContainer(containers.DeclarativeContainer):
    """Composes the domain containers. Order matters: each one only uses those above."""

    config = providers.Container(ConfigContainer)
    common = providers.Container(CommonContainer)
    app_config = config.app_config

    storage = providers.Container(
        StorageContainer,
        data_dir=config.settings.provided.data_dir,
        access_overrides=app_config.provided.collection_access,
        config_dir=config.settings.provided.config_dir.call(),
        clock=common.clock,
    )
    users = providers.Container(
        UsersContainer,
        users=storage.users,
        roles=storage.roles,
        owner=app_config.provided.owner,
        ids=common.ids,
    )
    transcription = providers.Container(TranscriptionContainer, settings=config.settings)
    channels = providers.Container(
        ChannelsContainer,
        settings=config.settings,
        enabled=app_config.provided.channels,
        transcriber=transcription.transcriber,
        ids=common.ids,
    )
    approvals = providers.Container(
        ApprovalsContainer,
        approvals=storage.approvals,
        users=storage.users,
        authorizer=users.authorizer,
        presenters=channels.directory,
        clock=common.clock,
        ids=common.ids,
        approval_config=app_config.provided.approval,
        conversations=storage.conversations,
        observers=providers.List(channels.web_hub),
    )
    messaging = providers.Container(
        MessagingContainer,
        settings=config.settings,
        enabled=app_config.provided.senders,
    )
    conversations = providers.Container(
        ConversationsContainer,
        conversations=storage.conversations,
        append_log=storage.append_log,
        clock=common.clock,
        ids=common.ids,
        observers=providers.List(channels.web_hub),
    )
    log_reader = providers.Singleton(LogReader, log_file=config.settings.provided.log_file.call())
    variables = providers.Container(
        VariablesContainer,
        variables=storage.variables,
        settings=config.settings,
        clock=common.clock,
    )
    tools = providers.Container(
        ToolsContainer,
        users=storage.users,
        authorizer=users.authorizer,
        senders=messaging.directory,
        recorder=conversations.recorder,
        approvals=approvals.service,
        registry=storage.registry,
        ids=common.ids,
        clock=common.clock,
        log_reader=log_reader,
        agents=storage.agents,
        skills=storage.skills,
        connectors=storage.connectors,
        secret_extractor=variables.extractor,
    )
    connectors = providers.Container(
        ConnectorsContainer,
        expander=variables.resolver,
        connectors=storage.connectors,
        tokens=storage.connector_tokens,
        builtin_tools=tools.server.provided.tool_names.call(),
        clock=common.clock,
        box=variables.box,
        # Code connectors belong to the installation: they are in its configuration
        # repository, never in ai-os itself.
        code_roots=providers.List(
            providers.Callable(lambda s: s.config_dir() / "code", config.settings),
        ),
        overrides=app_config.provided.connectors,
        state_root=providers.Callable(lambda s: s.data_dir / "connector-state", config.settings),
        timezone=app_config.provided.timezone,
    )
    agents = providers.Container(
        AgentsContainer,
        agents=storage.agents,
        skills=storage.skills,
        connectors=connectors.catalog,
    )
    approval_policy = providers.Container(
        ApprovalPolicyContainer,
        approval_config=app_config.provided.approval,
        files_config=app_config.provided.files,
        builtin_tools=app_config.provided.agent.builtin_tools,
        tool_prefixes=connectors.catalog.provided.tool_prefixes,
        extra_rules=providers.Callable(
            lambda grant, code, rules: [grant, code, *rules],
            agents.grant_rule,
            connectors.approval_rule,
            tools.approval_rules,
        ),
    )
    engine = providers.Container(
        EngineContainer,
        agent_config=app_config.provided.agent,
        repo_dir=config.settings.provided.repo_dir,
        timezone=app_config.provided.timezone,
        memories=storage.memories,
        agents=agents.catalog,
        connectors=connectors.catalog,
        board=connectors.board,
        tool_server=tools.server,
        policy=approval_policy.policy,
        approvals=approvals.service,
        clock=common.clock,
        variable_resolver=variables.resolver,
    )
    gateway = providers.Container(
        GatewayContainer,
        users=storage.users,
        authorizer=users.authorizer,
        resolver=conversations.resolver,
        recorder=conversations.recorder,
        locks=conversations.locks,
        canceller=conversations.canceller,
        engine=engine.engine,
        channels=channels.directory,
        approvals=approvals.service,
        observers=providers.List(channels.web_hub),
    )
    scheduler = providers.Container(
        SchedulerContainer,
        schedules=storage.schedules,
        users=storage.users,
        channels=channels.directory,
        turns=gateway.gateway,
        clock=common.clock,
        scheduler_config=app_config.provided.scheduler,
    )

    config_repo = providers.Container(
        ConfigRepoContainer,
        repo_dir=config.settings.provided.repo_dir,
        store=storage.config_store,
        legacy_store=storage.document_store,
        collections=providers.List(
            storage.agents, storage.skills, storage.connectors, storage.schedules, storage.roles
        ),
        mcp_servers=app_config.provided.mcp_servers,
        remotes=storage.git_remotes,
        box=variables.box,
        clock=common.clock,
        known_hosts=config.settings.provided.known_hosts_file.call(),
        settings=config.settings,
    )
    web = providers.Container(
        WebContainer,
        app_config=app_config,
        config_file=config.settings.provided.resolved_config_file.call(),
        users=storage.users,
        roles=storage.roles,
        conversations=storage.conversations,
        approvals=storage.approvals,
        memories=storage.memories,
        schedules=storage.schedules,
        authorizer=users.authorizer,
        channels=channels.directory,
        web_channel=channels.web,
        web_hub=channels.web_hub,
        deleter=conversations.deleter,
        senders=messaging.directory,
        resolver=conversations.resolver,
        recorder=conversations.recorder,
        approval_service=approvals.service,
        schedule_timing=scheduler.timing,
        schedule_runner=scheduler.runner,
        log_reader=log_reader,
        clock=common.clock,
        ids=common.ids,
        agents=agents.catalog,
        skills=agents.skill_catalog,
        connectors=storage.connectors,
        connector_catalog=connectors.catalog,
        connector_board=connectors.board,
        connector_authorizer=connectors.authorizer,
        connector_tokens=connectors.token_store,
        variable_catalog=variables.catalog,
        variable_resolver=variables.resolver,
        connector_probe=engine.connector_probe,
        secret_extractor=variables.extractor,
        config_store=storage.config_store,
        config_collections=providers.List(
            storage.agents, storage.skills, storage.connectors, storage.schedules, storage.roles
        ),
        config_branches=config_repo.branches,
        config_remote=config_repo.remote,
        audit_trail=storage.audit_trail,
        claude_credentials=engine.credentials,
        code_connectors=connectors.code,
        repository_files=config_repo.files,
    )

    background = providers.Callable(
        lambda config, watcher, renewer, loop, server: [
            watcher,
            renewer,
            *([loop] if config.scheduler.enabled else []),
            *([server] if config.web.enabled else []),
        ],
        app_config,
        config_repo.watcher,
        connectors.renewer,
        scheduler.loop,
        web.server,
    )
    notice = providers.Singleton(
        StartupNotice,
        users=storage.users,
        channels=channels.directory,
        clock=common.clock,
        marker=config.settings.provided.startup_notice_file.call(),
    )
    application = providers.Singleton(
        Application,
        registry=storage.registry,
        startup=providers.List(
            # The repository first: roles live in it, and the owner needs them.
            config_repo.initializer,
            users.bootstrapper,
            config_repo.remote_from_env,
            config_repo.skills_link,
            connectors.migration,
        ),
        approvals=approvals.service,
        channels=channels.directory,
        gateway=gateway.gateway,
        background=background,
        notice=notice,
    )
