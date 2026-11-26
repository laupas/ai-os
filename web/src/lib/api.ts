// The ai-os JSON API. Every change carries X-Aios, which a page on another site
// cannot add without CORS (and ai-os answers no CORS).

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export async function api<T = unknown>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "X-Aios": "1" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError((await response.text()) || response.statusText, response.status);
  }
  return (await response.json()) as T;
}

export type Permission =
  | "chat"
  | "voice"
  | "approve"
  | "receive_unapproved"
  | "manage_agents"
  | "manage_skills"
  | "manage_connectors"
  | "manage_variables"
  | "manage_triggers"
  | "manage_shared_memories"
  | "view_logs"
  | "manage_users"
  | "administer";

/** Rights whose holder controls ai-os: a group with one is never filled automatically
 * (new users, a sign-in provider's groups). The server's `Permission.powerful`. */
export const POWERFUL: Permission[] = ["administer", "manage_users", "manage_connectors"];

export function isPowerful(permissions: Permission[]): boolean {
  return permissions.some((p) => POWERFUL.includes(p));
}

export interface Me {
  name: string;
  email: string;
  permissions: Permission[];
  chat: boolean;
}

export interface ConversationSummary {
  id: string;
  title: string | null;
  channels: string[];
  participants: string[];
  status: string;
  /** The agent answering here instead of the orchestrator, if one was chosen. */
  agent: string | null;
  updated_at: string;
  writable: boolean;
  preview: string;
  messages: number;
  last_at: string | null;
}

export type Role = "user" | "assistant" | "tool" | "activity";

export interface Message {
  id: string;
  role: Role;
  author?: string | null;
  author_user_id?: string | null;
  channel: string;
  text: string;
  created_at: string;
}

export interface Conversation extends Omit<ConversationSummary, "preview" | "messages" | "last_at"> {
  messages: Message[];
  /** Approvals still waiting for an answer in this conversation. */
  approvals: { id: string; question: string; options: string[]; voice_answerable: boolean }[];
}

export interface ConversationEvent {
  conversation_id: string;
  kind: "message" | "progress" | "delta" | "done" | "approval";
  text: string;
  restart: boolean;
  message: Message | null;
  approval_id: string | null;
  options: string[];
  /** A question an agent asked, which may be answered by speaking. */
  voice_answerable: boolean;
}

export interface Approval {
  id: string;
  conversation_id: string;
  channel: string;
  question: string;
  options: string[];
  created_at: string;
}

export interface Trigger {
  id: string;
  name: string;
  prompt: string;
  cron: string[];
  once_at: string | null;
  timezone: string;
  user_id: string;
  /** The agent each run goes to straight away; null asks the orchestrator. */
  agent: string | null;
  enabled: boolean;
  max_lateness_minutes: number;
  /** A POST to `/hooks/triggers/<id>` with its token also starts a run. */
  webhook: boolean;
  last_fired_at: string | null;
  next_run: string | null;
}

/** Someone a new conversation can be started with (`/api/chat/agents`). */
export interface ChatAgent {
  name: string;
  description: string;
}

export interface UserRef {
  id: string;
  name: string;
}

export type MemoryKind = "preference" | "person" | "project" | "note";

export interface Memory {
  id: string;
  kind: MemoryKind;
  subject: string | null;
  text: string;
  user_id: string | null;
  created_at: string;
  /** Whether the caller may change it: their own, or shared with manage_shared_memories. */
  editable?: boolean;
}

export interface MemoryOwner {
  id: string;
  name: string;
}

export interface Health {
  version: string;
  started_at: string;
  uptime_seconds: number;
  channels: string[];
  senders: string[];
  mcp_servers: string[];
  triggers: boolean;
  /** Which credential signs ai-os in to Claude, and where it comes from; never its value. */
  claude: { auth: "subscription" | "api_key"; variable: string; source: "variable" | "environment" | null } | null;
  counts: Record<string, number>;
  last_problem: string | null;
}

