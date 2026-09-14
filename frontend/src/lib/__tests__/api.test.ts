import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { api, ApiError, setUnauthorizedHandler, tokenStore } from "@/lib/api"

type Handler = (url: string, init: RequestInit | undefined) => Response

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })
}

describe("apiFetch", () => {
  let calls: Array<{ url: string; init: RequestInit | undefined }>
  beforeEach(() => {
    calls = []
    tokenStore.set("stale-token")
  })
  afterEach(() => {
    tokenStore.clear()
    setUnauthorizedHandler(null)
  })

  function mockFetch(handler: Handler) {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      calls.push({ url, init })
      return handler(url, init)
    }))
  }

  it("on 401 refreshes once via the cookie endpoint and retries with the new token", async () => {
    mockFetch((url, init) => {
      if (url.endsWith("/auth/refresh")) return json(200, { access_token: "fresh-token", token_type: "bearer", expires_in: 900 })
      const auth = new Headers(init?.headers).get("Authorization")
      return auth === "Bearer fresh-token" ? json(200, { ok: true }) : json(401, { error: { code: "unauthorized", message: "expired", details: {} } })
    })
    const result = await api.get<{ ok: boolean }>("/contacts")
    expect(result).toEqual({ ok: true })
    expect(calls.map((c) => c.url.replace(/^.*\/api\/v1/, ""))).toEqual(["/contacts", "/auth/refresh", "/contacts"])
    expect(calls[1]?.init?.credentials).toBe("include") // the HttpOnly refresh cookie rides along
    expect(tokenStore.get()).toBe("fresh-token")
    expect(typeof localStorage.getItem("access_token")).toBe("object") // null: nothing is ever persisted
  })

  it("gives up after one retry, surfaces the 401, and notifies the unauthorized handler", async () => {
    const onUnauthorized = vi.fn()
    setUnauthorizedHandler(onUnauthorized)
    mockFetch((url) => (url.endsWith("/auth/refresh") ? json(401, { error: { code: "unauthorized", message: "no cookie", details: {} } }) : json(401, { error: { code: "unauthorized", message: "expired", details: {} } })))
    await expect(api.get("/contacts")).rejects.toMatchObject({ status: 401, code: "unauthorized" } satisfies Partial<ApiError>)
    expect(calls.map((c) => c.url.replace(/^.*\/api\/v1/, ""))).toEqual(["/contacts", "/auth/refresh"])
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
    expect(tokenStore.get()).toBeNull()
  })

  it("parses the API error envelope into ApiError", async () => {
    mockFetch(() => json(404, { error: { code: "not_found", message: "Contact not found", details: { id: "x" } } }))
    const err = await api.get("/contacts/x").catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).message).toBe("Contact not found")
    expect((err as ApiError).details).toEqual({ id: "x" })
  })
})
