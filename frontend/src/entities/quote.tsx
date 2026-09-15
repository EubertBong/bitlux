import { CheckCircle2, FileDown, FileText, GitBranchPlus, Send, XCircle } from "lucide-react"
import { z } from "zod"
import { registerEntity, type FieldDef, type MoreAction, type SectionSpec } from "@/components/actions/registry"
import { useAccountHolderOptions, useAircraftOptions, useContactOptions, useOperatorOptions, useTripOptions } from "@/lib/lookups"
import { cents, CURRENCIES, currency, enumOptions, fromCents, isoOrNull, LINE_ITEM_TYPES, nul, numOrNull, optNum, optText, optUuid, reqText, toLocalInput } from "./_shared"

export const QUOTE_STATUSES = ["draft", "sent", "viewed", "negotiating", "accepted", "declined", "expired", "withdrawn", "superseded"] as const
const OPEN = new Set(["sent", "viewed", "negotiating"])

const schema = z.object({
  quote_number: z.string().trim().min(3, "Quote number is required").max(40),
  status: z.enum(QUOTE_STATUSES),
  trip_id: optUuid,
  contact_id: optUuid,
  account_holder_id: optUuid,
  operator_id: optUuid,
  aircraft_id: optUuid,
  currency,
  subtotal: optNum,
  tax: optNum,
  fees: optNum,
  discount: optNum,
  cost_total: optNum,
  valid_until: optText,
  terms: optText,
  customer_notes: optText,
  internal_notes: optText,
})
type V = z.infer<typeof schema>
const defaults: V = { quote_number: "", status: "draft", trip_id: "", contact_id: "", account_holder_id: "", operator_id: "", aircraft_id: "", currency: "USD", subtotal: NaN, tax: NaN, fees: NaN, discount: NaN, cost_total: NaN, valid_until: "", terms: "", customer_notes: "", internal_notes: "" }

const fields: FieldDef[] = [
  { name: "quote_number", label: "Quote number", placeholder: "Q-2026-0009", autoFocus: true },
  { name: "status", label: "Status", type: "select", allowEmpty: false, options: enumOptions(QUOTE_STATUSES) },
  { name: "trip_id", label: "Trip", type: "select", useOptions: useTripOptions, emptyLabel: "Speculative (no trip)" },
  { name: "contact_id", label: "Contact", type: "select", useOptions: useContactOptions, emptyLabel: "None" },
  { name: "account_holder_id", label: "Account holder", type: "select", useOptions: useAccountHolderOptions, emptyLabel: "None" },
  { name: "operator_id", label: "Operator", type: "select", useOptions: useOperatorOptions, emptyLabel: "TBD" },
  { name: "aircraft_id", label: "Aircraft", type: "select", useOptions: useAircraftOptions, emptyLabel: "TBD" },
  { name: "currency", label: "Currency", type: "select", allowEmpty: false, options: enumOptions(CURRENCIES) },
  { name: "subtotal", label: "Subtotal", type: "number" },
  { name: "tax", label: "Tax", type: "number" },
  { name: "fees", label: "Fees", type: "number" },
  { name: "discount", label: "Discount", type: "number" },
  { name: "cost_total", label: "Cost (internal)", type: "number" },
  { name: "valid_until", label: "Valid until", type: "datetime" },
  { name: "terms", label: "Terms", type: "textarea", span: 2 },
  { name: "customer_notes", label: "Notes to customer", type: "textarea", span: 2 },
  { name: "internal_notes", label: "Internal notes", type: "textarea", span: 2 },
]

type Row = { id: string } & Record<string, unknown>
const s = (v: unknown) => (typeof v === "string" ? v : "")
const n = (v: unknown) => (typeof v === "number" ? v : null)

function fromRecord(q: Row): V {
  return {
    quote_number: s(q.quote_number), status: (QUOTE_STATUSES as readonly string[]).includes(s(q.status)) ? (q.status as V["status"]) : "draft",
    trip_id: s(q.trip_id), contact_id: s(q.contact_id), account_holder_id: s(q.account_holder_id), operator_id: s(q.operator_id), aircraft_id: s(q.aircraft_id), currency: s(q.currency) || "USD",
    subtotal: fromCents(n(q.subtotal_cents)), tax: fromCents(n(q.tax_cents)), fees: fromCents(n(q.fees_cents)), discount: fromCents(n(q.discount_cents)), cost_total: fromCents(n(q.cost_total_cents)),
    valid_until: toLocalInput(s(q.valid_until)), terms: s(q.terms), customer_notes: s(q.customer_notes), internal_notes: s(q.internal_notes),
  }
}
function toPayload(v: V): Record<string, unknown> {
  const subtotal = cents(v.subtotal), tax = cents(v.tax), fees = cents(v.fees), discount = cents(v.discount)
  return {
    quote_number: v.quote_number.trim(), status: v.status, trip_id: nul(v.trip_id), contact_id: nul(v.contact_id), account_holder_id: nul(v.account_holder_id), operator_id: nul(v.operator_id), aircraft_id: nul(v.aircraft_id),
    currency: v.currency, subtotal_cents: subtotal, tax_cents: tax, fees_cents: fees, discount_cents: discount, total_cents: subtotal + tax + fees - discount, cost_total_cents: cents(v.cost_total),
    valid_until: isoOrNull(v.valid_until), terms: nul(v.terms), customer_notes: nul(v.customer_notes), internal_notes: nul(v.internal_notes),
  }
}

