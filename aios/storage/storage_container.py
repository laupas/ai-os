from dependency_injector import containers, providers

from aios.audit.audit_policy import AuditPolicy
from aios.audit.audit_trail import AuditTrail
from aios.audit.audited_document_store import AuditedDocumentStore
from aios.config_repo.front_matter_layout import FrontMatterLayout
from aios.config_repo.git_document_store import GitDocumentStore
from aios.config_repo.git_repository import GitRepository
from aios.config_repo.yaml_layout import YamlLayout
from aios.entities.agents.agent import Agent
from aios.entities.approvals.approval import Approval
from aios.entities.connectors.connector import Connector
from aios.entities.connectors.connector_token import ConnectorToken
from aios.entities.conversations.conversation import Conversation
from aios.entities.git.git_remote import GitRemote
from aios.entities.memories.memory import Memory
from aios.entities.schedules.schedule import Schedule
from aios.entities.skills.skill import Skill
from aios.entities.trades.trade import Trade
from aios.entities.users.permission import Permission
from aios.entities.users.role import Role
from aios.entities.users.user import User
from aios.entities.variables.variable import Variable
from aios.storage.agent_access import AgentAccess
from aios.storage.collection import Collection
from aios.storage.collection_access_overrides import CollectionAccessOverrides
from aios.storage.collection_definition import CollectionDefinition
from aios.storage.collection_registry import CollectionRegistry
from aios.storage.json_file_document_store import JsonFileDocumentStore
from aios.storage.jsonl_append_log import JsonlAppendLog


