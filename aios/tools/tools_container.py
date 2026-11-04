from dependency_injector import containers, providers

from aios.tools.aios_tool_server import AiosToolServer
from aios.tools.ask_human_tool import AskHumanTool
from aios.tools.collection_access_guard import CollectionAccessGuard
from aios.tools.crypto_balance_tool import CryptoBalanceTool
from aios.tools.crypto_quote_tool import CryptoQuoteTool
from aios.tools.crypto_signal_tool import CryptoSignalTool
from aios.tools.crypto_trade_approval_rule import CryptoTradeApprovalRule
from aios.tools.crypto_trade_tool import CryptoTradeTool
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
    crypto_signals = providers.Dependency()
    trader = providers.Dependency()
    trade_guard = providers.Dependency()
    log_reader = providers.Dependency()

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
    crypto_signal = providers.Singleton(CryptoSignalTool, signals=crypto_signals)
    crypto_quote = providers.Singleton(CryptoQuoteTool, trader=trader)
    crypto_trade = providers.Singleton(CryptoTradeTool, trader=trader)
    crypto_balance = providers.Singleton(CryptoBalanceTool, trader=trader)
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
            crypto_signal,
            crypto_quote,
            crypto_trade,
            crypto_balance,
            read_logs,
        ),
    )

    approval_rules = providers.List(
        providers.Singleton(SendMessageApprovalRule, users=users, authorizer=authorizer),
        providers.Singleton(DataAccessApprovalRule, registry=registry),
        providers.Singleton(CryptoTradeApprovalRule, guard=trade_guard),
    )
