"""The crypto code connector. ai-os runs it as `server.py` for an MCP session
over stdio, or as `server.py preflight <tool> <arguments>` to ask about a call
before a human is; that prints one JSON line, `{"deny": …}` or `{"ask": …}`."""

import json
import sys

from crypto_connector import CryptoConnector

if __name__ == "__main__":
    connector = CryptoConnector.from_environment()
    if sys.argv[1:2] == ["preflight"]:
        print(json.dumps(connector.preflight(sys.argv[2], json.loads(sys.argv[3]))))
    else:
        connector.server().run()