const lineSchema = z.object({ line_type: z.enum(LINE_ITEM_TYPES), description: reqText("Describe the line"), quantity: z.number().positive("Quantity must be positive"), unit: optText, unit_price: z.number().finite("Enter a price"), cost: optNum, is_taxable: z.boolean() })
const lineFields: FieldDef[] = [
  { name: "line_type", label: "Type", type: "select", allowEmpty: false, options: enumOptions(LINE_ITEM_TYPES) },
  { name: "description", label: "Description" },
  { name: "quantity", label: "Quantity", type: "number" },
  { name: "unit", label: "Unit", placeholder: "hour / leg / pax" },
  { name: "unit_price", label: "Unit price", type: "number" },
  { name: "cost", label: "Cost (internal)", type: "number" },
  { name: "is_taxable", label: "Taxable", type: "checkbox", span: 2 },
]
const lineDefaults = { line_type: "flight_hours", description: "", quantity: 1, unit: "hour", unit_price: NaN, cost: NaN, is_taxable: true }
const lineBody = (v: Record<string, unknown>, quoteId: string) => {
  const qty = Number(v.quantity), unit = cents(v.unit_price as number)
  return { quote_id: quoteId, line_type: v.line_type, description: String(v.description).trim(), quantity: qty, unit: nul(v.unit as string), unit_price_cents: unit, sell_cents: Math.round(unit * qty), cost_cents: cents(numOrNull(v.cost as number)), is_taxable: Boolean(v.is_taxable) }
}

const moreActions: MoreAction[] = [
  { key: "send", label: "Send", icon: Send, permission: "quotes.edit", kind: "patch", body: (row) => (row.status === "draft" ? { status: "sent", sent_at: new Date().toISOString() } : null), title: (r) => `Send ${s(r.quote_number)}?`, message: () => "Marks the quote as sent and stamps the time. Delivery itself (email/PDF) is not wired in this build.", success: "Quote marked sent" },
  { key: "revise", label: "Revise", icon: GitBranchPlus, permission: "quotes.edit", kind: "patch", post: (row) => `/quotes/${row.id}/supersede`, body: (row) => (row.is_current === false ? null : {}), title: (r) => `Create revision ${Number(r.revision ?? 1) + 1} of ${s(r.quote_number)}?`, message: () => "The current revision becomes superseded and its line items are copied to the new one.", success: "Revision created" },
  { key: "accept", label: "Accept", icon: CheckCircle2, permission: "quotes.edit", kind: "patch", body: (row) => (OPEN.has(s(row.status)) ? { status: "accepted", accepted_at: new Date().toISOString() } : null), title: (r) => `Accept ${s(r.quote_number)}?`, message: () => "Marks the quote accepted. Creating the booking from it arrives with the workflow sprint.", success: "Quote accepted" },
  { key: "decline", label: "Decline", icon: XCircle, permission: "quotes.edit", kind: "dialog", hidden: (row) => !OPEN.has(s(row.status)) && row.status !== "draft", title: "Decline quote", schema: z.object({ decline_reason: reqText("Give a reason") }), fields: [{ name: "decline_reason", label: "Reason", type: "textarea", span: 2, autoFocus: true }], defaults: () => ({ decline_reason: "" }), submit: (v, row) => ({ method: "patch", path: `/quotes/${row.id}`, body: { status: "declined", declined_at: new Date().toISOString(), decline_reason: String(v.decline_reason).trim() } }), success: "Quote declined" },
  { key: "pdf", label: "Download PDF", icon: FileDown, permission: "quotes.view", kind: "planned", reason: "PDF rendering is not in the API yet" },
]

const sections: SectionSpec[] = [
  { key: "line-items", title: "Line items", icon: FileText, list: (id) => `/quotes/${id}/line-items`, permission: "quotes.view", empty: "No line items yet.",
    columns: [{ key: "line_type", label: "Type", kind: "status" }, { key: "description", label: "Description" }, { key: "quantity", label: "Qty" }, { key: "unit_price_cents", label: "Unit price", kind: "money" }, { key: "sell_cents", label: "Sell", kind: "money" }, { key: "cost_cents", label: "Cost", kind: "money" }],
    add: { label: "Add line item", permission: "quotes.edit", schema: lineSchema, fields: lineFields, defaults: lineDefaults, body: lineBody, post: (id) => `/quotes/${id}/line-items`, success: "Line item added" } },
  { key: "revisions", title: "Revisions", icon: GitBranchPlus, list: (id) => `/quotes/${id}/revisions`, permission: "quotes.view", empty: "This is the only revision.",
    columns: [{ key: "quote_number", label: "Quote", kind: "link", to: (r) => `/quotes/${r.id}` }, { key: "revision", label: "Rev" }, { key: "status", label: "Status", kind: "status" }, { key: "total_cents", label: "Total", kind: "money" }, { key: "created_at", label: "Created", kind: "datetime" }] },
]

export const quoteEntity = registerEntity<Row, V>({
  kind: "quote", label: "Quote", plural: "Quotes", endpoint: "/quotes", path: "/quotes", queryKey: "quotes", permissionPrefix: "quotes", graphType: "quote", icon: FileText,
  statuses: QUOTE_STATUSES,
  nameOf: (q) => `${s(q.quote_number)} r${Number(q.revision ?? 1)}`,
  archive: { status: "withdrawn", label: "Archive (withdraw)" },
  form: { schema, fields, defaults, fromRecord, toPayload: (v) => toPayload(v), duplicate: (q) => ({ ...fromRecord(q), quote_number: `${s(q.quote_number)}-COPY`, status: "draft" }) },
  moreActions,
  sections,
  hideFields: ["parent_quote_id", "pdf_document_id", "esign_envelope_id", "first_viewed_at", "last_viewed_at", "view_count", "aircraft_model_id", "prepared_by_user_id"],
})
