# ai-os

A self-hosted personal assistant: chat channels in, Claude agents in the middle,
messages out, with a human in the loop for anything that matters. Configured from a
web console; its whole configuration is a git repository.

```
channel (web, Slack, Teams) ──► Gateway ──► Engine (Claude Agent SDK) ──► orchestrator
        ▲     │ progress / approvals               │                 └► agents
        └─────┘                                    ├► skills
                                                   ├► connectors (MCP servers)
                                                   └► ai-os tools (in-process MCP server "aios")
                                                        send_message ─► policy ─► approval ─► Signal / mail
                                                        send_webhook ─► policy ─► approval ─► webhook destinations
                                                        data_*       ─► policy ─► approval ─► storage
```

- **Channels** are where people talk to ai-os: the web console (typed or spoken),
  Slack and Microsoft Teams. A conversation can live on several at once.
- **Senders** deliver messages to people elsewhere: Signal, mail (through Resend).
- **Webhooks** post to named destinations (an n8n flow, Home Assistant, a chat's
  incoming webhook), each with its own URL, headers and body template.
- **Agents** do the work: an orchestrator answers every turn and delegates to the
  others. Each agent may use only the tools, skills and connectors it was granted,
  enforced in code.
- **Connectors** are MCP servers (Google Calendar, Gmail, Homey, anything MCP), set up
  and signed in to from the console.
- **Approvals** are enforced in code: every tool call passes the approval policy
  through the SDK's `can_use_tool`; nothing is pre-allowed.
- **Users and roles** decide who may chat, who may approve, and who can be messaged
  without asking.
- **Triggers** run stored prompts on cron times, once, or when a program calls
  the trigger's webhook, as a user, opening the conversation wherever that user
  can be reached.
- **Memories** keep what a user asked to remember. Each belongs to one user, whose
  turns alone see it, or is shared with every user; agents save shared ones only
  with an administrator's approval. Shared preferences and the user's own go into
  the system prompt.
- **Voice**: voice notes on Slack and Teams, and the console's Voice page, are
  transcribed (OpenAI) and handled like typed messages.
- **Audit**: every settings change, and every commit to the configuration, in one
  feed; logs and a health page for the running instance.

## Quick start (Docker)

You need Docker, and either an Anthropic API key or a Claude subscription.

```sh
mkdir ai-os && cd ai-os
curl -fsSLo docker-compose.yml https://raw.githubusercontent.com/laupas/ai-os/main/docker-compose.example.yml
docker compose up -d
```

Open http://localhost:8080 and pick "Owner" on the login page: an empty ai-os starts
with that one user, to sign in as and rename. Then set up the rest in the console:

1. **Settings → Claude**: the subscription token or API key (see **Claude** below).
2. **Settings → Users**: your name, and your accounts on Slack, Teams, Signal or mail.
3. Channels as you need them, and agents and connectors (Google, Playwright, GitHub, ...)
   from the **Store** page.

Everything lives in `./data`, next to the compose file.

**Before anyone else can reach it**, change the login. Without one the console uses
`web.auth.mode: pick`: whoever reaches it chooses who they are, which is fine on your
own machine and **never** on a server others can reach. Switch to a password or
chat-code login, or put a login proxy in front, under Settings → Login (see
[Web console and login](#web-console-and-login)). The compose file publishes the
port on loopback only for that reason.

**On a server**, also set `AIOS_SECRETS_KEY` in a `.env` next to the compose file
(the other variables are in [`.env.example`](.env.example)) and uncomment
`env_file: .env`. Without it, the key that encrypts the console's secrets is
generated into `./data`, so a backup of that folder holds them readable. Keep the key
safe: without it, the stored secrets cannot be read.

**On Azure**, ai-os runs as a Web App with its data on an Azure Files share, set up
with one click or by hand: see [docs/azure.md](docs/azure.md).

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Flaupas%2Fai-os%2Fmain%2Fdeploy%2Fazure%2Fazuredeploy.json/createUIDefinitionUri/https%3A%2F%2Fraw.githubusercontent.com%2Flaupas%2Fai-os%2Fmain%2Fdeploy%2Fazure%2FcreateUiDefinition.json)

**To set things up front** instead of in the console (the owner, channels, the
login), copy [`aios.example.yaml`](aios.example.yaml) to `data/config.yaml` before
the first start. Where you cannot put a file there first (a cloud template), the
same YAML in `AIOS_INITIAL_CONFIG` is written there on the first start, and
`AIOS_OWNER_PASSWORD` gives the owner a first password for `web.auth.mode: password`
(only while nobody has one).

To build the image yourself, clone the repository, uncomment `build: .` in the
compose file, and run `docker compose -f docker-compose.example.yml up -d --build`.

To run without Docker:

```sh
uv sync
mkdir -p /tmp/aios && cp aios.example.yaml /tmp/aios/config.yaml
AIOS_DATA_DIR=/tmp/aios uv run python -m aios
```

Then open http://localhost:8080 and pick yourself on the login page (`pick`, the
default); `web.auth.mode: dev` skips even that. The web console
has to be built once for that (`cd web && npm ci && npm run build`, then
copy `web/dist` to `aios/web/static`); the Docker image does it for you.

