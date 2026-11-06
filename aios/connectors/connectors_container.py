from dependency_injector import containers, providers

from aios.connectors.code_connector_approval_rule import CodeConnectorApprovalRule
from aios.connectors.code_connector_library import CodeConnectorLibrary
from aios.connectors.code_connectors import CodeConnectors
from aios.connectors.connector_authorizer import ConnectorAuthorizer
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.connectors.connector_token_migration import ConnectorTokenMigration
from aios.connectors.connector_token_renewer import ConnectorTokenRenewer
from aios.connectors.connector_tokens import ConnectorTokens
from aios.connectors.crypto_connector_migration import CryptoConnectorMigration
from aios.connectors.oauth_client import OAuthClient


class ConnectorsContainer(containers.DeclarativeContainer):
    """Connectors, what the last turn said about them, and their OAuth sign-in."""

    connectors = providers.Dependency()
    tokens = providers.Dependency()
    expander = providers.Dependency(default=None)
    builtin_tools = providers.Dependency()
    clock = providers.Dependency()
    box = providers.Dependency()
    code_roots = providers.Dependency(default=[])
    overrides = providers.Dependency(default={})
    state_root = providers.Dependency()
    timezone = providers.Dependency(default="UTC")

    code = providers.Singleton(
        CodeConnectors,
        library=providers.Singleton(CodeConnectorLibrary, roots=code_roots),
        overrides=overrides,
        state_root=state_root,
        timezone=timezone,
    )

    token_store = providers.Singleton(ConnectorTokens, tokens=tokens, box=box)
    migration = providers.Singleton(ConnectorTokenMigration, tokens=token_store)
    catalog = providers.Singleton(
        ConnectorCatalog,
        connectors=connectors,
        builtin_tools=builtin_tools,
        tokens=token_store,
        expander=expander,
        code=code,
    )
    approval_rule = providers.Singleton(CodeConnectorApprovalRule, catalog=catalog, code=code)
    agents = providers.Dependency()
    crypto_migration = providers.Singleton(
        CryptoConnectorMigration, agents=agents, connectors=connectors
    )
    board = providers.Singleton(ConnectorStatusBoard, clock=clock)
    authorizer = providers.Singleton(
        ConnectorAuthorizer,
        connectors=catalog,
        tokens=token_store,
        client=providers.Singleton(OAuthClient),
        clock=clock,
    )
    renewer = providers.Singleton(ConnectorTokenRenewer, authorizer=authorizer)
