/**
 * The one HTTP client.
 *
 * Token model (the brief's second option): the access token lives in this
 * module's memory only -- never localStorage, never a cookie the SPA can read.
 * The refresh token is an HttpOnly cookie set by the API on /auth/login and
 * rotated on /auth/refresh; this code never sees it. On a 401 the client asks
 * /auth/refresh (cookie goes along via credentials: "include"), stores the new
 * access token in memory and retries the original request exactly once.
 * Concurrent 401s share one in-flight refresh.
 */

import { API_BASE_URL } from "./config"
import type { ApiErrorBody, TokenPair } from "./types"

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>
  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.details = details
  }
}

let accessToken: string | null = null
let refreshInFlight: Promise<boolean> | null = null
let onUnauthorized: (() => void) | null = null

export const tokenStore = {
  get: (): string | null => accessToken,
  set: (token: string | null): void => {
    accessToken = token
  },
  clear: (): void => {
    accessToken = null
  },
}

/** Called when a refresh fails: the AuthProvider uses it to drop to the login screen. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

function isApiErrorBody(v: unknown): v is ApiErrorBody {
  return typeof v === "object" && v !== null && "error" in v && typeof (v as { error: unknown }).error === "object"
}

async function parseError(res: Response): Promise<ApiError> {
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    /* non-JSON error body */
  }
  if (isApiErrorBody(body)) {
    return new ApiError(res.status, body.error.code, body.error.message, body.error.details)
  }
  return new ApiError(res.status, "http_error", res.statusText || `HTTP ${res.status}`)
}

/** POST /auth/refresh using the HttpOnly cookie. Single-flight. */
export function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/auth/refresh`, { method: "POST", credentials: "include" })
      if (!res.ok) {
        tokenStore.clear()
        return false
      }
      const pair = (await res.json()) as TokenPair
      tokenStore.set(pair.access_token)
      return true
    } catch {
      tokenStore.clear()
      return false
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE"
  body?: unknown
  signal?: AbortSignal
  /** Internal: set once a refresh+retry has been attempted. */
  _retried?: boolean
}

const AUTH_PATHS = ["/auth/login", "/auth/refresh", "/auth/logout"]

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers()
  headers.set("Accept", "application/json")
  const token = tokenStore.get()
  if (token) headers.set("Authorization", `Bearer ${token}`)
  let body: BodyInit | undefined
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json")
    body = JSON.stringify(options.body)
  }
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body,
    credentials: "include",
    signal: options.signal,
  })

  if (res.status === 401 && !options._retried && !AUTH_PATHS.some((p) => path.startsWith(p))) {
    const refreshed = await refreshAccessToken()
    if (refreshed) return apiFetch<T>(path, { ...options, _retried: true })
    onUnauthorized?.()
  }
  if (!res.ok) throw await parseError(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

/** Build a query string, skipping undefined / null / empty values. */
export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue
    sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ""
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => apiFetch<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => apiFetch<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body: unknown) => apiFetch<T>(path, { method: "PATCH", body }),
  delete: <T = void>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
}