class StorageContainer(containers.DeclarativeContainer):
    """Stores and collections. A new kind of stored data is one definition and one
    collection provider here, plus an entry in `registry`.

    Configuration (agents, skills, connectors, schedules, roles) is kept as files in
    the git repository `config_dir`; everything else as JSON documents in `data_dir`.
    """

    data_dir = providers.Dependency()
    access_overrides = providers.Dependency(default={})
    config_dir = providers.Dependency()
    clock = providers.Dependency()

    document_store = providers.Singleton(JsonFileDocumentStore, root=data_dir)
    append_log = providers.Singleton(JsonlAppendLog, root=data_dir)
    audit_trail = providers.Singleton(AuditTrail, log=append_log, clock=clock)
    # Settings kept in the data dir. Those in the configuration repository need no
    # entry: their git history is the record (`ConfigHistory`).
    settings_store = providers.Singleton(
        AuditedDocumentStore,
        inner=document_store,
        trail=audit_trail,
        policies=providers.Dict(
            users=providers.Object(AuditPolicy(show_values=True)),
            variables=providers.Object(
                AuditPolicy(ignored_fields=frozenset({"updated_at", "updated_by"}))
            ),
            **{
                "git-remotes": providers.Object(
                    AuditPolicy(ignored_fields=frozenset({"updated_at", "updated_by"}))
                ),
                # A renewal changes only the tokens, and every save seals the
                # secrets afresh, so their ciphertext changes without them.
                # Signing in again changes `signed_in_at` and is recorded.
                "connector-tokens": providers.Object(
                    AuditPolicy(
                        ignored_fields=frozenset(
                            {
                                "access_token",
                                "refresh_token",
                                "client_secret",
                                "expires_at",
                                "encrypted",
                            }
                        )
                    )
                ),
            },
        ),
    )
    config_repo = providers.Singleton(GitRepository, root=config_dir)
    config_store = providers.Singleton(
        GitDocumentStore,
        repo=config_repo,
        layouts=providers.Dict(
            agents=providers.Singleton(FrontMatterLayout, "agents/{id}.md", "prompt"),
            skills=providers.Singleton(
                FrontMatterLayout, "skills/{id}/SKILL.md", "content", name_in_head=True
            ),
            connectors=providers.Singleton(YamlLayout, "connectors"),
            roles=providers.Singleton(YamlLayout, "roles"),
            schedules=providers.Singleton(YamlLayout, "schedules"),
        ),
        state=document_store,
        runtime_fields={"schedules": ["last_fired_at"]},
    )
    overrides = providers.Singleton(CollectionAccessOverrides, overrides=access_overrides)

    users_definition = providers.Singleton(
        overrides.provided.apply.call(
            CollectionDefinition(
                name="users",
                entity=User,
                agent_access=AgentAccess.WRITE,
                approver_permission=Permission.MANAGE_USERS,
            )
        )
    )
    roles_definition = providers.Singleton(
        overrides.provided.apply.call(
            CollectionDefinition(
                name="roles",
                entity=Role,
                agent_access=AgentAccess.WRITE,
                approver_permission=Permission.MANAGE_USERS,
            )
        )
    )
    conversations_definition = providers.Singleton(
        overrides.provided.apply.call(
            CollectionDefinition(
                name="conversations", entity=Conversation, agent_access=AgentAccess.READ
            )
        )
    )
    approvals_definition = providers.Singleton(
        overrides.provided.apply.call(
            CollectionDefinition(name="approvals", entity=Approval, agent_access=AgentAccess.READ)
        )
    )

    memories_definition = providers.Singleton(
        overrides.provided.apply.call(
            CollectionDefinition(
                name="memories",
                entity=Memory,
                agent_access=AgentAccess.WRITE,
                agent_writes_need_approval=False,
            )
        )
    )
    schedules_definition = providers.Singleton(
        overrides.provided.apply.call(
            CollectionDefinition(name="schedules", entity=Schedule, agent_access=AgentAccess.WRITE)
        )
    )
    trades_definition = providers.Singleton(
        overrides.provided.apply.call(
            CollectionDefinition(name="trades", entity=Trade, agent_access=AgentAccess.READ)
        )
    )

    # Not through `overrides`: an agent that could write these could grant itself
    # anything, so `collection_access` in config.yaml cannot open them.
    agents_definition = providers.Singleton(
        CollectionDefinition, name="agents", entity=Agent, agent_access=AgentAccess.NONE
    )
    skills_definition = providers.Singleton(
        CollectionDefinition, name="skills", entity=Skill, agent_access=AgentAccess.NONE
    )
    # Secrets: in the data dir, never in the configuration repository.
    connector_tokens_definition = providers.Singleton(
        CollectionDefinition,
        name="connector-tokens",
        entity=ConnectorToken,
        agent_access=AgentAccess.NONE,
    )
    git_remotes_definition = providers.Singleton(
        CollectionDefinition, name="git-remotes", entity=GitRemote, agent_access=AgentAccess.NONE
    )
    variables_definition = providers.Singleton(
        CollectionDefinition, name="variables", entity=Variable, agent_access=AgentAccess.NONE
    )
    connectors_definition = providers.Singleton(
        CollectionDefinition, name="connectors", entity=Connector, agent_access=AgentAccess.NONE
    )

    users = providers.Singleton(Collection, definition=users_definition, store=settings_store)
    memories = providers.Singleton(Collection, definition=memories_definition, store=document_store)
    schedules = providers.Singleton(Collection, definition=schedules_definition, store=config_store)
    trades = providers.Singleton(Collection, definition=trades_definition, store=document_store)
    agents = providers.Singleton(Collection, definition=agents_definition, store=config_store)
    skills = providers.Singleton(Collection, definition=skills_definition, store=config_store)
    connectors = providers.Singleton(
        Collection, definition=connectors_definition, store=config_store
    )
    roles = providers.Singleton(Collection, definition=roles_definition, store=config_store)
    variables = providers.Singleton(
        Collection, definition=variables_definition, store=settings_store
    )
    git_remotes = providers.Singleton(
        Collection, definition=git_remotes_definition, store=settings_store
    )
    connector_tokens = providers.Singleton(
        Collection, definition=connector_tokens_definition, store=settings_store
    )
    conversations = providers.Singleton(
        Collection, definition=conversations_definition, store=document_store
    )
    approvals = providers.Singleton(
        Collection, definition=approvals_definition, store=document_store
    )

    registry = providers.Singleton(
        CollectionRegistry,
        collections=providers.List(
            users,
            roles,
            conversations,
            approvals,
            memories,
            schedules,
            trades,
            agents,
            skills,
            connectors,
            connector_tokens,
            variables,
            git_remotes,
        ),
    )
