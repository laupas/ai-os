import re

from aios.connectors.code_connector_library import MANIFEST, CodeConnectorLibrary
from aios.connectors.connector_catalog import ConnectorCatalog
from aios.connectors.connector_variable_names import VARIABLES_KEY, ConnectorVariableNames
from aios.store.store_error import StoreError
from aios.store.store_item import StoreItem
from aios.store.store_kind import StoreKind

NAME = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")


class StoreConnectorCopy:
    """A connector from the Store installed under a name of its own, beside the
    one of its own name, e.g. a second GitHub account. Its variables are its own
    (`GITHUB_WORK_GITHUB_TOKEN`), so each copy has its own key or OAuth client; its
    sign-ins are its own anyway, being kept per connector. What it requires is
    shared, as with any install."""

    @staticmethod
    def of(item: StoreItem, name: str) -> StoreItem:
        if item.kind is not StoreKind.CONNECTOR:
            raise StoreError("only a connector can be installed under another name")
        if not NAME.match(name) or name == ConnectorCatalog.BUILTIN:
            raise StoreError("a name is lower-case letters, digits, - and _")
        declared = {v.variable for v in item.meta.variables}
        if item.code_folder is not None:
            manifest = CodeConnectorLibrary.load(item.code_folder / MANIFEST)
            declared |= {v.variable for v in manifest.variables} if manifest else set()
        names = {v: ConnectorVariableNames.scoped(name, v) for v in sorted(declared)}
        config = ConnectorVariableNames.renamed(dict(item.document.get("config") or {}), names)
        if item.code_folder is not None:
            config[VARIABLES_KEY] = {**ConnectorVariableNames.mapping(config), **names}
        variables = [
            v.model_copy(update={"variable": names[v.variable]}) for v in item.meta.variables
        ]
        return item.model_copy(
            update={
                "id": name,
                "copy_of": item.id,
                "document": {**item.document, "id": name, "config": config},
                "meta": item.meta.model_copy(update={"variables": variables}),
            }
        )