export interface ChannelAccount {
  channel: string;
  address: string;
}

export interface User {
  id: string;
  name: string;
  aliases: string[];
  accounts: ChannelAccount[];
  /** The groups they are in: their only source of rights. */
  group_ids: string[];
  notes: string | null;
}

export interface GroupDoc {
  id: string;
  name: string;
  description: string;
  permissions: Permission[];
  /** Messages, voice notes and trigger runs a member may start a minute; null: the general limit. */
  messages_per_minute?: number | null;
}

export type ClaudeAuth = "subscription" | "api_key";

/** How ai-os signs in to Claude. `auth` is what aios.yaml says, `running_auth` what
 * this process started with; the credentials say where each comes from, never the value. */
export interface ClaudeSettings {
  auth: ClaudeAuth;
  running_auth: ClaudeAuth;
  credentials: Record<ClaudeAuth, { variable: string; source: "variable" | "environment" | null }>;
}

/** What a one-line call to Claude with one credential showed. */
export interface SignInCheck {
  ok: boolean;
  error: string | null;
  model: string | null;
  seconds: number;
}

/** The aios.yaml sections the console's forms edit: each one's schema and what is set. */
export interface SettingsSections {
  sections: Record<string, { schema: Record<string, any>; value: unknown }>;
  /** The collections whose agent access can be changed, with their default. */
  collections?: Record<string, string>;
}

/** A channel as Settings shows it: what it can do, whether it is on (in aios.yaml)
 * and running (since the start), and its values; a secret one's never. */
export interface ChannelSetting {
  name: string;
  title: string;
  description: string;
  capabilities: ("chat" | "send" | "webhook")[];
  enabled: boolean;
  running: boolean;
  checkable: boolean;
  fields: VariableFieldRow[];
  /** How to set it up on the provider's side. */
  setup: SetupStep[];
  /** What commonly goes wrong while setting it up, and the fix. */
  problems: SetupProblem[];
}

/** Somewhere agents post to with `send_webhook`. `url`, `headers` and `body` are
 * templates: `{{field}}` from the agent, `${VAR}` a Variable. */
export interface WebhookDestination {
  name: string;
  description: string;
  method: "POST" | "PUT" | "PATCH" | "GET";
  url: string;
  headers: Record<string, string>;
  /** JSON schema of what the agent gives. */
  fields: Record<string, any>;
  /** A mapping or list is sent as JSON, a string as written, null for none. */
  body: unknown;
  approval: "ask" | "allow" | "deny";
  enabled: boolean;
  /** Variables the templates name that are set nowhere. */
  missing: string[];
}

/** One setup step of a channel, with the provider's page for it and what to watch out for. */
export interface SetupStep {
  text: string;
  link: string | null;
  details: string[];
}

export interface SetupProblem {
  symptom: string;
  fix: string;
}

/** A value something needs (a channel's token, a code connector's key): a Variable,
 * else the environment, else its default. A secret one's value is never sent. */
export interface VariableFieldRow {
  variable: string;
  label: string;
  hint: string;
  secret: boolean;
  required: boolean;
  default?: string | null;
  placeholder: string;
  source: "variable" | "environment" | "default" | null;
  value: string | null;
}

export interface Settings {
  config: string;
  /** aios.yaml's model as JSON schema, for the reference beside the editor. */
  config_schema: Record<string, any>;
  users: User[];
  groups: GroupDoc[];
  permissions: Permission[];
  permission_descriptions?: Record<string, string>;
  restart_needed?: boolean;
  in_repository?: boolean;
}

export interface Agent {
  name: string;
  description: string;
  prompt: string;
  model: string | null;
  enabled: boolean;
  builtin_tools: string[];
  skills: string[];
  connectors: Record<string, string[] | null>;
  /** Who may use it: everyone, group:<id>, role:<id>, user:<id>; null for administrators only. */
  available_to?: string[] | null;
  /** Always there and always on: ai-os depends on it. */
  fixed: boolean;
}

