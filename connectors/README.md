# Code connectors

A code connector is an MCP server written in Python that ships in a folder:
`connector.yaml` (what it is, which variables it needs, its settings and which
of its tools a human approves) and `server.py`. Add one in the console under
Connectors → New → Code.

ai-os starts it in its own process with ai-os's Python, and with **only** what
the manifest declares: its `env` (with `${VAR}` filled in from Variables) and
`AIOS_CONNECTOR_SETTINGS` (JSON), `AIOS_CONNECTOR_STATE` (a folder of its own
under the data dir) and `AIOS_TIMEZONE`. Nothing else from ai-os's environment
reaches it; `aios.connectors.code_connector_launcher` sees to that.

Settings are the manifest's defaults, then what is set on the connector in the
console, then what `aios.yaml` fixes under `connectors.<name>.settings`. A fixed
value is shown and cannot be changed in the console, and no agent can change
`aios.yaml`, which is the place for limits that must hold.

`approval.always` lists tools a human approves every time. For those also under
`approval.preflight`, ai-os first runs `server.py preflight <tool> <arguments>`,
which prints one JSON line: `{"deny": "why"}` refuses the call without asking
anyone, `{"ask": "question"}` is the question put to the human.

The ones here ship with ai-os. More can be put in the configuration repository
under `code/<name>/`; agents cannot write files there.
