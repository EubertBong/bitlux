import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { toast } from "sonner"
import { describe, expect, it, vi } from "vitest"
import { api, ApiError } from "@/lib/api"
import type { Contact } from "@/lib/types"
import { renderWithProviders } from "@/test/utils"
import { ContactDetailPage } from "../ContactDetailPage"
import { ContactListPage } from "../ContactListPage"

function contact(i: number, over: Partial<Contact> = {}): Contact {
  return {
    id: `contact-${i}`, segment_id: null, contact_type: "individual", status: "active", first_name: "Person", last_name: `Number${i}`,
    display_name: `Person Number${i}`, company_name: "Acme Air", job_title: "Owner", owner_user_id: "u-owner", primary_email: `p${i}@x.test`, primary_phone: null,
    lifetime_value_cents: 0, trip_count: 0, last_activity_at: null, source: "referral", do_not_contact: false, preferences: {},
    created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", ...over,
  }
}
const page = <T,>(items: T[], total = items.length) => ({ items, total, page: 1, page_size: 25 })

function mockGet(overrides: Record<string, unknown> = {}) {
  return vi.spyOn(api, "get").mockImplementation(async (path: string) => {
    const key = Object.keys(overrides).find((k) => path.startsWith(k))
    if (key) return overrides[key]
    if (path.startsWith("/contacts?")) return page(Array.from({ length: 3 }, (_, i) => contact(i + 1)))
    if (/^\/contacts\/contact-\d+\/channels/.test(path)) return []
    if (/^\/contacts\/contact-\d+\/activities/.test(path)) return []
    if (/^\/contacts\/contact-\d+\/passengers/.test(path)) return []
    if (/^\/contacts\/contact-\d+$/.test(path)) return contact(1)
    if (path.startsWith("/admin/users/lookup")) return [{ id: "u-owner", full_name: "Olivia Grant", role: "owner" }]
    if (path.startsWith("/segments")) return page([{ id: "s1", name: "UHNW", code: "UHNW", segment_type: "uhnw" }])
    if (path.startsWith("/documents/for/")) return []
    if (path.startsWith("/graph/")) return { nodes: [], edges: [] }
    return page([])
  })
}

describe("ContactListPage", () => {
  it("renders rows with owner and segment resolved, and the New Contact button", async () => {
    mockGet()
    renderWithProviders(<ContactListPage />, { route: "/contacts", path: "/contacts" })
    await waitFor(() => expect(screen.getAllByTestId("table-row")).toHaveLength(3))
    expect(screen.getByText("Person Number1")).toBeInTheDocument()
    expect(screen.getAllByText("Olivia Grant").length).toBeGreaterThan(0)
    expect(screen.getByRole("button", { name: /New Contact/ })).toBeInTheDocument()
  })

  it("shows the first-run empty state when the book is empty and no filter is set", async () => {
    mockGet({ "/contacts?": page([], 0) })
    renderWithProviders(<ContactListPage />, { route: "/contacts", path: "/contacts" })
    const empty = await screen.findByTestId("empty-state")
    expect(empty).toHaveTextContent("No contacts yet")
    expect(within(empty).getByRole("button", { name: /New Contact/ })).toBeInTheDocument()
  })

  it("passes search and filters to the API as q= and equality params", async () => {
    const get = mockGet()
    const user = userEvent.setup()
    renderWithProviders(<ContactListPage />, { route: "/contacts?status=active", path: "/contacts" })
    await waitFor(() => expect(screen.getAllByTestId("table-row")).toHaveLength(3))
    await user.type(screen.getByLabelText("Search contacts"), "gulf")
    await waitFor(() => expect(get.mock.calls.some(([p]) => String(p).includes("q=gulf") && String(p).includes("status=active"))).toBe(true))
  })

  it("creates a contact from the dialog: derived display_name, success toast, list refresh", async () => {
    mockGet()
    const post = vi.spyOn(api, "post").mockResolvedValue(contact(9, { display_name: "Ada Lovelace", first_name: "Ada", last_name: "Lovelace" }))
    const success = vi.spyOn(toast, "success")
    const user = userEvent.setup()
    renderWithProviders(<ContactListPage />, { route: "/contacts", path: "/contacts" })
    await user.click(await screen.findByRole("button", { name: /New Contact/ }))
    const dialog = await screen.findByTestId("contact-form-dialog")
    await user.type(within(dialog).getByLabelText("First name"), "Ada")
    await user.type(within(dialog).getByLabelText("Last name"), "Lovelace")
    await user.type(within(dialog).getByLabelText("Email"), "ada@example.com")
    await user.click(within(dialog).getByTestId("submit-button"))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    const [path, body] = post.mock.calls[0]!
    expect(path).toBe("/contacts")
    expect(body).toMatchObject({ contact_type: "individual", display_name: "Ada Lovelace", first_name: "Ada", last_name: "Lovelace", primary_email: "ada@example.com", status: "lead" })
    expect(success).toHaveBeenCalledWith("Contact created", expect.objectContaining({ description: "Ada Lovelace" }))
    await waitFor(() => expect(screen.queryByTestId("contact-form-dialog")).not.toBeInTheDocument())
  })

  it("validates client-side and maps a server 422 onto the field", async () => {
    mockGet()
    const post = vi.spyOn(api, "post").mockRejectedValue(new ApiError(422, "validation_error", "Request validation failed", { errors: [{ loc: ["body", "primary_email"], msg: "value is not a valid email address", type: "value_error" }] }))
    const user = userEvent.setup()
    renderWithProviders(<ContactListPage />, { route: "/contacts", path: "/contacts" })
    await user.click(await screen.findByRole("button", { name: /New Contact/ }))
    const dialog = await screen.findByTestId("contact-form-dialog")
    // Zod first: a person needs a last name.
    await user.click(within(dialog).getByTestId("submit-button"))
    expect(await within(dialog).findByTestId("error-last_name")).toHaveTextContent("Last name is required")
    expect(post).not.toHaveBeenCalled()
    // Then the server's answer lands on the right field.
    await user.type(within(dialog).getByLabelText("Last name"), "Byron")
    await user.type(within(dialog).getByLabelText("Email"), "not-an-email@x.test")
    await user.click(within(dialog).getByTestId("submit-button"))
    expect(await within(dialog).findByTestId("error-primary_email")).toHaveTextContent("not a valid email address")
  })

  it("row ⋯ menu: Delete asks for confirmation, soft-deletes, and offers Undo", async () => {
    mockGet()
    const del = vi.spyOn(api, "delete").mockResolvedValue(undefined)
    const success = vi.spyOn(toast, "success")
    const user = userEvent.setup()
    renderWithProviders(<ContactListPage />, { route: "/contacts", path: "/contacts" })
    await waitFor(() => expect(screen.getAllByTestId("table-row")).toHaveLength(3))
    await user.click(screen.getByTestId("actions-contact-2"))
    await user.click(await screen.findByRole("menuitem", { name: /Delete/ }))
    const confirm = await screen.findByTestId("confirm-dialog")
    expect(confirm).toHaveTextContent("Delete Person Number2?")
    await user.click(within(confirm).getByTestId("confirm-button"))
    await waitFor(() => expect(del).toHaveBeenCalledWith("/contacts/contact-2"))
    expect(success).toHaveBeenCalledWith("Contact deleted", expect.objectContaining({ description: "Person Number2", action: expect.objectContaining({ label: "Undo" }) }))
  })

  it("row ⋯ menu: Edit opens the form pre-filled and PATCHes only the mapped payload", async () => {
    mockGet()
    const patch = vi.spyOn(api, "patch").mockResolvedValue(contact(1, { job_title: "Chairman" }))
    const user = userEvent.setup()
    renderWithProviders(<ContactListPage />, { route: "/contacts", path: "/contacts" })
    await waitFor(() => expect(screen.getAllByTestId("table-row")).toHaveLength(3))
    await user.click(screen.getByTestId("actions-contact-1"))
    await user.click(await screen.findByRole("menuitem", { name: /Edit/ }))
    const dialog = await screen.findByTestId("contact-form-dialog")
    const title = await within(dialog).findByLabelText("Job title")
    await waitFor(() => expect(title).toHaveValue("Owner"))
    await user.clear(title)
    await user.type(title, "Chairman")
    await user.click(within(dialog).getByTestId("submit-button"))
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1))
    expect(patch.mock.calls[0]![0]).toBe("/contacts/contact-1")
    expect(patch.mock.calls[0]![1]).toMatchObject({ job_title: "Chairman", display_name: "Person Number1" })
  })
})

