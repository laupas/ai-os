from pydantic import BaseModel

from aios.connectors.code_connector_option import CodeConnectorOption


class CodeConnectorOptions(BaseModel):
    """What a code connector answered to `server.py options <list>`; `error` when
    it could not say, and the console then takes any value."""

    options: list[CodeConnectorOption] = []
    error: str = ""
