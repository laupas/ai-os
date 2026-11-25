from pathlib import Path

from dependency_injector import containers, providers

from aios.agents.agents_container import AgentsContainer
from aios.approvals.approval_policy_container import ApprovalPolicyContainer
from aios.approvals.approvals_container import ApprovalsContainer
from aios.bootstrap.application import Application
from aios.bootstrap.startup_notice import StartupNotice
from aios.channels.channels_container import ChannelsContainer
from aios.common.common_container import CommonContainer
from aios.config.app_config_watcher import AppConfigWatcher
from aios.config.config_container import ConfigContainer
from aios.config_repo.config_repo_container import ConfigRepoContainer
from aios.connectors.code_connector_library import CodeConnectorLibrary
from aios.connectors.connector_settings_migration import ConnectorSettingsMigration
from aios.connectors.connectors_container import ConnectorsContainer
from aios.conversations.conversations_container import ConversationsContainer
from aios.conversations.gateway_container import GatewayContainer
from aios.engine.engine_container import EngineContainer
from aios.logs.log_reader import LogReader
from aios.storage.storage_container import StorageContainer
from aios.store.store_container import StoreContainer
from aios.tools.tools_container import ToolsContainer
from aios.transcription.transcription_container import TranscriptionContainer
from aios.triggers.triggers_container import TriggersContainer
from aios.triggers.triggers_migration import TriggersMigration
from aios.users.access_lists_migration import AccessListsMigration
from aios.users.groups_migration import GroupsMigration
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
        groups=storage.groups,
        owner=app_config.provided.owner,
        ids=common.ids,
    )
    variables = providers.Container(
        VariablesContainer,
        variables=storage.variables,
        settings=config.settings,
        clock=common.clock,
    )
    transcription = providers.Container(TranscriptionContainer, resolver=variables.resolver)
    channels = providers.Container(
        ChannelsContainer,
        config=app_config.provided.channels,
        resolver=variables.resolver,
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
        approval_config=config.approval,
        conversations=storage.conversations,
        observers=providers.List(channels.web_hub),
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
    # Code connectors belong to the installation: they are in its configuration
    # repository, never in ai-os itself.
    code_roots = providers.List(
        providers.Callable(lambda s: s.config_dir() / "code", config.settings),
    )
    tools = providers.Container(
        ToolsContainer,
        users=storage.users,
        authorizer=users.authorizer,
        senders=channels.senders,
        webhooks=storage.webhooks,
        webhook_poster=channels.webhook_poster,
        recorder=conversations.recorder,
        conversations=storage.conversations,
        approvals=approvals.service,
        registry=storage.registry,
        ids=common.ids,
        clock=common.clock,
        log_reader=log_reader,
        agents=storage.agents,
        skills=storage.skills,
        connectors=storage.connectors,
        secret_extractor=variables.extractor,
        code_library=providers.Singleton(CodeConnectorLibrary, roots=code_roots),
    )
    connectors = providers.Container(
        ConnectorsContainer,
        expander=variables.resolver,
        connectors=storage.connectors,
        tokens=storage.connector_tokens,
        builtin_tools=tools.server.provided.tool_names.call(),
        clock=common.clock,
        box=variables.box,
        code_roots=code_roots,
        state_root=providers.Callable(lambda s: s.data_dir / "connector-state", config.settings),
        timezone=config.timezone,
        tools_file=providers.Callable(
            lambda s: s.data_dir / "connector-tools.json", config.settings
        ),
    )
    agents = providers.Container(
        AgentsContainer,
        agents=storage.agents,
        skills=storage.skills,
        connectors=connectors.catalog,
        audience=users.audience,
    )
    approval_policy = providers.Container(
        ApprovalPolicyContainer,
        approval_config=config.approval,
        files_config=config.files,
        # ai-os's own data and code, the decrypted variables, and the Claude CLI's
        # sign-ins: never reachable by the file tools, whatever aios.yaml says.
        protected_dirs=providers.Callable(
            lambda s: [s.data_dir, s.repo_dir, s.variable_files_dir(), Path.home() / ".claude"],
            config.settings,
        ),
        builtin_tools=providers.Callable(lambda agent: lambda: agent().builtin_tools, config.agent),
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
        agent_config=config.agent,
        repo_dir=config.settings.provided.repo_dir,
        timezone=config.timezone,
        memories=storage.memories,
        agents=agents.catalog,
        connectors=connectors.catalog,
        board=connectors.board,
        tool_server=tools.server,
        policy=approval_policy.policy,
        approvals=approvals.service,
        clock=common.clock,
        variable_resolver=variables.resolver,
        audience=users.audience,
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
    triggers = providers.Container(
        TriggersContainer,
        triggers=storage.triggers,
        users=storage.users,
        channels=channels.directory,
        turns=gateway.gateway,
        clock=common.clock,
        triggers_config=config.triggers,
    )

    # What the configuration repository holds, one file per document.
    config_collections = providers.List(
        storage.agents,
        storage.skills,
        storage.connectors,
        storage.triggers,
        storage.roles,
        storage.groups,
        storage.webhooks,
    )
    config_repo = providers.Container(
        ConfigRepoContainer,
        repo_dir=config.settings.provided.repo_dir,
        store=storage.config_store,
        legacy_store=storage.document_store,
        collections=config_collections,
        mcp_servers=app_config.provided.mcp_servers,
        remotes=storage.git_remotes,
        box=variables.box,
        clock=common.clock,
        known_hosts=config.settings.provided.known_hosts_file.call(),
        settings=config.settings,
    )
    store = providers.Container(
        StoreContainer,
        root=providers.Callable(lambda s: s.data_dir / "store", config.settings),
        sources=providers.Callable(lambda live: lambda: live.current().store.sources, config.live),
        config_store=storage.config_store,
        agents=agents.catalog,
        skills=agents.skill_catalog,
        connectors=storage.connectors,
        triggers=storage.triggers,
        variables=variables.catalog,
        ids=common.ids,
        clock=common.clock,
        secrets=variables.extractor,
    )
    web = providers.Container(
        WebContainer,
        app_config=app_config,
        live_config=config.live,
        agent_config=config.agent,
        config_file=config.settings.provided.resolved_config_file.call(),
        users=storage.users,
        groups=storage.groups,
        audience=users.audience,
        conversations=storage.conversations,
        approvals=storage.approvals,
        memories=storage.memories,
        triggers=storage.triggers,
        authorizer=users.authorizer,
        channels=channels.directory,
        web_channel=channels.web,
        web_hub=channels.web_hub,
        deleter=conversations.deleter,
        senders=channels.senders,
        webhooks=storage.webhooks,
        webhook_poster=channels.webhook_poster,
        channel_catalog=channels.catalog,
        channel_values=channels.values,
        file_root_guard=approval_policy.file_root_guard,
        collection_overrides=storage.collection_overrides,
        resolver=conversations.resolver,
        recorder=conversations.recorder,
        approval_service=approvals.service,
        trigger_timing=triggers.timing,
        trigger_runner=triggers.runner,
        triggers_config=config.triggers,
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
        config_collections=config_collections,
        config_branches=config_repo.branches,
        config_remote=config_repo.remote,
        audit_trail=storage.audit_trail,
        claude_credentials=engine.credentials,
        claude_sign_in_check=engine.sign_in_check,
        code_connectors=connectors.code,
        repository_files=config_repo.files,
        transcriber=transcription.transcriber,
        web_passwords=storage.web_passwords,
        web_sessions=storage.web_sessions,
        appearances=storage.appearances,
        owner_password=config.settings.provided.owner_password,
        secret_box=variables.box,
        store_sources=store.catalog,
        store_installer=store.installer,
    )

    # aios.yaml applied while ai-os runs. In the configuration repository only a
    # commit counts, as for the rest of the configuration.
    app_config_watcher = providers.Singleton(
        AppConfigWatcher, config=config.live, read=web.aios_yaml.provided.read_committed
    )
    # The triggers loop always runs: it reads `triggers.enabled` on every tick.
    background = providers.Callable(
        lambda config, yaml_watcher, watcher, renewer, loop, server: [
            yaml_watcher,
            watcher,
            renewer,
            loop,
            *([server] if config.web.enabled else []),
        ],
        app_config,
        app_config_watcher,
        config_repo.watcher,
        connectors.renewer,
        triggers.loop,
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
            providers.Singleton(
                TriggersMigration,
                store=storage.config_store,
                state=storage.document_store,
                collections=config_collections,
                config=web.aios_yaml,
            ),
            providers.Singleton(
                AccessListsMigration,
                store=storage.config_store,
                agents=storage.agents,
                connectors=storage.connectors,
            ),
            providers.Singleton(
                GroupsMigration,
                store=storage.config_store,
                users=storage.users,
                roles=storage.roles,
                groups=storage.groups,
                config=web.aios_yaml,
            ),
            users.bootstrapper,
            web.owner_password_seed,
            config_repo.remote_from_env,
            config_repo.skills_link,
            connectors.migration,
            providers.Singleton(
                ConnectorSettingsMigration, config=web.aios_yaml, connectors=storage.connectors
            ),
        ),
        approvals=approvals.service,
        channels=channels.directory,
        gateway=gateway.gateway,
        background=background,
        notice=notice,
    )
