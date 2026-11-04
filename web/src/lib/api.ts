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

export type Permission = "chat" | "approve" | "receive_unapproved" | "manage_users" | "administer";

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
}

export interface ConversationEvent {
  conversation_id: string;
  kind: "message" | "progress" | "delta" | "done" | "approval";
  text: string;
  restart: boolean;
  message: Message | null;
  approval_id: string | null;
  options: string[];
}

export interface Approval {
  id: string;
  conversation_id: string;
  channel: string;
  question: string;
  options: string[];
  created_at: string;
}

export interface Schedule {
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
  created_at: string;
}

export interface Health {
  version: string;
  started_at: string;
  uptime_seconds: number;
  channels: string[];
  senders: string[];
  mcp_servers: string[];
  scheduler: boolean;
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
  role_ids: string[];
  notes: string | null;
}

export interface RoleDoc {
  id: string;
  name: string;
  permissions: Permission[];
}

export interface Settings {
  config: string;
  users: User[];
  roles: RoleDoc[];
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

export interface AgentsData {
  agents: Agent[];
  skills: Skill[];
  connectors: { name: string; enabled: boolean; tools: string[] | null }[];
  builtin_tools: string[];
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

export interface Connector {
  id: string;
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
  sign_in?: { signed_in: boolean; by: string | null; at: string | null; expires_at: string | null; renewable: boolean } | null;
}
