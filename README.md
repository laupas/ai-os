# ai-os

A self-hosted personal assistant: chat channels in, Claude agents in the middle,
messages out, with a human in the loop for anything that matters. Configured from a
web console; its whole configuration is a git repository.

```
channel (web, Slack) ──► Gateway ──► Engine (Claude Agent SDK) ──► orchestrator
        ▲     │ progress / approvals               │                 └► agents
        └─────┘                                    ├► skills
                                                   ├► connectors (MCP servers)
                                                   └► ai-os tools (in-process MCP server "aios")
                                                        send_message ─► policy ─► approval ─► Signal / mail
                                                        data_*       ─► policy ─► approval ─► storage
```

- **Channels** are where people talk to ai-os: the web console, Slack, the terminal.
- **Senders** deliver messages elsewhere: Signal, mail (through Resend).
- **Agents** do the work: an orchestrator answers every turn and delegates to the
  others. Each agent may use only the tools, skills and connectors it was granted,
  enforced in code.
- **Connectors** are MCP servers (Google Calendar, Gmail, Homey, anything MCP), set up
  and signed in to from the console.
- **Approvals** are enforced in code: every tool call passes the approval policy
  through the SDK's `can_use_tool`; nothing is pre-allowed.
- **Users and roles** decide who may chat, who may approve, and who can be messaged
  without asking.
- **Scheduler** runs stored prompts on cron times or once.
- **Memories** keep what a user asked to remember. Each belongs to one user, whose
  turns alone see it, or is shared with every user; agents save shared ones only
  with an administrator's approval. Shared preferences and the user's own go into
  the system prompt.

## Quick start (Docker)

You need Docker, and either an Anthropic API key or a Claude Code login.

```sh
git clone https://github.com/laupas/ai-os.git && cd ai-os
cp .env.example .env                       # fill in ANTHROPIC_API_KEY and AIOS_SECRETS_KEY
mkdir -p data && cp aios.example.yaml data/config.yaml   # set the owner's address
docker compose -f docker-compose.example.yml up -d --build
```