**Claude**: ai-os runs Claude through the Claude Agent SDK, so it signs in the way
Claude Code does: with a Claude subscription (a token from `claude setup-token`,
`CLAUDE_CODE_OAUTH_TOKEN`, the default) or an Anthropic API key (`ANTHROPIC_API_KEY`,
recommended for a server). Pick one and paste the token or key on the console's
Settings, Claude tab: the choice is `agent.auth` in `aios.yaml` and applies after a
restart, the value is stored as a secret Variable and applies to the next turn. The
process environment is the fallback, so it can also come from `.env`. Only the chosen
one reaches the CLI, and Health shows which is in use and where it came from. Check
Anthropic's terms for the kind of use you have in mind.

### Updating

**ai-os itself**: in the folder with the compose file,

```sh
docker compose pull
docker compose up -d
```

pulls the new image and restarts ai-os with it; conversations in progress are
interrupted, nothing else. Everything in `./data` stays as it is: an update never
changes your agents, skills, connectors, triggers, users or Variables. The agents
that ship with ai-os only seed an empty installation, and a setting that was renamed
is still read under its old name. Before a bigger jump, copy `./data` (with ai-os
stopped), or push the configuration to a remote (Settings → Git) so it is off the
machine anyway.

The image is `ghcr.io/laupas/ai-os` (amd64 and arm64): `:latest` follows `main`, and
each release tag `vX.Y.Z` is also published as `:X.Y.Z` and `:X.Y`. To stay on one
version, set the tag in the compose file (`image: ghcr.io/laupas/ai-os:2.0`) and
change it when you want to move on. A self-built image is updated with `git pull`
in the clone, then `docker compose up -d --build`.

**What you installed from the Store**: open the Store page and press **Refresh**.
An item whose source has a newer version shows **Update**; updating replaces only
that item, never what it brought along or what you made yourself. ai-os does not
update anything on its own.

## Configuration

| Where | What |
|---|---|
| environment | secrets and paths: `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN`, `AIOS_SECRETS_KEY`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `TEAMS_APP_ID`, `TEAMS_APP_PASSWORD`, `TEAMS_TENANT_ID`, `RESEND_API_KEY`, `AIOS_MAIL_FROM`, `SIGNAL_API_URL`, `SIGNAL_SENDER`, `OPENAI_API_KEY` (voice notes), `AIOS_DATA_DIR`, `AIOS_VARIABLE_FILES_DIR` (best a tmpfs), `AIOS_INITIAL_CONFIG` and `AIOS_OWNER_PASSWORD` (first start only), `AIOS_LOG_LEVEL`; see `.env.example` |
| `<data>/config` | the configuration repository (git): `aios.yaml`, agents, skills, connectors, triggers, roles, webhooks |
| `<data>/users` | who is who, with their accounts on each channel |
| `<data>/variables` | values and secrets for connectors, set in the console; secrets encrypted |
| `<data>/…` | runtime: conversations, approvals, memories, logs |

`aios.yaml` holds:

| Key | What |
|---|---|
| `channels` | which channels are on: `web`, `slack`, `teams`, `signal`, `mail`, `webhook` (their tokens are Variables) |
| `timezone` | for triggers and dates in prompts (`Europe/Zurich`) |
| `owner` | the first user, created once when there is none |
| `web` | port, `auth` (the login, see below), `public_url` for OAuth redirects |
| `agent` | `model`, `auth` (subscription or API key), `builtin_tools` agents may be given, `turn_timeout_seconds` |
| `approval` | `always` and `deny` (tool names), `timeout_seconds` after which an unanswered approval is No |
| `files` | `read_roots` and `write_roots` for the built-in file tools |
| `triggers` | `enabled` (off: no trigger runs, on time or by webhook), `tick_seconds`; until 2026-11-23 `scheduler`, still read |
| `collection_access` | per stored collection, what agents may do with it (`none`, `read`, `write`) |

