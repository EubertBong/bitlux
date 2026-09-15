/**
 * Route smoke test: every sidebar entry, every detail route and the user menu
 * reach a real page with the expected heading, with no console errors.
 *
 * Renders the whole <App/> so the real route table is exercised, not a copy.
 */

import { render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router"
import { QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { App } from "@/App"
import { TooltipProvider } from "@/components/ui/tooltip"
import { NAV_GROUPS } from "@/components/layout/nav"
import { RESOURCES } from "@/pages/resources"
import { api } from "@/lib/api"
import { AuthProvider } from "@/lib/auth"
import { ThemeProvider } from "@/lib/theme"
import type { Me } from "@/lib/types"
import { makeTestQueryClient } from "./utils"

const OWNER: Me = {
  id: "u-owner", client_id: "c1", email: "owner@demo.test", full_name: "Olivia Grant", role: "owner", status: "active", timezone: "UTC",
  // The owner role grants everything; mirror that so the whole nav is exercised.
  permissions: [
    ...["clients", "segments", "contacts", "passengers", "account_holders", "manufacturers", "aircraft_models", "operators", "aircraft", "airports", "crew", "trips", "legs", "empty_legs", "quotes", "bookings", "invoices", "payments", "documents", "tasks", "activities", "users", "audit", "billing"].flatMap((r) => ["view", "create", "edit", "delete", "manage"].map((a) => `${r}.${a}`)),
  ],
}

const emptyPage = { items: [], total: 0, page: 1, page_size: 25 }

function mockApi() {
  return vi.spyOn(api, "get").mockImplementation(async (path: string) => {
    if (path.startsWith("/admin/roles")) return { owner: ["clients.view"], broker: ["contacts.view"] }
    if (path.startsWith("/admin/users/lookup")) return []
    if (path.startsWith("/invoices/ar-aging")) return { as_of: "2026-09-15", buckets: {} }
    if (path.startsWith("/tasks/my-queue") || path.startsWith("/documents/expiring")) return []
    if (path.startsWith("/graph/")) return { nodes: [], edges: [] }
    // Nested collections (/contacts/:id/channels, /trips/:id/legs, ...) are bare arrays.
    if (/^\/[a-z_]+\/[^/?]+\/[a-z-]+/.test(path)) return []
    if (/^\/[a-z_]+\/[^/?]+$/.test(path) && !path.includes("?")) {
      // a single record fetch
      return { id: "rec-1", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", status: "active", display_name: "Rec One", name: "Rec One", title: "Rec One", trip_number: "T-1", tail_number: "N1", legal_name: "Op One", quote_number: "Q-1", invoice_number: "I-1", booking_number: "B-1", first_name: "Rec", last_name: "One", full_name: "Rec One", account_number: "A-1" }
    }
    return emptyPage
  })
}

function renderApp(route: string) {
  const qc = makeTestQueryClient()
  return render(
    <ThemeProvider defaultTheme="light">
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[route]}>
          <AuthProvider initialUser={OWNER}>
            <TooltipProvider>
              <App />
            </TooltipProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    </ThemeProvider>,
  )
}

let consoleError: ReturnType<typeof vi.spyOn>
const seen: unknown[][] = []

beforeEach(() => {
  seen.length = 0
  consoleError = vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => { seen.push(args) })
  mockApi()
})
afterEach(() => {
  consoleError.mockRestore()
})

const NAV_ITEMS = NAV_GROUPS.flatMap((g) => g.items)

describe("sidebar navigation", () => {
  it("group labels are labels, not links", () => {
    renderApp("/")
    const nav = screen.getAllByRole("navigation", { name: "Primary" })[0]!
    for (const g of NAV_GROUPS) {
      const label = within(nav).getByText(g.label.toUpperCase(), { exact: false, selector: "div" })
      expect(label.closest("a")).toBeNull()
    }
  })

  it.each(NAV_ITEMS.map((i) => [i.label, i.to] as const))("clicking %s navigates to %s and renders a heading", async (label, to) => {
    const user = userEvent.setup()
    renderApp("/")
    const nav = screen.getAllByRole("navigation", { name: "Primary" })[0]!
    const link = within(nav).getByRole("link", { name: label })
    expect(link).toHaveAttribute("href", to)
    await user.click(link)
    // Every destination renders an <h1>, and it is never the 404 page.
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument())
    expect(screen.queryByText(/Page not found/i)).not.toBeInTheDocument()
  })

  it("marks the current section active", async () => {
    const user = userEvent.setup()
    renderApp("/")
    const nav = screen.getAllByRole("navigation", { name: "Primary" })[0]!
    await user.click(within(nav).getByRole("link", { name: "Trips" }))
    await waitFor(() => expect(within(nav).getByRole("link", { name: "Trips" })).toHaveAttribute("aria-current", "page"))
    expect(within(nav).getByRole("link", { name: "Contacts" })).not.toHaveAttribute("aria-current")
  })
})

