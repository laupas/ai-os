from dependency_injector import containers, providers

from aios.audit.audit_feed import AuditFeed
from aios.audit.config_history import ConfigHistory
from aios.web.aios_yaml_file import AiosYamlFile
from aios.web.audit_middleware import AuditMiddleware
from aios.web.login.chat_code_login import ChatCodeLogin
from aios.web.login.code_messenger import CodeMessenger
from aios.web.login.console_users import ConsoleUsers
from aios.web.login.login_throttle import LoginThrottle
from aios.web.login.password_hasher import PasswordHasher
from aios.web.login.password_login import PasswordLogin
from aios.web.login.pick_login import PickLogin
from aios.web.login.sign_in_codes import SignInCodes
from aios.web.login.web_passwords import WebPasswords
from aios.web.login.web_sessions import WebSessions
from aios.web.restart_request import RestartRequest
from aios.web.routes.agent_routes import AgentRoutes
from aios.web.routes.approval_routes import ApprovalRoutes
from aios.web.routes.audit_routes import AuditRoutes
from aios.web.routes.channel_settings_routes import ChannelSettingsRoutes
from aios.web.routes.claude_settings_routes import ClaudeSettingsRoutes
from aios.web.routes.connector_auth_routes import ConnectorAuthRoutes
from aios.web.routes.connector_routes import ConnectorRoutes
from aios.web.routes.conversation_routes import ConversationRoutes
from aios.web.routes.files_settings_routes import FilesSettingsRoutes
from aios.web.routes.git_routes import GitRoutes
from aios.web.routes.health_routes import HealthRoutes
from aios.web.routes.history_routes import HistoryRoutes
from aios.web.routes.log_routes import LogRoutes
from aios.web.routes.login_routes import LoginRoutes
from aios.web.routes.memory_routes import MemoryRoutes
from aios.web.routes.password_routes import PasswordRoutes
from aios.web.routes.repository_routes import RepositoryRoutes
from aios.web.routes.settings_routes import SettingsRoutes
from aios.web.routes.settings_section_routes import SettingsSectionRoutes
from aios.web.routes.skill_routes import SkillRoutes
from aios.web.routes.store_routes import StoreRoutes
from aios.web.routes.trigger_hook_routes import TriggerHookRoutes
from aios.web.routes.trigger_routes import TriggerRoutes
from aios.web.routes.variable_routes import VariableRoutes
from aios.web.routes.voice_routes import VoiceRoutes
from aios.web.routes.voice_settings_routes import VoiceSettingsRoutes
from aios.web.routes.web_auth_settings_routes import WebAuthSettingsRoutes
from aios.web.routes.webhook_routes import WebhookRoutes
from aios.web.web_auth import WebAuth
from aios.web.web_identity_factory import WebIdentityFactory
from aios.web.web_server import WebServer


