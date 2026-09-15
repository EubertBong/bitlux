import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { api } from "@/lib/api"
import { renderWithProviders } from "@/test/utils"
import { RESOURCES, ResourceDetailPage, ResourceListPage } from "../resources"

const spec = (path: string) => RESOURCES.find((r) => r.path === path)!
const page = <T,>(items: T[], total = items.length) => ({ items, total, page: 1, page_size: 25 })

function mockGet(map: Record<string, unknown>) {
  return vi.spyOn(api, "get").mockImplementation(async (path: string) => {
    const key = Object.keys(map).find((k) => path.startsWith(k))
    if (key) return map[key]
    return page([])
  })
}

describe("generic list pages", () => {
  it("airports (no form yet): New is visible but disabled with the planned hint; rows render with a row menu", async () => {
    mockGet({ "/airports?": page([{ id: "ap1", icao_code: "KTEB", iata_code: "TEB", name: "Teterboro", city: "Teterboro", country_code: "US", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }]) })
    renderWithProviders(<ResourceListPage resource={spec("airports")} />, { route: "/airports", path: "/airports", user: { id: "o", client_id: "x", email: "o@d", full_name: "Owner", role: "owner", status: "active", timezone: null, permissions: ["airports.view", "airports.create", "airports.edit", "airports.delete"] } })
    await waitFor(() => expect(screen.getAllByTestId("table-row")).toHaveLength(1))
    const create = screen.getByTestId("create-airport")
    expect(create).toBeDisabled()
    expect(create.closest("[data-testid=planned]")).toHaveAttribute("title", "Coming in a future sprint")
    expect(screen.getByTestId("actions-ap1")).toBeInTheDocument()
    expect(screen.getByTestId("list-actions")).toBeInTheDocument()
  })

  it("tasks (form wired): New opens the create dialog and POSTs", async () => {
    mockGet({ "/tasks?": page([]), "/admin/users/lookup": [] })
    const post = vi.spyOn(api, "post").mockResolvedValue({ id: "t9", title: "Chase deposit" })
    const user = userEvent.setup()
    renderWithProviders(<ResourceListPage resource={spec("tasks")} />, { route: "/tasks", path: "/tasks" })
    const empty = await screen.findByTestId("empty-state")
    expect(empty).toHaveTextContent("No tasks yet")
    await user.click(within(empty).getByTestId("create-task"))
    const dialog = await screen.findByTestId("task-form-dialog")
    await user.type(within(dialog).getByLabelText("Title"), "Chase deposit")
    await user.click(within(dialog).getByTestId("submit-button"))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    expect(post.mock.calls[0]![0]).toBe("/tasks")
    expect(post.mock.calls[0]![1]).toMatchObject({ title: "Chase deposit", status: "open", priority: "normal" })
  })

  it("row menu: View / Edit / Duplicate / Archive / Delete in order; Edit disabled where there is no form", async () => {
    mockGet({ "/crew?": page([{ id: "cm1", first_name: "Ava", last_name: "Pilot", primary_role: "pic", status: "active", medical_expiry: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }]) })
    const user = userEvent.setup()
    renderWithProviders(<ResourceListPage resource={spec("crew")} />, { route: "/crew", path: "/crew", user: { id: "o", client_id: "x", email: "o@d", full_name: "Owner", role: "owner", status: "active", timezone: null, permissions: ["crew.view", "crew.create", "crew.edit", "crew.delete"] } })
    await waitFor(() => expect(screen.getAllByTestId("table-row")).toHaveLength(1))
    await user.click(screen.getByTestId("actions-cm1"))
    const items = await screen.findAllByRole("menuitem")
    expect(items.map((i) => i.textContent?.replace(/Planned/g, "").trim())).toEqual(["View", "Edit", "Duplicate", "Archive (mark inactive)", "Delete"])
    expect(screen.getByTestId("menu-edit")).toHaveAttribute("aria-disabled", "true")
    expect(screen.getByTestId("menu-duplicate")).toHaveAttribute("aria-disabled", "true")
    expect(screen.getByTestId("menu-archive")).not.toHaveAttribute("aria-disabled")
    expect(screen.getByTestId("menu-delete")).not.toHaveAttribute("aria-disabled")
  })
})

describe("generic detail page", () => {
  it("shows Back, title, status, Edit / Delete / More; More has wired and planned items; Complete POSTs", async () => {
    mockGet({ "/tasks/t1": { id: "t1", title: "Send contract", status: "open", priority: "high", task_type: "follow_up", due_at: null, assigned_to_user_id: null, created_at: "2026-09-01T10:00:00Z", updated_at: "2026-09-02T10:00:00Z" }, "/graph/": { nodes: [], edges: [] } })
    const post = vi.spyOn(api, "post").mockResolvedValue({ id: "t1", status: "completed" })
    const user = userEvent.setup()
    renderWithProviders(<ResourceDetailPage resource={spec("tasks")} />, { route: "/tasks/t1", path: "/tasks/:id" })
    expect(await screen.findByRole("heading", { name: /Send contract/ })).toBeInTheDocument()
    expect(screen.getByTestId("back-link")).toBeInTheDocument()
    expect(screen.getByTestId("edit-task")).toBeEnabled()
    expect(screen.getByTestId("delete-task")).toBeEnabled()
    await user.click(screen.getByTestId("more-menu"))
    expect(await screen.findByTestId("more-complete")).not.toHaveAttribute("aria-disabled")
    await user.click(screen.getByTestId("more-complete"))
    const confirm = await screen.findByTestId("confirm-dialog")
    expect(confirm).toHaveTextContent('Complete "Send contract"?')
    await user.click(within(confirm).getByTestId("confirm-button"))
    await waitFor(() => expect(post).toHaveBeenCalledWith("/tasks/t1/complete", {}))
  })

  it("planned More items are disabled with the reason, and sections show '+ Add' wired or planned", async () => {
    mockGet({ "/trips/tr1": { id: "tr1", trip_number: "BLX-2026-009", status: "draft", trip_type: "charter", currency: "USD", total_sell_cents: 0, total_cost_cents: 0, pax_count: 2, created_at: "2026-09-01T10:00:00Z", updated_at: "2026-09-01T10:00:00Z" }, "/trips/tr1/legs": [], "/trips/tr1/quotes": [], "/graph/": { nodes: [], edges: [] } })
    const user = userEvent.setup()
    renderWithProviders(<ResourceDetailPage resource={spec("trips")} />, { route: "/trips/tr1", path: "/trips/:id", user: { id: "o", client_id: "x", email: "o@d", full_name: "Owner", role: "owner", status: "active", timezone: null, permissions: ["trips.view", "trips.edit", "trips.delete", "legs.view", "legs.create", "quotes.view", "quotes.create"] } })
    await screen.findByRole("heading", { name: /BLX-2026-009/ })
    const legs = await screen.findByTestId("section-legs")
    expect(legs).toHaveTextContent("No legs added to this trip yet.")
    expect(within(legs).getByRole("button", { name: /Add leg/ })).toBeDisabled()
    await user.click(screen.getByTestId("more-menu"))
    expect(await screen.findByTestId("more-generate-quote")).toHaveAttribute("aria-disabled", "true")
    expect(screen.getByTestId("more-generate-quote")).toHaveTextContent("Planned")
    expect(screen.getByTestId("more-advance")).not.toHaveAttribute("aria-disabled")
    expect(screen.getByTestId("more-advance")).toHaveTextContent("Advance status")
  })
})