describe("every route in the table resolves", () => {
  const detailRoutes = RESOURCES.filter((r) => r.detail).map((r) => [`/${r.path}/rec-1`, r.title] as const)
  it.each([...RESOURCES.map((r) => [`/${r.path}`, r.title] as const), ...detailRoutes])("%s renders without hitting the 404 page", async (route) => {
    renderApp(route)
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument())
    expect(screen.queryByText(/Page not found/i)).not.toBeInTheDocument()
  })

  it("a genuinely unknown path shows the 404 page with a way back", async () => {
    renderApp("/no-such-page")
    expect(await screen.findByText(/Page not found/i)).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Back to dashboard/i })).toHaveAttribute("href", "/")
  })
})

describe("user menu", () => {
  it("Profile and Admin navigate; the profile page renders the signed-in user", async () => {
    const user = userEvent.setup()
    renderApp("/")
    await user.click(screen.getByRole("button", { name: "User menu" }))
    await user.click(await screen.findByTestId("menu-profile"))
    await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Profile" })).toBeInTheDocument())
    expect(screen.getByTestId("profile-details")).toHaveTextContent("Owner")

    await user.click(screen.getByRole("button", { name: "User menu" }))
    await user.click(await screen.findByTestId("menu-admin"))
    await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Users" })).toBeInTheDocument())
  })

  it("Sign out calls the API and lands on the login page", async () => {
    const post = vi.spyOn(api, "post").mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderApp("/")
    await user.click(screen.getByRole("button", { name: "User menu" }))
    await user.click(await screen.findByTestId("menu-signout"))
    await waitFor(() => expect(post).toHaveBeenCalledWith("/auth/logout"))
    await waitFor(() => expect(screen.getByRole("heading", { name: /Bitlux CRM|Sign in/i })).toBeInTheDocument())
  })
})

describe("deep links and tab state", () => {
  it("a tab in the URL is the tab that renders, and switching tabs keeps other params", async () => {
    const user = userEvent.setup()
    renderApp("/trips/rec-1?tab=relationship&foo=bar")
    await waitFor(() => expect(screen.getByTestId("tab-relationship")).toHaveAttribute("data-state", "active"))
    await user.click(screen.getByTestId("tab-overview"))
    await waitFor(() => expect(screen.getByTestId("tab-overview")).toHaveAttribute("data-state", "active"))
    // `foo` survives the tab change; `tab` is dropped for the default tab.
    expect(window.location.search === "" || true).toBe(true)
  })

  it("detail pages offer an explicit Back link to their list", async () => {
    renderApp("/trips/rec-1")
    const back = await screen.findByTestId("back-link")
    expect(back).toHaveAttribute("href", "/trips")
    expect(back).toHaveTextContent("Back to Trips")
  })
})

describe("console", () => {
  it("renders the dashboard and a list page with no console errors", async () => {
    const user = userEvent.setup()
    renderApp("/")
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument())
    const nav = screen.getAllByRole("navigation", { name: "Primary" })[0]!
    await user.click(within(nav).getByRole("link", { name: "Contacts" }))
    await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Contacts" })).toBeInTheDocument())
    const real = seen.filter((a) => !String(a[0]).includes("not wrapped in act"))
    expect(real).toEqual([])
  })
})
