// The only place that talks to the backend.
//
// - Sends cookies with every request (credentials: "include").
// - Adds the X-CSRF-Token header to POST, PATCH and DELETE (copied from the readable
//   mentora_csrf cookie), which the backend requires.
// - When a request returns 401, refreshes the session once and retries.

import type { ApiErrorBody } from "../types/api";

const API_BASE = "/api/v1";
const CSRF_COOKIE = "mentora_csrf";
const NO_REFRESH = ["/auth/login", "/auth/signup", "/auth/refresh", "/auth/logout"];

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: { field: string; message: string }[];

  constructor(status: number, code: string, message: string, details: ApiError["details"] = []) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function readCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as ApiErrorBody;
    return new ApiError(response.status, body.error.code, body.error.message, body.error.details);
  } catch {
    return new ApiError(response.status, "network_error", response.statusText);
  }
}

// If several requests get 401 at once, they share one refresh call.
let refreshing: Promise<boolean> | null = null;

function refreshSession(): Promise<boolean> {
  refreshing ??= send("POST", "/auth/refresh")
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

function send(method: string, path: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  return fetch(API_BASE + path, {
    method,
    credentials: "include",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await send(method, path, body);
    // No CSRF cookie means there was never a session, so there is nothing to refresh.
    const hadSession = readCookie(CSRF_COOKIE) !== null;
    if (
      response.status === 401 &&
      hadSession &&
      !NO_REFRESH.includes(path) &&
      (await refreshSession())
    ) {
      response = await send(method, path, body);
    }
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the server.");
  }
  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
};