class WebContainer(containers.DeclarativeContainer):
    """The web console. A new API area is a `WebRoutes` class plus an entry in
    `routes`."""

    app_config = providers.Dependency()  # aios.yaml as ai-os started
    live_config = providers.Dependency()
    agent_config = providers.Dependency()  # a getter: `agent` as it is now
    config_file = providers.Dependency()
    users = providers.Dependency()
    roles = providers.Dependency()
    conversations = providers.Dependency()
    approvals = providers.Dependency()
    memories = providers.Dependency()
    triggers = providers.Dependency()
    authorizer = providers.Dependency()
    channels = providers.Dependency()
    web_channel = providers.Dependency()
    web_hub = providers.Dependency()
    deleter = providers.Dependency()
    senders = providers.Dependency()
    webhooks = providers.Dependency()
    webhook_poster = providers.Dependency()
    resolver = providers.Dependency()
    recorder = providers.Dependency()
    approval_service = providers.Dependency()
    trigger_timing = providers.Dependency()
    trigger_runner = providers.Dependency()
    triggers_config = providers.Dependency()  # a getter: `triggers` as it is now
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
    audit_trail = providers.Dependency()
    claude_credentials = providers.Dependency(default=None)
    claude_sign_in_check = providers.Dependency(default=None)
    channel_catalog = providers.Dependency()
    channel_values = providers.Dependency()
    file_root_guard = providers.Dependency()
    collection_overrides = providers.Dependency(default=None)
    code_connectors = providers.Dependency(default=None)
    repository_files = providers.Dependency()
    transcriber = providers.Dependency()
    web_passwords = providers.Dependency()
    secret_box = providers.Dependency()
    store_sources = providers.Dependency()
    store_installer = providers.Dependency()

    # The console's own login (`web.auth.mode` pick, password or code). A new way of
    # signing in is a `WebLogin` plus an entry in `logins`.
    console_users = providers.Singleton(ConsoleUsers, users=users, authorizer=authorizer)
    passwords = providers.Singleton(
        WebPasswords,
        passwords=web_passwords,
        hasher=providers.Singleton(PasswordHasher),
        clock=clock,
    )
    sessions = providers.Singleton(
        WebSessions, key=secret_box.provided.derive_key.call("web-session"), clock=clock
    )
    logins = providers.List(
        providers.Singleton(PickLogin, users=console_users),
        providers.Singleton(
            PasswordLogin,
            users=console_users,
            passwords=passwords,
            throttle=providers.Singleton(LoginThrottle, clock=clock),
        ),
        providers.Singleton(
            ChatCodeLogin,
            users=console_users,
            codes=providers.Singleton(SignInCodes, clock=clock),
            messenger=providers.Singleton(CodeMessenger, channels=channels, senders=senders),
            throttle=providers.Singleton(LoginThrottle, clock=clock),
        ),
    )
    identities = providers.Singleton(
        WebIdentityFactory, sessions=sessions, users=console_users, logins=logins
    )
    login = providers.Singleton(
        lambda factory, web: factory.login_for(web.effective_auth()),
        identities,
        app_config.provided.web,
    )
    identity = providers.Singleton(
        lambda factory, web: factory.create(web), identities, app_config.provided.web
    )
    auth = providers.Singleton(
        WebAuth,
        identity=identity,
        users=users,
        authorizer=authorizer,
        login_page=providers.Callable(lambda login: login is not None, login),
    )
    restart = providers.Singleton(RestartRequest)
    aios_yaml = providers.Singleton(
        AiosYamlFile, config_file=config_file, store=config_store, live=live_config
    )
    audit = providers.Singleton(AuditMiddleware, trail=audit_trail)
    audit_feed = providers.Singleton(
        AuditFeed,
        trail=audit_trail,
        history=providers.Singleton(ConfigHistory, repo=config_store.provided.repo),
    )

    routes = providers.List(
        providers.Singleton(
            HealthRoutes,
            config=app_config,
            channels=channels,
            senders=senders,
            conversations=conversations,
            approvals=approvals,
            memories=memories,
            triggers=triggers,
            users=users,
            log_reader=log_reader,
            clock=clock,
            connectors=connector_catalog,
            credentials=claude_credentials,
        ),
        providers.Singleton(
            LoginRoutes,
            login=login,
            sessions=sessions,
            days=providers.Callable(
                lambda web: web.effective_auth().session_days, app_config.provided.web
            ),
        ),
        providers.Singleton(
            PasswordRoutes, passwords=passwords, users=users, authorizer=authorizer
        ),
        providers.Singleton(LogRoutes, log_reader=log_reader, clock=clock),
        providers.Singleton(AuditRoutes, feed=audit_feed),
        providers.Singleton(RepositoryRoutes, files=repository_files),
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
        providers.Singleton(VoiceRoutes, transcriber=transcriber),
        providers.Singleton(
            StoreRoutes,
            sources=store_sources,
            installer=store_installer,
            config=aios_yaml,
            resolver=variable_resolver,
        ),
        providers.Singleton(
            TriggerRoutes,
            triggers=triggers,
            timing=trigger_timing,
            runner=trigger_runner,
            clock=clock,
            ids=ids,
            users=users,
            agents=agents,
        ),
        providers.Singleton(
            TriggerHookRoutes,
            triggers=triggers,
            runner=trigger_runner,
            clock=clock,
            config=triggers_config,
        ),
        providers.Singleton(MemoryRoutes, memories=memories, users=users, ids=ids, clock=clock),
        providers.Singleton(
            AgentRoutes,
            agents=agents,
            skills=skills,
            connectors=connector_catalog,
            board=connector_board,
            builtin_tools=providers.Callable(
                lambda agent: lambda: agent().builtin_tools, agent_config
            ),
        ),
        providers.Singleton(SkillRoutes, skills=skills, agents=agents),
        providers.Singleton(HistoryRoutes, store=config_store, collections=config_collections),
        providers.Singleton(
            WebhookRoutes, destinations=webhooks, poster=webhook_poster, secrets=secret_extractor
        ),
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
            code=code_connectors,
            variables=variable_catalog,
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
            config=aios_yaml,
            live=live_config,
            users=users,
            roles=roles,
            ids=ids,
            restart=restart,
        ),
        providers.Singleton(
            SettingsSectionRoutes, config=aios_yaml, collections=collection_overrides
        ),
        providers.Singleton(
            VoiceSettingsRoutes, variables=variable_catalog, resolver=variable_resolver
        ),
        providers.Singleton(WebAuthSettingsRoutes, config=aios_yaml, identities=identities),
        providers.Singleton(FilesSettingsRoutes, config=aios_yaml, guard=file_root_guard),
        providers.Singleton(
            ChannelSettingsRoutes,
            config=aios_yaml,
            catalog=channel_catalog,
            values=channel_values,
            variables=variable_catalog,
            running=providers.Callable(
                lambda chat, send, hooks: [
                    *chat.names(),
                    *send.names(),
                    *(["webhook"] if hooks.enabled else []),
                ],
                channels,
                senders,
                webhook_poster,
            ),
        ),
        providers.Singleton(
            ClaudeSettingsRoutes,
            config=aios_yaml,
            variables=variable_catalog,
            resolver=variable_resolver,
            running_auth=providers.Callable(lambda agent: lambda: agent().auth, agent_config),
            sign_in_check=claude_sign_in_check,
        ),
    )
    server = providers.Singleton(
        WebServer,
        auth=auth,
        routes=routes,
        restart=restart,
        port=app_config.provided.web.port,
        audit=audit,
    )