Every section can be edited on the console's Settings page. Start
from `aios.example.yaml`: put it at `<data>/config.yaml` before the first start, which
moves it into the configuration repository. Afterwards edit it on the console's
Settings page. It is read at start; a banner offers a restart when it changed.

Users have accounts (one per channel: a Slack id, an Entra object id, a phone
number, a mail address, a web address) and roles. A role is a set of permissions:

| Permission | Allows |
|---|---|
| `chat` | talking to ai-os on a channel |
| `approve` | answering approval requests |
| `receive_unapproved` | being sent a message without an approval first |
| `manage_users` | approving an agent's changes to users and roles |
| `administer` | the console's controls: settings, agents, connectors, logs, every conversation, restart |

Default roles (created on the first start): `owner` (everything), `member` (may
chat), `trusted_contact` (may be messaged without approval). Edit them, or add
your own, under Settings → Roles. On every start the owners get a "started and
ready" message on a channel that can reach them.

## Web console and login

The console (port 8080) is a React app in `web/` (Vite, Tailwind, shadcn/ui), built
by the Dockerfile. What each person sees depends on their permissions:

| Page | What |
|---|---|
| Chat | conversations with ai-os, picking the agent to talk to; every conversation for administrators |
| Voice | hands-free talking: speech is transcribed, the reply read aloud, "stop" cuts it off |
| Approvals | open approval requests, answered here or on Slack and Teams |
| Triggers | create, edit, switch off, run now; turn on a trigger's webhook and renew its token |
| Memories | what ai-os remembers, per user or shared |
| Agents, Skills | prompts, models and grants; instructions |
| Connectors | MCP servers and code connectors, starting and signing in; users who are not administrators see only their own sign-ins |
| Variables | values and secrets for connectors, channels and webhooks |
| Audit | who changed what when, settings and configuration commits together |
| Logs, Health | the instance's log, and what is running (channels, connectors, Claude sign-in) |
| Settings | Claude, Channels (with Webhooks), General, Agents, Approvals, Login, Files, Data access, Users, Roles, Repository (the configuration files, editable), Branches, aios.yaml |

The console either signs people in itself, or trusts a **login proxy** in front of
it and checks again who is asking, since anything on the same network may reach the
port directly. Pick one in `web.auth` (or under Settings → Login):

| `mode` | For | Checks |
|---|---|---|
| `pick` (default) | a fresh install, or a home network where everyone is trusted | nothing: the login page lists the users and you pick one |
| `password` | a small installation without a proxy (behind https) | a name (web address, name or alias) and a password set per user under Settings → Users |
| `code` | the same, without passwords | a one-time code ai-os sends to the user's Slack, Teams, Signal or mail account |
| `sso` | Microsoft 365, Google, or any OpenID Connect provider, without a proxy | the provider's signed ID token, fetched by ai-os itself (see below) |
| `cloudflare` | Cloudflare Access (Zero Trust) | Access's signed token (`team_domain`, `audience`) |
| `jwt` | oauth2-proxy, Authentik, Pomerium, any proxy forwarding a signed token | signature against `jwks_url`, `issuer`, `audience` |
| `header` | Authelia, Traefik forward-auth, any proxy setting a plain header | only from `trusted_proxies` and/or with a shared secret (`secret_env`) |
| `dev` | your own machine | nothing: every request is `dev_email` |

`pick`, `password`, `code` and `sso` keep a browser signed in with a signed cookie for
`session_days` (30). Passwords are hashed (scrypt) in `<data>/web-passwords`, never
in git; a new password signs that user out everywhere, and five wrong attempts for
one name block it for 15 minutes. Settings refuse to switch to `password` before the
administrator saving it has a password, and to `code` before ai-os can reach them.
A code is valid for 10 minutes, works once, and a new one is sent at most once a
minute; the login page answers the same whether or not a name is known.

A person gets in with a `web` account (the address the proxy reports) on a user with
the `chat` permission; the controls need `administer`. Changes need an `X-Aios: 1`
header, which another site cannot send. No change is accepted that would leave
nobody able to administer ai-os.

### API docs

Switch on **API docs** under Settings → General (or `api_docs: {enabled: true}` in
`aios.yaml`; applies at once) and administrators get a Swagger page at `/api/docs`
and the OpenAPI 3.1 description at `/api/openapi.json`. Both are generated from the
running server: every route, grouped by console page, with its request body and the
permission it needs, so they never fall behind the code. *Try it out* uses the
browser's own sign-in. Off, both answer 404.

