export type Visibility = "private" | "team" | "public";

export function formatDate(iso: string): { label: string; full: string } {
  const date = new Date(iso);
  const full = date.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit",
  });
  const now = Date.now();
  const diff = now - date.getTime();
  const mins = Math.floor(diff / 60_000);
  const hours = Math.floor(diff / 3_600_000);
  const days = Math.floor(diff / 86_400_000);
  let label: string;
  if (mins < 1) label = "Just now";
  else if (mins < 60) label = `${mins}m ago`;
  else if (hours < 24) label = `${hours}h ago`;
  else if (days === 1) label = "Yesterday";
  else if (days < 7) label = `${days} days ago`;
  else label = date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  return { label, full };
}

export interface Invite {
  token: string;
  team_id: string;
  invited_by: string;
  created_at: string;
  expires_at: string;
  link: string | null;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  team_id: string | null;
}

export interface TeamMembersResponse {
  team_id: string;
  members: User[];
}

export interface TemplateSummary {
  schema_name: string;
  owner_id: string;
  owner_name: string;
  visibility: Visibility;
  team_id: string | null;
  updated_at: string | null;
}

export interface SchemaListResponse {
  schemas: string[];
  templates: TemplateSummary[];
}

export interface SchemaDetail {
  schema_name: string;
  schema: Record<string, unknown>;
  owner_id: string | null;
  visibility: Visibility | null;
  team_id: string | null;
  updated_at: string | null;
}

export interface ValidationErrorDetail {
  path: string;
  message: string;
  validator?: string | null;
}

export interface ValidateResponse {
  valid: boolean;
  errors: ValidationErrorDetail[];
  suggestion?: string | null;
}

export interface BatchValidateResultItem {
  index: number;
  valid: boolean;
  errors: ValidationErrorDetail[];
}

export interface BatchValidateResponse {
  results: BatchValidateResultItem[];
}

export interface PayloadSummary {
  payload_name: string;
  owner_id: string;
  owner_name: string;
  visibility: Visibility;
  team_id: string | null;
  schema_name: string | null;
  updated_at: string | null;
}