describe("ContactDetailPage", () => {
  it("renders header, tabs and the log-activity buttons; Delete confirms and calls the API", async () => {
    mockGet()
    const del = vi.spyOn(api, "delete").mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderWithProviders(<ContactDetailPage />, { route: "/contacts/contact-1", path: "/contacts/:id" })
    expect(await screen.findByRole("heading", { name: /Person Number1/ })).toBeInTheDocument()
    for (const t of ["overview", "passengers", "documents", "activities", "relationship"]) expect(screen.getByTestId(`tab-${t}`)).toBeInTheDocument()
    expect(screen.getByTestId("log-call")).toBeInTheDocument()
    expect(screen.getByTestId("edit-contact")).toBeInTheDocument()
    await user.click(screen.getByTestId("delete-contact"))
    await user.click(within(await screen.findByTestId("confirm-dialog")).getByTestId("confirm-button"))
    await waitFor(() => expect(del).toHaveBeenCalledWith("/contacts/contact-1"))
  })

  it("logs a call: POSTs an activity bound to the contact and the current user", async () => {
    mockGet()
    const post = vi.spyOn(api, "post").mockResolvedValue({ id: "a-new" })
    const user = userEvent.setup()
    renderWithProviders(<ContactDetailPage />, { route: "/contacts/contact-1?tab=activities", path: "/contacts/:id" })
    await screen.findByRole("heading", { name: /Person Number1/ })
    await user.click(screen.getAllByTestId("log-call")[0]!)
    const dialog = await screen.findByTestId("log-activity-dialog")
    await user.type(within(dialog).getByLabelText("Subject"), "Intro call about Q4 travel")
    await user.click(within(dialog).getByTestId("submit-button"))
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
    const [path, body] = post.mock.calls[0]!
    expect(path).toBe("/activities")
    expect(body).toMatchObject({ activity_type: "call", direction: "outbound", subject: "Intro call about Q4 travel", contact_id: "contact-1", user_id: "14b66518-1136-52cc-9474-7f3adfefc800" })
    expect(typeof (body as { occurred_at: string }).occurred_at).toBe("string")
  })

  it("hides Edit/Delete/Log buttons for a read-only role", async () => {
    mockGet()
    renderWithProviders(<ContactDetailPage />, { route: "/contacts/contact-1", path: "/contacts/:id", user: { id: "ro", client_id: "x", email: "ro@demo.test", full_name: "Read Only", role: "read_only", status: "active", timezone: null, permissions: ["contacts.view", "activities.view"] } })
    await screen.findByRole("heading", { name: /Person Number1/ })
    expect(screen.queryByTestId("edit-contact")).not.toBeInTheDocument()
    expect(screen.queryByTestId("delete-contact")).not.toBeInTheDocument()
    expect(screen.queryByTestId("log-call")).not.toBeInTheDocument()
  })
})
