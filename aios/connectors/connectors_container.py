from dependency_injector import containers, providers

from aios.connectors.connector_authorizer import ConnectorAuthorizer
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.connectors.connector_status_board import ConnectorStatusBoard
from aios.connectors.connector_token_renewer import ConnectorTokenRenewer
from aios.connectors.oauth_client import OAuthClient


class ConnectorsContainer(containers.DeclarativeContainer):
    """Connectors, what the last turn said about them, and their OAuth sign-in."""

    connectors = providers.Dependency()
    tokens = providers.Dependency()
    expander = providers.Dependency(default=None)
    builtin_tools = providers.Dependency()
    clock = providers.Dependency()

    catalog = providers.Singleton(
        ConnectorCatalog,
        connectors=connectors,
        builtin_tools=builtin_tools,
        tokens=tokens,
        expander=expander,
    )
    board = providers.Singleton(ConnectorStatusBoard, clock=clock)
    authorizer = providers.Singleton(
        ConnectorAuthorizer,
        connectors=catalog,
        tokens=tokens,
        client=providers.Singleton(OAuthClient),
        clock=clock,
    )
    renewer = providers.Singleton(ConnectorTokenRenewer, authorizer=authorizer)