export interface PayloadDetail {
  payload_name: string;
  content: Record<string, unknown>;
  owner_id: string;
  visibility: Visibility;
  team_id: string | null;
  schema_name: string | null;
  updated_at: string | null;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown, message?: string) {
    super(message ?? `Request failed with status ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

const API_URL = import.meta.env.VITE_API_URL ?? "";

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler;
}

function getToken(): string | null {
  return localStorage.getItem("token");
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem("token", token);
  } else {
    localStorage.removeItem("token");
  }
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  auth?: boolean;
};

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = getToken();
  if (options.auth !== false && token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, null, "Unable to reach server");
  }

  const text = await response.text();
  let data: { detail?: unknown } | null = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new ApiError(response.status, text, "Unexpected server response");
    }
  }

  if (!response.ok) {
    if (response.status === 401 && options.auth !== false) {
      onUnauthorized?.();
    }
    throw new ApiError(response.status, data?.detail ?? data, formatApiError(response.status, data));
  }

  return data as T;
}

export function formatApiError(status: number, data: { detail?: unknown } | null): string {
  if (status === 401) return "Please sign in to continue";
  if (status === 403) return "You don't have permission to perform this action";
  if (status === 404) return "Resource not found";
  if (status === 422) {
    if (Array.isArray(data?.detail)) {
      return data.detail
        .map((e: { message?: string; loc?: unknown[] }) => {
          const field = Array.isArray(e.loc) ? e.loc.filter((s) => s !== "body").join(".") : null;
          const msg = e.message ?? "Validation error";
          return field ? `${field}: ${msg}` : msg;
        })
        .join("; ");
    }
    return String(data?.detail ?? "Validation failed");
  }
  if (status === 500) return "Something went wrong on the server";
  if (status === 0) return "Unable to reach server";
  return String(data?.detail ?? "Request failed");
}

export const api = {
  health: () => apiRequest<{ status: string }>("/health", { auth: false }),
  me: () => apiRequest<User>("/auth/me"),
  listSchemas: () => apiRequest<SchemaListResponse>("/schemas"),
  getSchema: (name: string) => apiRequest<SchemaDetail>(`/schemas/${encodeURIComponent(name)}`),
  uploadSchema: (payload: {
    schema_name: string;
    schema: Record<string, unknown>;
    visibility?: Visibility;
    team_id?: string | null;
  }) => apiRequest("/schemas/upload", { method: "POST", body: payload }),
  updateSchema: (
    name: string,
    payload: { schema?: Record<string, unknown>; visibility?: Visibility; team_id?: string | null },
  ) => apiRequest(`/schemas/${encodeURIComponent(name)}`, { method: "PUT", body: payload }),
  deleteSchema: (name: string) =>
    apiRequest(`/schemas/${encodeURIComponent(name)}`, { method: "DELETE" }),
  verifySchema: (schema: Record<string, unknown>) =>
    apiRequest<{ valid: boolean; message: string | null }>("/schemas/verify", {
      method: "POST",
      body: { schema },
    }),
  validateSingle: (schema_name: string, payload: Record<string, unknown>, explain = false) =>
    apiRequest<ValidateResponse>(`/validate/single${explain ? "?explain=true" : ""}`, {
      method: "POST",
      body: { schema_name, payload },
    }),
  validateBatch: (schema_name: string, payloads: Record<string, unknown>[]) =>
    apiRequest<BatchValidateResponse>("/validate/batch", {
      method: "POST",
      body: { items: payloads.map((payload) => ({ schema_name, payload })) },
    }),
  listPayloads: () =>
    apiRequest<{ payloads: PayloadSummary[] }>("/payloads"),
  getPayload: (name: string) =>
    apiRequest<PayloadDetail>(`/payloads/${encodeURIComponent(name)}`),
  savePayload: (
    payload_name: string,
    content: Record<string, unknown>,
    visibility: Visibility,
    schema_name?: string | null,
    team_id?: string | null,
  ) =>
    apiRequest<PayloadDetail>("/payloads", {
      method: "POST",
      body: { payload_name, content, visibility, schema_name: schema_name ?? null, team_id: team_id ?? null },
    }),
  updatePayload: (payload_name: string, content: Record<string, unknown>, visibility?: Visibility, schema_name?: string | null) =>
    apiRequest<PayloadDetail>(`/payloads/${encodeURIComponent(payload_name)}`, {
      method: "PUT",
      body: { content, visibility, schema_name: schema_name ?? undefined },
    }),
  deletePayload: (payload_name: string) =>
    apiRequest(`/payloads/${encodeURIComponent(payload_name)}`, { method: "DELETE" }),
  updateMe: (body: { team_id?: string | null }) => apiRequest<User>("/auth/me", { method: "PUT", body }),
  listUsers: () => apiRequest<User[]>("/auth/users"),
  listTeamMembers: () => apiRequest<TeamMembersResponse>("/auth/team/members"),
  updateUser: (userId: string, body: { role?: string; team_id?: string | null }) =>
    apiRequest<User>(`/auth/users/${encodeURIComponent(userId)}`, { method: "PUT", body }),
  loginUrl: (provider: "google" | "github") => `${API_URL}/auth/login/${provider}`,
  deleteMe: () => apiRequest("/auth/me", { method: "DELETE" }),
  createInvite: () =>
    apiRequest<Invite>("/invites", { method: "POST" }),
  listInvites: () => apiRequest<Invite[]>("/invites"),
  getInvite: (token: string) => apiRequest<Invite>(`/invites/${encodeURIComponent(token)}`, { auth: false }),
  acceptInvite: (token: string) =>
    apiRequest<Invite>(`/invites/${encodeURIComponent(token)}/accept`, { method: "POST" }),
  revokeInvite: (token: string) =>
    apiRequest(`/invites/${encodeURIComponent(token)}`, { method: "DELETE" }),
};
