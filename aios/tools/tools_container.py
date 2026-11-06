from dependency_injector import containers, providers

from aios.agents.agent_catalog import AgentCatalog
from aios.agents.skill_catalog import SkillCatalog
from aios.tools.aios_tool_server import AiosToolServer
from aios.tools.ask_human_tool import AskHumanTool
from aios.tools.collection_access_guard import CollectionAccessGuard
from aios.tools.config_change_approval_rule import ConfigChangeApprovalRule
from aios.tools.config_delete_tool import ConfigDeleteTool
from aios.tools.config_editor import ConfigEditor
from aios.tools.config_get_tool import ConfigGetTool
from aios.tools.config_list_tool import ConfigListTool
from aios.tools.config_put_tool import ConfigPutTool
from aios.tools.data_access_approval_rule import DataAccessApprovalRule
from aios.tools.data_delete_tool import DataDeleteTool
from aios.tools.data_get_tool import DataGetTool
from aios.tools.data_list_collections_tool import DataListCollectionsTool
from aios.tools.data_put_tool import DataPutTool
from aios.tools.data_query_tool import DataQueryTool
from aios.tools.read_logs_tool import ReadLogsTool
from aios.tools.send_message_approval_rule import SendMessageApprovalRule
from aios.tools.send_message_tool import SendMessageTool


class ToolsContainer(containers.DeclarativeContainer):
    """A new tool is one provider here and an entry in `server`; if it needs a
    say in approvals, its rule goes into `approval_rules`."""

    users = providers.Dependency()
    authorizer = providers.Dependency()
    senders = providers.Dependency()
    recorder = providers.Dependency()
    approvals = providers.Dependency()
    registry = providers.Dependency()
    ids = providers.Dependency()
    clock = providers.Dependency()
    log_reader = providers.Dependency()
    agents = providers.Dependency()
    skills = providers.Dependency()
    connectors = providers.Dependency()
    secret_extractor = providers.Dependency(default=None)

    guard = providers.Singleton(CollectionAccessGuard, registry=registry)

    send_message = providers.Singleton(
        SendMessageTool, users=users, senders=senders, recorder=recorder
    )
    ask_human = providers.Singleton(AskHumanTool, approvals=approvals)
    data_list_collections = providers.Singleton(DataListCollectionsTool, guard=guard)
    data_query = providers.Singleton(DataQueryTool, guard=guard)
    data_get = providers.Singleton(DataGetTool, guard=guard)
    data_put = providers.Singleton(DataPutTool, guard=guard, ids=ids)
    data_delete = providers.Singleton(DataDeleteTool, guard=guard)
    # Its own catalogs over the collections: the agents container needs the tool
    # names first, so it cannot hand its catalogs in here.
    config_editor = providers.Singleton(
        ConfigEditor,
        agents=providers.Singleton(AgentCatalog, agents=agents),
        skills=providers.Singleton(SkillCatalog, skills=skills),
        connectors=connectors,
        secrets=secret_extractor,
    )
    config_list = providers.Singleton(ConfigListTool, editor=config_editor)
    config_get = providers.Singleton(ConfigGetTool, editor=config_editor)
    config_put = providers.Singleton(ConfigPutTool, editor=config_editor)
    config_delete = providers.Singleton(ConfigDeleteTool, editor=config_editor)
    read_logs = providers.Singleton(ReadLogsTool, reader=log_reader, clock=clock)

    server = providers.Singleton(
        AiosToolServer,
        tools=providers.List(
            send_message,
            ask_human,
            data_list_collections,
            data_query,
            data_get,
            data_put,
            data_delete,
            config_list,
            config_get,
            config_put,
            config_delete,
            read_logs,
        ),
    )

    approval_rules = providers.List(
        providers.Singleton(SendMessageApprovalRule, users=users, authorizer=authorizer),
        providers.Singleton(DataAccessApprovalRule, registry=registry),
        providers.Singleton(ConfigChangeApprovalRule),
    )