export interface Skill {
  name: string;
  description: string;
  /** SKILL.md without its front matter. */
  content: string;
  /** The agents granted it (granting happens on the agent). */
  agents: string[];
}

/** A group as a list of who something is available to shows it. */
export interface AudienceGroup {
  id: string;
  name: string;
  description?: string;
}

export interface AgentsData {
  agents: Agent[];
  skills: Skill[];
  connectors: {
    name: string;
    enabled: boolean;
    tools: string[] | null;
    /** A code connector's settings as they apply, and which are locked against agents. */
    settings?: Record<string, unknown>;
    locked?: string[];
  }[];
  builtin_tools: string[];
  /** The groups the caller may make an agent available to. */
  groups: AudienceGroup[];
  orchestrator: string;
}

export interface GitBranchRow {
  name: string;
  commit: string;
  author: string;
  date: string;
  subject: string;
  current: boolean;
  /** Commits this branch has that the running one lacks, and the other way round. */
  ahead: number;
  behind: number;
}

export interface RemoteResult {
  action: string;
  ok: boolean;
  message: string;
  at: string;
}

export interface GitRemoteInfo {
  url: string;
  auth: "ssh" | "token" | "none";
  public_key: string | null;
  has_token: boolean;
  auto_push: boolean;
  updated_by: string | null;
  last: RemoteResult | null;
  /** Per local branch, as of the last fetch; null when the remote has no such branch. */
  branches: Record<string, { ahead: number; behind: number } | null>;
}

export interface GitOverview {
  current: string;
  protected: string;
  clean: boolean;
  branches: GitBranchRow[];
}

export interface Variable {
  name: string;
  secret: boolean;
  file: boolean;
  description: string;
  /** Null for a secret: its value never leaves ai-os. */
  value: string | null;
  updated_at: string | null;
  updated_by: string | null;
  used_by: string[];
}

export interface ProbeResult {
  status: string;
  error: string | null;
  server: string | null;
  tools: string[];
  seconds: number;
}

/** A code connector, as the console sees it: its settings, those locked against
 * agents, and the variables it declares. */
export interface CodeConnectorPart {
  name: string;
  found: boolean;
  description: string;
  schema: Record<string, any>;
  settings: Record<string, unknown>;
  locked: string[];
  /** Its server answers `check`: the Test button. */
  checkable: boolean;
  effective: Record<string, unknown>;
  variables: VariableFieldRow[];
}

/** A code connector that can be added, and the agents it brings. */
export interface CodeConnectorOffer {
  name: string;
  description: string;
  agents: string[];
}

export interface Connector {
  id: string;
  /** Set for a code connector. */
  code?: CodeConnectorPart | null;
  description: string;
  config: Record<string, unknown> | null;
  enabled: boolean;
  builtin: boolean;
  status: string | null;
  /** Why it failed, when the last start or turn said so. */
  error?: string | null;
  tools: string[];
  seen_at: string | null;
  used_by: string[];
  /** Null for a connector that cannot be signed in to (a command, or no https). */
  /** Referred to as ${NAME} but set nowhere. */
  missing_variables?: string[];
  /** Never a token. `mine` only for a per-user connector, `shared` where it is used
   * (always for an administrator), `users` for administrators only. */
  sign_in?: {
    mode: SignInMode;
    shared_fallback: boolean;
    mine: SignInState | null;
    shared: SignInState | null;
    users: number | null;
  } | null;
  /** The connector's own setting; administrators only. */
  sign_in_mode?: SignInMode;
  shared_fallback?: boolean;
  /** Whose conversations it is in: everyone, group:<id>, role:<id>, user:<id>; null for administrators only. */
  available_to?: string[] | null;
}

export type SignInMode = "shared" | "per_user";

