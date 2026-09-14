import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import type { Client } from "@/lib/types"
import { DEMO_ID, MOCK_GRAPH, renderWithProviders } from "@/test/utils"
import { ClientDetailPage } from "../ClientDetailPage"
import { ClientListPage } from "../ClientListPage"

function client(i: number): Client {
  return {
    id: `client-${i}`, slug: `client-${i}`, name: `Client ${String(i).padStart(2, "0")}`, legal_name: null, status: "active",
    default_currency: "USD", timezone: "UTC", locale: "en-US", billing_email: null, support_email: null, trip_number_prefix: null,
    created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
  }
}
const page = <T,>(items: T[], total: number, p: number, size: number) => ({ items, total, page: p, page_size: size })

function mockApi(overrides: Record<string, unknown> = {}) {
  return vi.spyOn(api, "get").mockImplementation(async (path: string) => {
    const key = Object.keys(overrides).find((k) => path.startsWith(k))
    if (key) return overrides[key]
    if (path.startsWith("/clients?")) {
      const p = Number(new URL(`http://x${path}`).searchParams.get("page") ?? 1)
      const items = Array.from({ length: p === 2 ? 5 : 25 }, (_, i) => client((p - 1) * 25 + i + 1))
      return page(items, 30, p, 25)
    }
    if (path.startsWith(`/clients/${DEMO_ID}`)) return { ...client(1), id: DEMO_ID, name: "Demo Brokerage" }
    if (path.startsWith("/segments")) return page([{ id: "s1", name: "UHNW", code: "UHNW", segment_type: "uhnw" }], 5, 1, 100)
    if (path.startsWith("/contacts")) return page([{ id: "c1", display_name: "Victoria Ashworth", status: "active", primary_email: "v@x.test", company_name: null }], 8, 1, 25)
    if (path.startsWith("/trips/upcoming")) return page([], 1, 1, 5)
    if (path.startsWith("/trips")) return page([{ id: "t1", trip_number: "BLX-2026-001", total_sell_cents: 4_419_000 }], 5, 1, 500)
    if (path.startsWith("/activities")) return page([{ id: "a1", subject: "Discovery call", activity_type: "call", direction: "outbound", occurred_at: "2026-09-01T10:00:00Z" }], 20, 1, 8)
    if (path.startsWith("/invoices/ar-aging")) return { as_of: "2026-09-14", buckets: { current: { bucket: "current", count: 1, balance_cents: 1_459_500 } } }
    if (path.startsWith("/graph/")) return MOCK_GRAPH
    return page([], 0, 1, 25)
  })
}

describe("ClientListPage", () => {
  it("renders one row per client and the paging summary", async () => {
    mockApi()
    renderWithProviders(<ClientListPage />, { route: "/clients", path: "/clients" })
    await waitFor(() => expect(screen.getAllByTestId("table-row")).toHaveLength(25))
    expect(screen.getByText("Client 01")).toBeInTheDocument()
    expect(screen.getByTestId("pagination")).toHaveTextContent("1–25 of 30")
    expect(screen.getByRole("button", { name: /New Client/ })).toBeInTheDocument()
  })

  it("requests the next page when paging forward", async () => {
    const get = mockApi()
    const user = userEvent.setup()
    renderWithProviders(<ClientListPage />, { route: "/clients", path: "/clients" })
    await waitFor(() => expect(screen.getAllByTestId("table-row")).toHaveLength(25))
    await user.click(screen.getByRole("button", { name: "Next page" }))
    await waitFor(() => expect(get.mock.calls.some(([p]) => String(p).startsWith("/clients?page=2"))).toBe(true))
    await waitFor(() => expect(screen.getAllByTestId("table-row")).toHaveLength(5))
    expect(screen.getByTestId("pagination")).toHaveTextContent("26–30 of 30")
  })
})

describe("ClientDetailPage", () => {
  it("loads the client, shows Overview KPIs, and switches tabs", async () => {
    mockApi()
    const user = userEvent.setup()
    renderWithProviders(<ClientDetailPage />, { route: `/clients/${DEMO_ID}`, path: "/clients/:id" })
    expect(await screen.findByRole("heading", { name: /Demo Brokerage/ })).toBeInTheDocument()
    await waitFor(() => expect(screen.getAllByTestId("kpi")).toHaveLength(4))
    expect(screen.getByText("$44,190.00")).toBeInTheDocument() // lifetime value from the mocked trip
    await user.click(screen.getByTestId("tab-contacts"))
    expect(await screen.findByTestId("related-row")).toHaveTextContent("Victoria Ashworth")
  })

  it("embeds the relationship graph in the Relationship tab", async () => {
    const get = mockApi()
    const user = userEvent.setup()
    const { container } = renderWithProviders(<ClientDetailPage />, { route: `/clients/${DEMO_ID}`, path: "/clients/:id" })
    await screen.findByRole("heading", { name: /Demo Brokerage/ })
    await user.click(screen.getByTestId("tab-relationship"))
    await waitFor(() => expect(within(container).getAllByTestId("relationship-graph")).toHaveLength(1))
    await waitFor(() => expect(container.querySelectorAll("[data-node]")).toHaveLength(5))
    expect(get).toHaveBeenCalledWith(`/graph/client/${DEMO_ID}?depth=1`, expect.anything())
  })
})