### Single sign-on

With `sso`, the login page shows a button per provider in `providers`, and ai-os
runs the OpenID Connect sign-in itself (authorization code with PKCE, a nonce, and
the ID token's signature, issuer and audience checked). Whoever signs in is the
user whose `web` account is the address the provider vouches for; names and
aliases do not count.

```yaml
web:
  public_url: https://ai-os.example.com
  auth:
    mode: sso
    providers:
      - kind: microsoft
        tenant: example.com              # tenant id or domain, or consumers
        client_id: 00000000-0000-0000-0000-000000000000
        client_secret_variable: AIOS_SSO_MICROSOFT_SECRET
      - kind: google
        client_id: 1234-abcd.apps.googleusercontent.com
        client_secret_variable: AIOS_SSO_GOOGLE_SECRET
        domains: [example.com]
      - kind: oidc
        issuer: https://auth.example.com/application/o/ai-os/
        client_id: ai-os
        client_secret_variable: AIOS_SSO_SECRET
```

1. Register an application with the provider, with
   `<public_url>/api/login/sso/callback` as redirect address:
   - **Microsoft 365**: Entra ID → App registrations → New registration, platform
     *Web*; then Certificates & secrets → New client secret. `tenant` is the
     directory (tenant) id or a domain of it, or `consumers` for personal Microsoft
     accounts. `common` and `organizations` are refused: they let in accounts of
     any organisation, whose addresses nobody you trust has checked. Without an
     `email` claim, the sign-in name (`preferred_username`) is the address.
   - **Google**: Google Cloud → APIs & Services → Credentials → OAuth client id,
     type *Web application*. Only addresses Google has verified count; one entry
     in `domains` also limits Google's account picker to that Workspace domain.
   - **OpenID Connect** (Authentik, Keycloak, Okta, Auth0, Zitadel, …): `issuer` is
     the address under which `/.well-known/openid-configuration` is found. A
     provider without a secret (public client) leaves out `client_secret_variable`.
2. Set the client secret as a Variable (Settings → Variables) under the name in
   `client_secret_variable`; it is never written into `aios.yaml`.
3. Give everyone who should get in a `web` account with the address they sign in
   with (Settings → People), then switch under Settings → Login. Saving is refused
   while the secret is unset or the provider cannot be reached.

`domains` keeps out every address outside them; `label` changes the button's
text, and `id` tells two providers of one kind apart. `scopes` (default `openid
email profile`) and `email_claim` (default `email`) are there for unusual
providers. If a wrong setting locks you out, change `web.auth` in `aios.yaml` on
the host and restart.

## Conversations

- A conversation is the unit, not a channel: replies and progress go to every place
  it lives, and a user's message is mirrored to the others (on Slack and Teams as
  written by them, where the app may).
