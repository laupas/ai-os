# hello-world: an example code connector

The smallest complete code connector, as a starting point for your own. It shows
every part ai-os supports:

| file | what it shows |
|---|---|
| `connector.yaml` | the manifest: description, a variable (`HELLO_TOKEN`), settings with defaults, a tool a human approves (`shout`) with a preflight |
| `server.py` | an MCP server over stdio with three tools; reads its settings, its state folder, the timezone and its variable; answers the preflight |
| `agents/hello-greeter.md` | an agent that comes with it, added when the connector is |
| `tests/` | its own tests, run with ai-os's Python |

## Try it

Code connectors belong to an installation, not to ai-os, so ai-os does not load
this folder. Copy it into your configuration repository and commit:

```sh
cp -r examples/code-connectors/hello-world <data>/config/code/
cd <data>/config && git add code/hello-world && git commit -m "Add hello-world"
```

Then, in the console: Connectors → New → Code → `hello-world`, named `hello-world`
(the agent's grants use that name). Ask "say hello to Ada", or "shout hi", which asks
you first, and "shout" something longer than 20 characters, which is refused without
asking. The connector's page asks for the `HELLO_TOKEN` variable, and shows
`max_shout_length` as locked: you can change it there, an agent cannot.

## Write your own

- Copy this folder under a new name: the folder name is the connector's name.
- Keep `server.py` a stdio MCP server; `mcp.server.mcpserver.MCPServer` is there.
- Read settings from `AIOS_CONNECTOR_SETTINGS`, keep files in `AIOS_CONNECTOR_STATE`,
  and declare every value you need under `variables` (or pass it under `env`): you
  get nothing else.
- Mark a setting `x-locked: true` when it is a limit that must hold: agents cannot
  change it, nor add or delete a connector that has one.
- Set `check: true` and answer `server.py check` with `{"ok": …, "detail": …}`:
  the console's Test button. Keep it cheap and free of side effects (read an
  account, never place an order).
- Give the form a shape with `title`, `x-group`, `x-order`, `x-unit` and `x-widget`
  (see the manifest); ai-os only uses them for the console.
- Put a tool that changes something real under `approval.always`, and refuse in
  `preflight` what your own rules refuse, so a human is never asked about it.
- Imports between files of the connector work as plain `import x` (its folder is on
  the path), and nothing is written beside them: ai-os forbids bytecode there.