Open http://localhost:8080. The example config uses `web.auth.mode: dev`, which
treats every request as the owner: fine on your own machine, **never** on a server
others can reach. Before exposing it, put a login proxy in front (see
[Web console and login](#web-console-and-login)).

To run without Docker:

```sh
uv sync
mkdir -p /tmp/aios && cp aios.example.yaml /tmp/aios/config.yaml
AIOS_DATA_DIR=/tmp/aios uv run python -m aios
```

Then open http://localhost:8080; with `web.auth.mode: dev` every request is the
`dev_email` user, so no login proxy is needed on your own machine. The web console
has to be built once for that (`cd web && npm ci && npm run build`, then
copy `web/dist` to `aios/web/static`); the Docker image does it for you.

**Claude**: ai-os runs Claude through the Claude Agent SDK, so it signs in the way
Claude Code does. `agent.auth` in `aios.yaml` picks how: `api_key` uses
`ANTHROPIC_API_KEY` (recommended for a server), `subscription` (the default) uses
`CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`. Set that one as a secret on the
console's Variables page; the process environment is the fallback, so it can also
come from `.env`. Only the chosen one reaches the CLI, and Health shows which is in
use and where it came from. Check Anthropic's terms for the kind of use you have in
mind.

## Configuration

| Where | What |
|---|---|
| environment | secrets and paths: `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN`, `AIOS_SECRETS_KEY`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `RESEND_API_KEY`, `AIOS_MAIL_FROM`, `SIGNAL_API_URL`, `SIGNAL_SENDER`, `OPENAI_API_KEY` (voice notes), `AIOS_DATA_DIR`, `AIOS_VARIABLE_FILES_DIR` (best a tmpfs), `AIOS_LOG_LEVEL`; see `.env.example` |
| `<data>/config` | the configuration repository (git): `aios.yaml`, agents, skills, connectors, schedules, roles |
| `<data>/users` | who is who, with their accounts on each channel |
| `<data>/variables` | values and secrets for connectors, set in the console; secrets encrypted |
| `<data>/…` | runtime: conversations, approvals, memories, logs |

`aios.yaml` holds channels, senders, the web console and its login, file access,
approval rules, the model and the built-in tools agents may get, and limits. Start
from `aios.example.yaml`: put it at `<data>/config.yaml` before the first start, which
moves it into the configuration repository. Afterwards edit it on the console's
Settings page. It is read at start; a banner offers a restart when it changed.

Default roles (created on the first start): `owner` (everything), `member` (may
chat), `trusted_contact` (may be messaged without approval).

## Web console and login

The console (port 8080) has chat, approvals, schedules, memories, agents, skills,
connectors, variables, logs, health and settings. It is a React app in `web/` (Vite,
Tailwind, shadcn/ui), built by the Dockerfile.

ai-os has no passwords of its own: it trusts a **login proxy** in front of it, and
checks again who is asking, since anything on the same network may reach the port
directly. Pick one in `web.auth`:

| `mode` | For | Checks |
|---|---|---|
| `cloudflare` | Cloudflare Access (Zero Trust) | Access's signed token (`team_domain`, `audience`) |
| `jwt` | oauth2-proxy, Authentik, Pomerium, any proxy forwarding a signed token | signature against `jwks_url`, `issuer`, `audience` |
| `header` | Authelia, Traefik forward-auth, any proxy setting a plain header | only from `trusted_proxies` and/or with a shared secret (`secret_env`) |
| `dev` | your own machine | nothing: every request is `dev_email` |

A person gets in with a `web` account (the address the proxy reports) on a user with
the `chat` permission; the controls need `administer`. Changes need an `X-Aios: 1`
header, which another site cannot send. No change is accepted that would leave
nobody able to administer ai-os.

## Agents and skills

The orchestrator answers every turn and delegates to the enabled agents. Each agent is
a prompt plus what it may use: built-in tools, skills, connectors and which of their
tools. Edit them on the **Agents** page, add your own, switch them off. `orchestrator`,
`ai-os-configurator`, `scheduler`, `memory` and `messenger` are fixed: editable, never
off or deleted. A prompt may contain `{{agents}}`, replaced on every turn by the
enabled agents.

The grants are enforced in code: `AgentGrantRule` refuses any tool, connector or
delegation the calling agent was not granted, before any approval is asked.

A conversation can skip the orchestrator: a new web chat has a **Talk to** picker,
and a schedule an **Agent** field.

Agents that ship with ai-os (a seed: edit or delete them freely):

| Agent | Does | Needs |
|---|---|---|
| `general` | questions, web research | none |
| `messenger` | writes and sends Signal / mail, or drafts | a sender, recipients as users |
| `calendar` | reads and changes Google Calendar | a `gcal` connector |
| `contacts` | looks up people (users, then Google Contacts) | optionally a `gcontacts` connector |
| `inbox-triage` | labels unread Gmail, drafts replies, never sends | a `gmail` connector |
| `homey` | smart home across one or several Homey hubs | a `homey` connector (OAuth) |
| `weather` | weather from wttr.in | none |
| `memory` | remembers and recalls | none |
| `scheduler` | creates and manages schedules and reminders | none |
| `ai-os-configurator` | creates and changes agents, skills, connectors and schedules from a chat; every change is approved by an administrator | none |
| `second-brain` | searches and writes a notes vault mounted at `/vault` | `files.write_roots: [/vault]` |
| `log-checker` | ai-os's own errors and warnings | none |

**Skills** are instructions an agent loads when a task calls for them, edited on the
**Skills** page; which agent may use one is set on the agent. One ships:
`message-style`, the user's voice for messages and mails.

### Code connectors

A **code connector** is an MCP server written in Python that belongs to your
installation rather than to ai-os: a folder under `code/<name>/` in the
configuration repository, holding

- `connector.yaml`: what it is, the variables it needs (`env`, with `${VAR}` filled
  in from Variables), its settings as a JSON schema with defaults (`settings`), and
  which of its tools a human approves (`approval.always`);
- `server.py`: the server, over stdio;
- optionally `agents/*.md`, agents it brings (in the seed format), and `tests/`.

Start from [`examples/code-connectors/hello-world`](examples/code-connectors/hello-world),
a complete small one: copy it to `code/` in your configuration repository. Add one
under Connectors → New → Code; its agents are added with it. ai-os runs it
in a process of its own with ai-os's Python and **only** what the manifest declares,
plus `AIOS_CONNECTOR_SETTINGS` (JSON), `AIOS_CONNECTOR_STATE` (a folder of its own in
the data dir) and `AIOS_TIMEZONE`: nothing else from ai-os's environment reaches it.

Settings are the manifest's defaults, then what is set on the connector in the
console, then what `aios.yaml` fixes under `connectors.<name>.settings`. A fixed
value is shown and cannot be changed in the console, and no agent can change
`aios.yaml`: that is the place for limits that must hold. For a tool under
`approval.preflight` too, ai-os first runs `server.py preflight <tool> <arguments>`,
which prints one JSON line: `{"deny": "why"}` refuses the call without asking anyone,
`{"ask": "question"}` is the question put to the human.

> A code connector is code that ai-os runs. Whoever can commit to the configuration
> repository, or push to its remote, can run code on the machine; agents cannot
> write there.

## Connectors and variables

External MCP servers are **connectors**, managed on the **Connectors** page: add,
edit, switch off, **Start** one to see whether it comes up, and see which agents use
it. A connector does nothing until an agent is granted it.

- A connector with an https address and OAuth (Homey, Google's MCP servers, …) has a
  **Sign in** button: ai-os discovers the server's OAuth endpoints, registers itself,
  and keeps and renews the token. Set `web.public_url` if the console is not reached
  at the host the request names.
- A server that publishes no OAuth endpoints and lets nobody register (Google's
  `gmailmcp`, `calendarmcp` and `people` MCP servers) signs in with a client of your
  own: **Sign in with an own OAuth client** on the connector's URL tab (with a
  *Fill in Google* button), stored as `oauth:` in its config. ai-os takes that key
  out before the config reaches Claude Code:

  ```yaml
  config:
    type: http
    url: https://people.googleapis.com/mcp/v1
    oauth:
      authorization_endpoint: https://accounts.google.com/o/oauth2/v2/auth
      token_endpoint: https://oauth2.googleapis.com/token
      client_id: ${GOOGLE_CLIENT_ID}
      client_secret: ${GOOGLE_CLIENT_SECRET}
      scopes: [https://www.googleapis.com/auth/contacts.readonly]
      params: {access_type: offline, prompt: consent}
  ```

  For Google that is a **Web** OAuth client with the console's
  `/api/oauth/callback` as its redirect URI; `access_type: offline` is what gets a
  refresh token. Gmail and Calendar also need the Cloud project enrolled in the
  Workspace Developer Preview, or every tool call answers that it is not.
- **Whose account** a sign-in is, is set per connector (`sign_in` beside `config`):
  - `shared` (the default): one account for everybody, signed in by an
    administrator. Right for a household device such as Homey.
  - `per_user`: every user who may chat signs in on the Connectors page with their
    own account, and a turn carries only the sign-in of the user it is for; a
    schedule runs as its user. A user who has not signed in does not get the
    connector at all for that turn (the agent is told to ask them to sign in),
    unless `shared_fallback: true` lets them use the shared account.

  ```yaml
  sign_in: per_user
  shared_fallback: false
  config: {type: http, url: https://gmailmcp.googleapis.com/mcp/v1, oauth: {...}}
  ```

  Users who are not administrators see the Connectors page reduced to the
  connectors they can sign in to and their own sign-in; never a configuration or
  anybody else's sign-in. Sign-ins are kept in `<data>/connector-tokens`, one file
  per connector and account (`<connector>.shared`, `<connector>.user.<user id>`),
  their tokens encrypted with `AIOS_SECRETS_KEY`: changing that key means signing
  in again. All of them are renewed in the background.
- **Variables** hold what connectors need: `${NAME}` in a connector's settings for a
  value, `${file:NAME}` for a server that wants the path of a file holding it (a JSON
  key file). Secrets are encrypted with `AIOS_SECRETS_KEY` and never shown again.
  The process environment is the fallback.
  - A `${file:…}` value is a decrypted copy on disk, so point
    `AIOS_VARIABLE_FILES_DIR` at a tmpfs: it then never reaches a disk, and a server
    that rewrites it (a refreshed token) keeps that until the next restart, when the
    stored value is written again. Deleting the variable removes its file.
  - A literal secret is never kept in a connector's config, which is a git
    repository: saving one from the console or through the configurator moves
    `oauth.client_secret`, and every header or environment value whose name says
    key, token, secret, password, credential, auth or cookie, into an encrypted
    variable (`<CONNECTOR>_<KEY>`) and writes `${NAME}` in its place. A commit made
    on the host is not checked; keep `${…}` there yourself.
- `approval.always` and `approval.deny` in `aios.yaml` list connector tools that must
  be asked or are never allowed, whichever agent calls them.
- A Node server built on Google's older client libraries (gaxios 6, node-fetch 2),
  such as `@gongrzhe/server-gmail-autoauth-mcp`, starts fine and then fails every
  token refresh with "Premature close". Give it
  `NODE_OPTIONS: --require /app/node/no-keepalive.cjs` in its `env`.

## The configuration repository

Everything that says how ai-os behaves (`aios.yaml`, agents, skills, connectors,
schedules, roles) is one git repository at `<data>/config`, one file per thing:

| File | What |
|---|---|
| `aios.yaml` | channels, senders, web, approvals, model, limits |
| `agents/<name>.md` | front matter (description, model, enabled, tools, skills, connectors), then the prompt |
| `skills/<name>/SKILL.md` | front matter (name, description), then the instructions |
| `connectors/<name>.yaml` | description, enabled, and the MCP config (`${VAR}` for secrets) |
| `schedules/<id>.yaml` | the schedule; when it last fired is runtime state, outside git |
| `roles/<id>.yaml` | a role's name and permissions |

- Every save in the console is a commit, under the name of whoever saved it. Each
  item has a **History** with diffs and *Restore*.
- Commits made outside ai-os (an editor, a terminal) are picked up within seconds;
  a commit that does not load is ignored and logged.
- **Branches** (Settings → Git): each is a whole version of the configuration. ai-os
  runs the one checked out; switch, compare, merge, delete. A conflicting merge is
  undone and names its files.
- **Remote**: push to a private repository, signed in with an SSH deploy key ai-os
  generates or a fine-grained token, both stored encrypted. With auto-push every
  change goes off-site a few seconds later.
- **Moving to a new machine**: set `AIOS_CONFIG_REMOTE` and `AIOS_CONFIG_SSH_KEY` or
  `AIOS_CONFIG_TOKEN`, start with an empty data dir, and the first start clones the
  configuration before reading it. Not in the repository, by design: users and
  memories (personal), variables and sign-ins (secrets), and runtime state.

On the first start the repository is created from the seed in this repo: `agents/`,
`skills/` and `mcp_servers` in `config.yaml`. Editing the seed afterwards changes
nothing in a running installation.

## Security model

- Every tool call goes through the approval policy; `allowed_tools` stays empty, so
  nothing bypasses it. Unknown tools are denied; built-in tools are opt-in and never
  Bash, since the process environment holds secrets.
- The file tools reach only `files.read_roots` / `files.write_roots`.
- Who may chat, approve or be messaged is decided from users and roles in code, never
  by a prompt. Agents cannot read or change agents, skills, connectors, variables or
  sign-ins.
- Secrets are environment variables or encrypted variables; nothing secret is written
  to the configuration repository.

## Slack app

Socket Mode, bot scopes `chat:write`, `im:history`, `channels:history`,
`groups:history`, `mpim:history` (and optionally `chat:write.customize`, `users:read`);
events `message.im`, `message.channels`, `message.groups`, `message.mpim`;
interactivity on. A Slack user can talk to ai-os once their Slack id is a `slack`
account of a user with the `chat` permission.

## Development

```sh
uv sync
uv run pytest
uv run ruff check aios tests && uv run ruff format aios tests
cd web && npm ci && npm run build   # typecheck and build the console
```

`CLAUDE.md` has the code conventions. To extend:

| To add | Do |
|---|---|
| an agent, skill or connector | in the console (the files in this repo only seed a new install) |
| a tool | a class implementing `AiosTool` in `aios/tools/`, registered in `ToolsContainer`; approval logic as an `ApprovalRule` beside it |
| a channel | a package `aios/channels/<name>/` with a `MessageChannel`, one provider in `ChannelsContainer` |
| a sender | `aios/messaging/<name>/<name>_sender.py` implementing `MessageSender`, one provider in `MessagingContainer` |
| stored data | an entity in `aios/entities/<subject>/`, a collection in `StorageContainer` |

## License

MIT, see [LICENSE](LICENSE).
