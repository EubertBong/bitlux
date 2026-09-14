import { screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import * as apiModule from "@/lib/api"
import { RequireAuth, RequirePermission } from "@/lib/auth"
import { LoginPage } from "@/pages/LoginPage"
import { BROKER, renderWithProviders } from "@/test/utils"

describe("auth guards", () => {
  it("redirects unauthenticated users to /login (after the silent refresh fails)", async () => {
    vi.spyOn(apiModule, "refreshAccessToken").mockResolvedValue(false)
    renderWithProviders(
      <RequireAuth>
        <div>SECRET</div>
      </RequireAuth>,
      { user: null, route: "/clients" },
    )
    expect(await screen.findByText("LOGIN PAGE")).toBeInTheDocument()
    expect(screen.queryByText("SECRET")).not.toBeInTheDocument()
  })

  it("renders a Forbidden message when the permission is missing", () => {
    renderWithProviders(
      <RequirePermission permission="invoices.view">
        <div>INVOICES</div>
      </RequirePermission>,
    )
    expect(screen.getByRole("alert")).toHaveTextContent("invoices.view")
    expect(screen.queryByText("INVOICES")).not.toBeInTheDocument()
  })

  it("treats <resource>.manage as implying the other actions", () => {
    renderWithProviders(
      <RequirePermission permission="trips.delete">
        <div>DELETE TRIPS</div>
      </RequirePermission>,
      { user: { ...BROKER, permissions: ["trips.manage"] } },
    )
    expect(screen.getByText("DELETE TRIPS")).toBeInTheDocument()
  })

  it("sends an already-authenticated user away from /login", async () => {
    renderWithProviders(<LoginPage />, { route: "/login", path: "/login" })
    // the wrapper mounts "*" -> nothing at "/", so the redirect leaves the login form unmounted
    expect(screen.queryByLabelText("Email")).not.toBeInTheDocument()
  })
})