export interface SignInState {
  signed_in: boolean;
  by: string | null;
  at: string | null;
  expires_at: string | null;
  renewable: boolean;
}

export interface AuditEntry {
  at: string;
  actor: string;
  actor_email: string;
  area: string;
  item: string;
  action: "created" | "changed" | "deleted" | "performed";
  fields: string[];
  detail: string | null;
  commit: string | null;
}

/** The console's own login, if it has one (`web.auth.mode` pick, password, code or sso); null behind a proxy. */
export interface LoginInfo {
  mode: "pick" | "password" | "code" | "sso" | null;
  /** pick: whom the login page offers. */
  users?: UserRef[];
  /** sso: a button for each. */
  providers?: { id: string; kind: "microsoft" | "google" | "oidc"; label: string }[];
}

/** Who has a console password; `users` only for those who manage users. */
export interface PasswordState {
  mine: boolean;
  users: string[] | null;
}

export type StoreKind = "agent" | "skill" | "connector" | "trigger";

/** A git repository the Store offers items from (`store.sources` in aios.yaml). */
export interface StoreSource {
  url: string;
  branch: string | null;
  /** From the source's store.yaml, once fetched. */
  name: string | null;
  description: string | null;
  /** Why the last fetch failed, if it did. */
  error: string | null;
  fetched_at: string | null;
}

export interface StoreRequirement {
  kind: StoreKind;
  id: string;
  installed: boolean;
  /** The same source has it, so it is installed along with the item. */
  in_source: boolean;
}

export interface StoreItem {
  /** The source's url. */
  source: string;
  kind: StoreKind;
  id: string;
  title: string;
  description: string;
  category: string | null;
  /** Markdown: how to set it up, shown before installing. */
  notes: string;
  /** Always false for a trigger: each install adds one. */
  installed: boolean;
  /** A code connector: its server runs on this machine. */
  code: boolean;
  requires: StoreRequirement[];
  /** The item's and those of the requirements installed with it. */
  variables: VariableFieldRow[];
  version: string | null;
  author: string | null;
  license: string | null;
  /** A URL. */
  homepage: string | null;
  tags: string[];
  /** Null when not installed, or installed before versions were tracked. */
  installed_version: string | null;
  /** The source URL it was installed from. */
  installed_from: string | null;
  /** Installed, and the source has a higher version. */
  update_available: boolean;
  /** `kind:id` of what refers to it; only for installed items. */
  used_by: string[];
  /** Installed and not a fixed core agent; never a trigger. */
  removable: boolean;
  /** A connector: the names it is installed under besides its own. */
  copies: string[];
  /** The variables the item itself declares; a copy reads them under names of its own. */
  own_variables: string[];
}

/** By `kind:id`: an item installed from the Store, and still there. */
export type InstalledVersions = Record<
  string,
  {
    version: string | null;
    source: string;
    installed_at: string;
    installed_by: string;
    /** A connector installed under another name: the id the source offers it as. */
    copy_of?: string | null;
    /** Its source's version is a code connector. */
    code?: boolean;
    /** A newer version the source offered when last fetched. */
    latest: string | null;
  }
>;

export interface StoreState {
  sources: StoreSource[];
  items: StoreItem[];
}

export interface StoreInstallRequest {
  source: string;
  kind: StoreKind;
  id: string;
  /** An empty value leaves that variable as it is. */
  variables: Record<string, string>;
  replace: boolean;
  trust_code: boolean;
  /** A connector only: installed under this name, with variables of its own. */
  name?: string;
}

/** `kind:id` of what was installed, kept as it was, or needed and found nowhere. */
export interface StoreInstallResult {
  installed: string[];
  kept: string[];
  missing: string[];
  moved_secrets: string[];
  version: string | null;
}

/** `removed`: `kind:id`, and for a code connector its files under code/. */
export interface StoreUninstallResult {
  removed: string[];
  still_used_by: string[];
}
