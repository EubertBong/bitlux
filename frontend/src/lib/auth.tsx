/**
 * Authentication state for the SPA.
 *
 * On mount we try a silent refresh (the HttpOnly cookie) and then GET /auth/me.
 * Permissions come from /auth/me, already expanded by the backend; `can()` also
 * honours `<resource>.manage` implying the other actions, matching the API.
 */

import * as React from "react"
import { Navigate, useLocation } from "react-router"
import { api, refreshAccessToken, setUnauthorizedHandler, tokenStore } from "./api"
import type { Me, TokenPair } from "./types"

export type AuthStatus = "loading" | "authenticated" | "anonymous"

export interface AuthContextValue {
  status: AuthStatus
  user: Me | null
  permissions: ReadonlySet<string>
  can: (permission: string) => boolean
  login: (email: string, password: string, clientSlug?: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<boolean>
}

const AuthContext = React.createContext<AuthContextValue | null>(null)

/** A boolean hint -- not a credential -- that this browser has signed in before, so the
 * app can skip the silent refresh (and its 401) on a first visit. Cleared on sign-out. */
const SESSION_HINT_KEY = "bitlux-session"
const sessionHint = {
  get: (): boolean => {
    try {
      return localStorage.getItem(SESSION_HINT_KEY) === "1"
    } catch {
      return false
    }
  },
  set: (on: boolean): void => {
    try {
      if (on) localStorage.setItem(SESSION_HINT_KEY, "1")
      else localStorage.removeItem(SESSION_HINT_KEY)
    } catch {
      /* ignore */
    }
  },
}

export function hasPermission(perms: ReadonlySet<string>, key: string): boolean {
  if (perms.has(key)) return true
  const resource = key.split(".")[0]
  return resource !== undefined && perms.has(`${resource}.manage`) && !key.endsWith(".transfer")
}

export function AuthProvider({ children, initialUser = null }: { children: React.ReactNode; initialUser?: Me | null }) {
  const [status, setStatus] = React.useState<AuthStatus>(initialUser ? "authenticated" : "loading")
  const [user, setUser] = React.useState<Me | null>(initialUser)

  const loadMe = React.useCallback(async (): Promise<boolean> => {
    try {
      const me = await api.get<Me>("/auth/me")
      setUser(me)
      setStatus("authenticated")
      return true
    } catch {
      setUser(null)
      setStatus("anonymous")
      return false
    }
  }, [])

  React.useEffect(() => {
    if (initialUser) return
    let cancelled = false
    ;(async () => {
      const ok = tokenStore.get() ? true : sessionHint.get() ? await refreshAccessToken() : false
      if (cancelled) return
      if (ok) await loadMe()
      else setStatus("anonymous")
    })()
    return () => {
      cancelled = true
    }
  }, [initialUser, loadMe])

  React.useEffect(() => {
    setUnauthorizedHandler(() => {
      tokenStore.clear()
      setUser(null)
      setStatus("anonymous")
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  const login = React.useCallback(
    async (email: string, password: string, clientSlug?: string) => {
      const pair = await api.post<TokenPair>("/auth/login", { email, password, client_slug: clientSlug ?? null })
      tokenStore.set(pair.access_token) // memory only; the refresh token arrived as an HttpOnly cookie
      sessionHint.set(true)
      await loadMe()
    },
    [loadMe],
  )

  const logout = React.useCallback(async () => {
    try {
      await api.post<void>("/auth/logout")
    } catch {
      /* logout is idempotent server-side; local state is what matters */
    }
    tokenStore.clear()
    sessionHint.set(false)
    setUser(null)
    setStatus("anonymous")
  }, [])

  const refresh = React.useCallback(async () => {
    const ok = await refreshAccessToken()
    if (ok) await loadMe()
    return ok
  }, [loadMe])

  const permissions = React.useMemo(() => new Set(user?.permissions ?? []), [user])
  const can = React.useCallback((key: string) => hasPermission(permissions, key), [permissions])

  const value = React.useMemo<AuthContextValue>(
    () => ({ status, user, permissions, can, login, logout, refresh }),
    [status, user, permissions, can, login, logout, refresh],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = React.useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>")
  return ctx
}

export function FullPageSpinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex h-full min-h-[40vh] items-center justify-center text-sm text-muted-foreground" role="status">
      {label}
    </div>
  )
}

/** Gate: unauthenticated users go to /login and come back afterwards. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()
  if (status === "loading") return <FullPageSpinner />
  if (status === "anonymous") return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <>{children}</>
}

export function Forbidden({ permission }: { permission?: string }) {
  return (
    <div className="mx-auto max-w-lg py-16 text-center" role="alert">
      <h1 className="text-xl font-semibold">You don't have access to this page</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        {permission ? (
          <>
            Your role does not include the <code className="rounded bg-muted px-1">{permission}</code> permission.
          </>
        ) : (
          "Ask an administrator if you think you should."
        )}
      </p>
    </div>
  )
}

/** Gate: renders children only if the current user has the permission. */
export function RequirePermission({ permission, children }: { permission: string; children: React.ReactNode }) {
  const { can } = useAuth()
  if (!can(permission)) return <Forbidden permission={permission} />
  return <>{children}</>
}
