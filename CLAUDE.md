# ai-os: working on this repo

Read `README.md` for what ai-os is. This file is the rules for changing it.

## Code conventions (agreed, not optional)

- **One class per file**, file named after the class (`approval_service.py` holds
  `ApprovalService`). Enums, models, interfaces and exceptions too.
- **SOLID.** Classes take their dependencies through the constructor and depend on
  interfaces. Extending means adding a class plus a registration, not editing a
  working class.
- **Pydantic for every model**, never dataclasses. **`abc.ABC` only for behaviour
  contracts** that have swappable implementations.
- **Persisted models are entities** in `aios/entities/<subject>/`, including the value
  types and enums stored inside them. Transient models (requests, events, results,
  config) live in the domain folder that uses them.
- **Interfaces live in the domain that uses them** (`approvals/approval_presenter.py`).
  There is no global `interfaces/` folder. Platform code lives with its platform
  (`channels/slack/`), one folder per channel or sender type.
- **Dependency injection with `dependency-injector`**: one `DeclarativeContainer` per
  domain (`<domain>_container.py`), composed in `bootstrap/application_container.py`
  in dependency order. Business classes never touch a container.
- **Keep it simple.** Prefer the smallest design that works; no speculative layers.

## Security model (do not weaken by accident)

- `allowed_tools` in `ClaudeOptionsFactory` stays **empty**. Anything listed there
  bypasses `can_use_tool`, and with it the approval policy. The SDK warns
  (`CanUseToolShadowedWarning`) when that happens; treat the warning as a bug.
  `skills="all"` is not used for the same reason.
- `strict_mcp_config=True` stays: otherwise the agent sees MCP connectors of whatever
  account runs it.
- Unknown tools are denied by `KnownToolsRule`; built-in tools are opt-in via
  `agent.builtin_tools`, and never Bash: the process environment holds secrets.
- The file tools reach only `files.read_roots` / `files.write_roots` (`FileAccessRule`
  resolves symlinks and `..`, and refuses a search without a path). Never add `/data`
  or `/app` there.
- Each agent may use only the built-in tools, skills, connectors and connector tools
  it was granted (`AgentGrantRule`, fed by `AgentTracker` from the `SubagentStart`
  hook). A call whose agent cannot be named is denied. Agents are passed with
  `agents=`, never loaded from `.claude/agents`, so nothing slips past the catalog.
- The `agents`, `skills` and `connectors` collections are `AgentAccess.NONE` and deliberately
  not subject to `collection_access`: an agent that could write them could grant
  itself anything.
  The only way in is the `config_*` tools, which `ConfigChangeApprovalRule` keeps to
  the fixed `ai-os-configurator` agent, whatever an agent was granted, and which ask
  an administrator before every save or delete. Never relax either half.
- A granted connector tool is still subject to approvals; its write tools belong in
  `approval.always` or `approval.deny`.
- Trading limits live in `TradeLimits` and are checked again right before every
  order; the approval is extra, not instead.
- Who may chat, approve or be messaged is decided from users and roles in code
  (`Authorizer`), never by a prompt.

- Configuration (agents, skills, connectors, schedules) is the git repository
  `<data>/config` (`GitDocumentStore`). Never put a secret into it: connector configs
  carry `${VAR}`, and git history keeps whatever was committed. Runtime fields
  (`last_fired_at`) stay out of it, or every schedule run is a commit.

## Working in this tree

- If the clone sits in a synced folder (Google Drive, Dropbox, iCloud), keep the venv
  and `node_modules` out of it: `export UV_PROJECT_ENVIRONMENT=~/.venvs/aios`, and
  build the web console from a copy (see `web/README.md`).
- `uv run pytest`, `uv run ruff check aios tests`, `uv run ruff format aios tests`.
- `tests/fakes/world.py` builds the real core over in-memory storage with fakes at
  the edges; most tests start from it.
- An agent turn cannot be unit-tested without Claude. To try the real thing, run the
  CLI channel against a temp data dir (see README).