- While a turn runs, its progress shows ("Looking at the calendar", "Waiting for
  your answer"), with a **Stop** button on Slack, Teams and the web.
- Approvals arrive as buttons on Slack and Teams, in the console, or as a yes/no
  question where a channel has no buttons. A turn waits for the answer; an
  unanswered one is No after `approval.timeout_seconds`.
- On Teams, a personal or group chat is one conversation until `/new`; in a team,
  each post that mentions the bot is a thread. Quoting an earlier message goes back
  to its conversation.
- Agents can search the user's earlier conversations (`conversation_search`).

### ai-os tools

What ai-os offers its agents, besides connectors. Each must be granted to an agent
(connector `aios`), and passes the approval policy like any tool.

| Tool | Does | Approval |
|---|---|---|
| `send_message` | sends a Signal or mail message to a known user | asked, unless the recipient has `receive_unapproved` |
| `send_webhook` | posts to a webhook destination | per destination: ask, allow or deny |
| `ask_human` | asks the user to choose between options and waits | none |
| `data_list_collections`, `data_query`, `data_get` | read stored data (users, triggers, memories, …) | as `collection_access` allows |
| `data_put`, `data_delete` | change stored data | asked, except a user's own memories; refused where a collection is read-only |
| `config_list`, `config_get`, `config_put`, `config_delete` | read and change agents, skills and connectors | only the `ai-os-configurator`, and every change is asked of an administrator |
| `conversation_search` | the user's own earlier conversations | none |
| `read_logs` | ai-os's own log lines | none |

## Agents and skills

The orchestrator answers every turn and delegates to the enabled agents. Each agent is
a prompt plus what it may use: built-in tools, skills, connectors and which of their
tools. Edit them on the **Agents** page, add your own, switch them off. `orchestrator`,
`ai-os-configurator`, `triggers`, `memory` and `messenger` are fixed: editable, never
off or deleted. A prompt may contain `{{agents}}`, replaced on every turn by the
enabled agents.

The grants are enforced in code: `AgentGrantRule` refuses any tool, connector or
delegation the calling agent was not granted, before any approval is asked.

A conversation can skip the orchestrator: a new web chat has a **Talk to** picker,
and a trigger an **Agent** field.

A new installation starts with the core agents (a seed: edit them freely; the
fixed ones cannot be switched off or deleted). Everything else comes from the
[Store](#store).

| Agent | Does |
|---|---|
| `orchestrator` | answers every turn and hands work to the others (fixed) |
| `ai-os-configurator` | creates and changes agents, skills, connectors and triggers from a chat; every change is approved by an administrator (fixed) |
| `triggers` | creates and manages triggers and reminders (fixed) |
| `memory` | remembers and recalls (fixed) |
| `messenger` | writes and sends Signal / mail, or drafts (fixed; needs a sender, recipients as users) |
| `general` | questions, web research |
| `log-checker` | ai-os's own errors and warnings |

**Skills** are instructions an agent loads when a task calls for them, edited on the
**Skills** page; which agent may use one is set on the agent. One ships:
`message-style`, the user's voice for messages and mails.

### Store

The **Store** page installs agents, skills, connectors and triggers from git
repositories laid out like the configuration repository. The default source is
[laupas/ai-os-templates](https://github.com/laupas/ai-os-templates): Google
Calendar, Gmail, Drive and Contacts (Google's own MCP servers), Playwright, GitHub,
Homey, and agents and triggers that use them. Add your own sources on the same page;
they are `store.sources` in `aios.yaml`:

```yaml
store:
  sources:
    - url: https://github.com/laupas/ai-os-templates
    - url: https://github.com/you/your-templates
      branch: main
```

Each item is installed on its own, in one commit, together with what it needs and
the installation does not have yet: an agent's connectors and skills, a trigger's
agent. What is there already is kept, never overwritten; the item itself is
replaced only on **Reinstall**. The install asks for the values the item names
(an OAuth client, a token) and saves them as Variables, and a connector's config
goes through the same secret check as a save on the Connectors page. A trigger is
added for whoever installs it. A code connector is copied into `code/` only after
you confirm you trust the source: it is a program that runs on this server.

**Versions and updates**: ai-os records which source and version each item came
from, in `.aios-store.yaml` in the configuration repository. When a source offers a
higher version, the item shows **Update**, which replaces only the item itself.

**Uninstall** removes one item and its record in one commit, and for a code
connector its folder under `code/`. What it brought along, its Variables and its
sign-ins stay, since other items may use them; the page names what still refers to
it before you confirm. The fixed core agents cannot be removed, and a trigger is
deleted on the Triggers page.

#### Making a store source

A store source is any git repository ai-os can clone over `https://` (or `file://`
for a local test) without a password: a public repository. Its layout is that of the
configuration repository, with a `store.yaml` on top:

```
store.yaml                 name and description of the source
agents/<id>.md             one agent per file
skills/<id>/SKILL.md       one skill per folder
connectors/<id>.yaml       one connector per file
triggers/<id>.yaml         one trigger per file
code/<name>/               a code connector's folder (connector.yaml, server.py, agents/)
```

Every folder is optional; the file name is the item's id.

```yaml
# store.yaml
name: My templates
description: Connectors and agents for our team.
```

Each item is written exactly as ai-os writes it into the configuration repository,
so the easiest start is to build it in the console and copy the file from
`data/config/`. The rules:

- **Agent** (`agents/<id>.md`): YAML front matter with `description`, `model`,
  `enabled`, `builtin_tools`, `skills` and `connectors` (a connector id mapped to
  the list of its tools granted, or `null` for all of them), then the prompt.
- **Skill** (`skills/<id>/SKILL.md`): front matter with `name` and `description`,
  then the instructions.
- **Connector** (`connectors/<id>.yaml`): `description`, `config` (one server in
  the shape of Claude Code's `.mcp.json`), `enabled`, `sign_in` (`shared` or
  `per_user`), `shared_fallback`. Never put a secret here: write `${VAR}` and list
  the variable under `store.variables`, so it is asked for on install and saved as a
  Variable. A config with a token in it is moved to a Variable on install anyway.
- **Code connector**: a connector whose `config` is `{code: <name>}`, with its
  folder at `code/<name>/` (see [Code connectors](#code-connectors)).
- **Trigger** (`triggers/<id>.yaml`): `name`, `prompt`, `cron` (a list) or
  `once_at`, `timezone`, `agent` (`null` for the orchestrator), `enabled`,
  `max_lateness_minutes`. No `user_id`: it is added for whoever installs it.

Each item may carry a `store:` block, a top-level key of a YAML file or in the front
matter of an agent or skill. It is shown on the Store page and never written into
the configuration repository:

```yaml
store:
  title: GitHub (read-only)        # shown name; default: the id
  category: Developer              # groups items on the Store page
  version: "1.0.0"                 # raise it on every change
  author: Your name
  license: MIT
  homepage: https://github.com/github/github-mcp-server
  tags: [github, developer]
  notes: |                         # Markdown shown before installing
    Create a fine-grained personal access token with read-only access ...
  variables:                       # asked for on install, saved as Variables
    - variable: GITHUB_MCP_TOKEN
      label: GitHub token
      hint: A fine-grained personal access token.
      secret: true                 # stored encrypted, never shown again
      required: true
  requires: [skills/message-style] # further items installed with it
```

`requires` only needs what is not implied already: an agent's `connectors` and
`skills` and a trigger's `agent` are installed with it when they are in the same
source (the built-in `aios` connector excepted). Quote the version so YAML keeps it
as text; versions compare number by number, so `1.10.0` is newer than `1.9.0`, and
an installation offers **Update** once yours is higher than the one it has.

An item that does not read (bad YAML, an unknown field, a code connector without
its folder) is left out, and the Store page names the file and the reason under the
source. [laupas/ai-os-templates](https://github.com/laupas/ai-os-templates) is a
complete example of every kind.

### Code connectors

A **code connector** is an MCP server written in Python that belongs to your
installation rather than to ai-os: a folder under `code/<name>/` in the
configuration repository, holding

- `connector.yaml`: what it is, the values it needs (`variables`, asked for on the
  connector and stored as Variables; `env` passes more, with `${VAR}` filled in), its
  settings as a JSON schema with defaults (`settings`), and which of its tools a
  human approves (`approval.always`);
- `server.py`: the server, over stdio;
- optionally `agents/*.md`, agents it brings (in the seed format), and `tests/`.

Start from [`examples/code-connectors/hello-world`](examples/code-connectors/hello-world),
a complete small one: copy it to `code/` in your configuration repository. Add one
under Connectors → New → Code; its agents are added with it. ai-os runs it
in a process of its own with ai-os's Python and **only** what the manifest declares,
plus `AIOS_CONNECTOR_SETTINGS` (JSON), `AIOS_CONNECTOR_STATE` (a folder of its own in
the data dir) and `AIOS_TIMEZONE`: nothing else from ai-os's environment reaches it.

Settings are the manifest's defaults, then what is set on the connector in the
console. A setting with `x-locked: true` in the schema is out of reach of agents:
the `config_*` tools refuse to change it, or to add, delete or repoint a connector
that has one, even with an administrator's approval. That is the place for limits
that must hold. (`aios.yaml` used to fix them under `connectors:`; such values are
moved onto the connector at the next start.) For a tool under
`approval.preflight` too, ai-os first runs `server.py preflight <tool> <arguments>`,
which prints one JSON line: `{"deny": "why"}` refuses the call without asking anyone,
`{"ask": "question"}` is the question put to the human. With `check: true` in the
manifest, the connector's page has a Test button: ai-os runs `server.py check` with
the settings and variables shown there, saved or not, and shows the one JSON line it
prints, `{"ok": true|false, "detail": "..."}`.

The console draws the settings form from the schema. Beyond the JSON Schema basics
(`type`, `default`, `description`, `enum`, `minimum`, `maximum`, and `title` as the
label), it reads `x-group` (a heading the field is shown under), `x-order` (lower
first, else the schema's order), `x-unit` (shown after the input) and `x-widget`
(`textarea` for a long string, `slider` for a number with `minimum` and `maximum`).
The server sees none of this; it is only layout. `x-options: <list>` on a value
offers choices the server gives: the console asks, ai-os runs `server.py options
<list>` with the settings and variables shown, and the server prints
`{"options": [...]}`, each a value or `{"value": ..., "label": ...}`. Any other value
can still be typed, so a list that cannot be fetched costs nothing.

> A code connector is code that ai-os runs. Whoever can commit to the configuration
> repository, or push to its remote, can run code on the machine; agents cannot
> write there.

## Webhooks

The `webhook` channel lets agents post to named **destinations**, set up under
Settings → Channels → Webhooks. Each is one file, `webhooks/<name>.yaml`, in the
configuration repository, and applies to the next turn without a restart:

```yaml
description: Posts an alert into the family channel.  # agents read this to pick it
method: POST                                           # POST, PUT, PATCH or GET
url: https://n8n.example.com/webhook/${N8N_ALERTS_ID}
headers:
  Authorization: Bearer ${N8N_TOKEN}
fields:                                                # JSON schema of what the agent gives
  type: object
  properties:
    text: {type: string, description: The alert}
    level: {type: integer, minimum: 1, maximum: 3}
  required: [text]
body:                                                  # a mapping or list is sent as JSON
  message: "Alert: {{text}}"
  level: "{{level}}"                                   # exactly one field: keeps its type
approval: ask                                          # ask, allow or deny
enabled: true
```

- `{{field}}` is a value the agent gives; every field a template uses must be
  declared in `fields`, and the agent's values are checked against that schema
  before anyone is asked to approve.
- `${NAME}` is a Variable. Both are filled in one pass, so a field holding
  `${SECRET}` stays literal text: an agent cannot pull a secret into a request.
- In the URL a field is percent-encoded; in a header it loses its line breaks. A
  body that is a string is sent as written (a form, plain text); set `Content-Type`
  under `headers`. A GET sends no body.
- A literal secret in a header whose name says so is moved into a Variable on
  save, as for connectors. A token in the URL belongs in a `${NAME}` too.
- **Send test** in the editor really calls the destination, as typed, saved or not.
- Switch the channel on (restart), then grant `send_webhook` to the agents that may
  post. A post and its fields are recorded in the conversation.

## Triggers

A trigger is a prompt ai-os runs by itself for one user: on cron times (**Repeat**),
once (**Once**), or when a program calls its webhook. Each run is a new conversation
for that user, opened wherever they can be reached, and runs with their permissions.
Manage them on the Triggers page, or ask the `triggers` agent ("remind me tomorrow
at 9 to …"). Until 2026-11-23 they were called schedules: the first start after the
update moves `schedules/` to `triggers/` and the `scheduler` agent to `triggers` in
one commit, `/hooks/schedules/<id>` keeps working, and an agent prompt that still
names the `schedules` collection finds the triggers.

### Starting a trigger by webhook

A trigger can also be started by a program (n8n, a CI job, Home Assistant): turn on
**Can also be started by a webhook** in its editor, or pick **Webhook only** for a
trigger with no time at all. The console then shows its URL and token, once:

```sh
curl -X POST https://ai-os.example.com/hooks/triggers/<id> \
  -H "Authorization: Bearer aios_..." \
  -H "Content-Type: application/json" \
  -d '{"service": "web", "status": "failed"}'
```

- The answer is `202` and the run starts like any other: a new conversation for the
  trigger's user. Whatever the call sent (JSON, pretty-printed, or plain text, up
  to 20,000 characters) is added below the prompt, fenced and marked as data the
  agent must not take orders from. Its tools are still approved as usual.
- A wrong token, an unknown trigger and one without a webhook all answer `404`. A
  switched-off trigger answers `409`, switched-off `triggers` `503`, and a second
  call within 10 seconds `429`.
- Only the token's SHA-256 is stored in the trigger's file. **New token** makes a
  new one and retires the old; turning the webhook off drops it.
- `/hooks/` is the only path the console's sign-in lets through, since the token is
  the proof. Behind Cloudflare Access (or another login proxy) give `/hooks/*` a
  bypass or service-token rule, or call ai-os from inside its network
  (`http://ai-os:8080/hooks/...`).

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
    trigger runs as its user. A user who has not signed in does not get the
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
triggers, roles, webhooks, code connectors) is one git repository at `<data>/config`, one file per thing:

| File | What |
|---|---|
| `aios.yaml` | channels, senders, web, approvals, model, limits |
| `agents/<name>.md` | front matter (description, model, enabled, tools, skills, connectors), then the prompt |
| `skills/<name>/SKILL.md` | front matter (name, description), then the instructions |
| `connectors/<name>.yaml` | description, enabled, and the MCP config (`${VAR}` for secrets) |
| `triggers/<id>.yaml` | the trigger; when it last fired is runtime state, outside git |
| `roles/<id>.yaml` | a role's name and permissions |
| `webhooks/<name>.yaml` | a webhook destination (`${VAR}` for secrets) |
| `code/<name>/` | a code connector: `connector.yaml`, `server.py`, its agents |

- Every save in the console is a commit, under the name of whoever saved it. Each
  item has a **History** with diffs and *Restore*. Settings → Repository browses
  and edits the files themselves, on any branch.
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
  by a prompt. Agents cannot read or change agents, skills, connectors, webhook
  destinations, variables or sign-ins; only the configurator changes the first
  three, and only with an administrator's yes.
- Each agent may use only what it was granted (`AgentGrantRule`), checked before
  any approval is asked.
- Secrets are environment variables or encrypted variables; nothing secret is written
  to the configuration repository. A trigger's webhook keeps only its token's hash.
- `/hooks/` is the only way in without the console's sign-in; each call there needs
  the trigger's own token, and what it sends reaches the agent as marked data.

## Slack app

Socket Mode, bot scopes `chat:write`, `im:history`, `channels:history`,
`groups:history`, `mpim:history` (and optionally `chat:write.customize`, `users:read`);
events `message.im`, `message.channels`, `message.groups`, `message.mpim`;
interactivity on. A Slack user can talk to ai-os once their Slack id is a `slack`
account of a user with the `chat` permission.

## Teams app

The `teams` channel uses the Teams SDK's **Socket Mode** (a Microsoft preview): ai-os
dials out to Teams, like Slack's Socket Mode, so no public address is needed. Only
outbound HTTPS to `login.microsoftonline.com`, `*.botapi.skype.com` and
`*.service.signalr.net`. Everything is set up on the web, in the
[Teams Developer Portal](https://dev.teams.microsoft.com):

1. **Tools → Bot management → New bot.** Copy its id, and add a client secret.
2. **Configure → Delivery method → Socket mode → Save.** Only new bots can use it.
3. **Apps → New app → App features → Bot:** pick the bot, scopes personal, team and
   group chat; then **Preview in Teams** (or publish it to your organisation).
4. In the ai-os console, **Settings → Channels → Microsoft Teams:** the bot id, the
   secret and your tenant id; **Check** confirms the bot signs in and has a socket.
   Turn the channel on and restart.

A Teams user can talk to ai-os once their Microsoft Entra object id is a `teams`
account of a user with the `chat` permission. In a team, mention the bot to start a
thread; a personal or group chat is one conversation until someone writes `/new`.
Trigger runs reach a user in their personal chat with the bot.

## Signal and mail

Both only send: agents message people, nobody chats with ai-os there. The console's
Settings → Channels has the setup steps and a **Test** for each.

- **Signal** goes through [signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api)
  running next to ai-os, with a number linked or registered there: its address
  (`SIGNAL_API_URL`) and the number (`SIGNAL_SENDER`).
- **Mail** goes through [Resend](https://resend.com), from a domain verified there:
  an API key (`RESEND_API_KEY`) and a From address (`AIOS_MAIL_FROM`).

A person is reached once their number or address is a `signal` or `mail` account
on their user.

## Development

```sh
uv sync
uv run pytest
uv run ruff check aios tests && uv run ruff format aios tests
cd web && npm ci && npm run build   # typecheck and build the console
```

GitHub Actions (`.github/workflows/docker.yml`) runs ruff and the tests on every push
and pull request. From `main` and from `v*` tags it then builds the image for amd64
and arm64 and pushes it to `ghcr.io/<owner>/ai-os`. A release is a tag:
`git tag v2.1.0 && git push origin v2.1.0`.

`CLAUDE.md` has the code conventions. To extend:

| To add | Do |
|---|---|
| an agent, skill or connector | in the console (the files in this repo only seed a new install) |
| a tool | a class implementing `AiosTool` in `aios/tools/`, registered in `ToolsContainer`; approval logic as an `ApprovalRule` beside it |
| a chat channel | a package `aios/channels/<name>/` with a `ChannelType` and its `MessageChannel`, one entry in `ChannelsContainer.types` |
| a sender | a package `aios/messaging/<name>/` with a `ChannelType` and its `MessageSender`, one entry in `ChannelsContainer.types` |
| stored data | an entity in `aios/entities/<subject>/`, a collection in `StorageContainer` |

## License

MIT, see [LICENSE](LICENSE).
