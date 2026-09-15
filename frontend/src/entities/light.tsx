/**
 * Entities with pages but no create/edit form yet: the primitives render their
 * Edit / Duplicate / New disabled with the PLANNED hint, Delete works where the
 * API allows it, and the entity-specific "More" actions below are wired where a
 * route exists.
 */

import { Banknote, CalendarCheck, Factory, FileDown, FolderOpen, IdCard, Landmark, MapPin, ScrollText, Send, Shapes, Tags, UserCog, XCircle } from "lucide-react"
import { z } from "zod"
import { registerEntity, type MoreAction, type SectionSpec } from "@/components/actions/registry"
import { cents, enumOptions, LINE_ITEM_TYPES, nul, nowLocalInput, numOrNull, optText, reqNum, reqText } from "./_shared"

type Row = { id: string } & Record<string, unknown>
const s = (v: unknown) => (typeof v === "string" ? v : "")

registerEntity<Row, Record<string, unknown>>({ kind: "airport", label: "Airport", plural: "Airports", endpoint: "/airports", path: "/airports", queryKey: "airports", permissionPrefix: "airports", graphType: "airport", icon: MapPin, nameOf: (a) => `${s(a.icao_code) || s(a.iata_code)} ${s(a.name)}`.trim(), hideFields: ["location", "curfew"] })
registerEntity<Row, Record<string, unknown>>({ kind: "crew_member", label: "Crew member", plural: "Crew", endpoint: "/crew", path: "/crew", queryKey: "crew", permissionPrefix: "crew", graphType: "crew_member", icon: IdCard, statuses: ["active", "inactive", "training", "on_leave", "suspended", "terminated"], nameOf: (c) => `${s(c.first_name)} ${s(c.last_name)}`.trim(), archive: { status: "inactive", label: "Archive (mark inactive)" }, hideFields: ["license_number", "hours_on_type", "photo_document_id"] })
registerEntity<Row, Record<string, unknown>>({ kind: "booking", label: "Booking", plural: "Bookings", endpoint: "/bookings", path: "/bookings", queryKey: "bookings", permissionPrefix: "bookings", graphType: "booking", icon: CalendarCheck, statuses: ["pending", "confirmed", "contract_sent", "contract_signed", "funds_pending", "funds_received", "flown", "completed", "cancelled", "disputed"], nameOf: (b) => s(b.booking_number) || "Booking", hideFields: ["contract_document_id", "esign_envelope_id", "signed_by_contact_id"] })
registerEntity<Row, Record<string, unknown>>({ kind: "document", label: "Document", plural: "Documents", endpoint: "/documents", path: "/documents", queryKey: "documents", permissionPrefix: "documents", graphType: "document", icon: FolderOpen, statuses: ["pending", "under_review", "approved", "rejected", "expired", "superseded"], nameOf: (d) => s(d.title) || "Document", hideFields: ["ocr_text", "ocr_tsv", "bucket", "storage_key", "checksum_sha256", "metadata", "supersedes_document_id"] })
registerEntity<Row, Record<string, unknown>>({ kind: "account_holder", label: "Account holder", plural: "Account holders", endpoint: "/account_holders", path: "/account-holders", queryKey: "account_holders", permissionPrefix: "account_holders", graphType: "account_holder", icon: Landmark, statuses: ["pending", "active", "on_hold", "suspended", "closed"], nameOf: (a) => s(a.name) || "Account", archive: { status: "closed", label: "Archive (close)" }, hideFields: ["tax_id", "tax_id_last4", "billing_address_id"] })
registerEntity<Row, Record<string, unknown>>({ kind: "manufacturer", label: "Manufacturer", plural: "Manufacturers", endpoint: "/manufacturers", path: "/manufacturers", queryKey: "manufacturers", permissionPrefix: "manufacturers", graphType: "manufacturer", icon: Factory, nameOf: (m) => s(m.name) || "Manufacturer" })
registerEntity<Row, Record<string, unknown>>({ kind: "aircraft_model", label: "Aircraft model", plural: "Aircraft models", endpoint: "/aircraft_models", path: "/aircraft-models", queryKey: "aircraft_models", permissionPrefix: "aircraft_models", graphType: "aircraft_model", icon: Shapes, nameOf: (m) => s(m.name) || "Model" })
registerEntity<Row, Record<string, unknown>>({ kind: "segment", label: "Segment", plural: "Segments", endpoint: "/segments", path: "/segments", queryKey: "segments", permissionPrefix: "segments", graphType: "segment", icon: Tags, nameOf: (sg) => s(sg.name) || "Segment", hideFields: ["path", "criteria"] })
registerEntity<Row, Record<string, unknown>>({ kind: "user", label: "User", plural: "Users", endpoint: "/admin/users", path: "/admin/users", queryKey: "users", permissionPrefix: "users", graphType: "user", icon: UserCog, statuses: ["invited", "active", "disabled", "locked"], nameOf: (u) => s(u.full_name) || s(u.email), archive: { status: "disabled", label: "Archive (disable)" }, hideFields: ["password_hash", "auth_subject", "auth_provider"] })
registerEntity<Row, Record<string, unknown>>({ kind: "audit_log", label: "Audit event", plural: "Audit log", endpoint: "/admin/audit-log", path: "/admin/audit-log", queryKey: "audit", permissionPrefix: "audit", icon: ScrollText, readOnly: true, nameOf: (e) => `${s(e.action)} ${s(e.entity_type)} ${s(e.entity_label)}`.trim() })

// ---- Invoices: no form yet, but the finance actions the brief names exist as routes.
const PAYMENT_METHODS = ["wire", "ach", "sepa", "credit_card", "check", "jet_card_debit", "escrow", "crypto", "other"] as const
const paymentSchema = z.object({ amount: reqNum("Enter the amount").positive("Amount must be positive"), method: z.enum(PAYMENT_METHODS), received_at: z.string().min(1, "When was it received?"), reference: optText, notes: optText })
const lineSchema = z.object({ line_type: z.enum(LINE_ITEM_TYPES), description: reqText("Describe the line"), quantity: z.number().positive(), unit_price: z.number().finite("Enter a price"), is_taxable: z.boolean() })
const lineBody = (v: Record<string, unknown>, invoiceId: string) => { const qty = Number(v.quantity), unit = cents(v.unit_price as number); return { invoice_id: invoiceId, line_type: v.line_type, description: String(v.description).trim(), quantity: qty, unit_price_cents: unit, amount_cents: Math.round(unit * qty), is_taxable: Boolean(v.is_taxable) } }
const invoiceOpen = (row: Row) => ["draft", "issued", "sent", "partially_paid", "overdue"].includes(s(row.status))

const invoiceActions: MoreAction[] = [
  { key: "send", label: "Send", icon: Send, permission: "invoices.edit", kind: "patch", body: (row) => (row.status === "draft" || row.status === "issued" ? { status: "sent", sent_at: new Date().toISOString() } : null), title: (r) => `Send ${s(r.invoice_number)}?`, message: () => "Marks the invoice sent and stamps the time. Email delivery is not wired in this build.", success: "Invoice marked sent" },
  { key: "record-payment", label: "Record payment", icon: Banknote, permission: "payments.create", kind: "dialog", hidden: (row) => !invoiceOpen(row), title: "Record payment", schema: paymentSchema,
    fields: [{ name: "amount", label: "Amount", type: "number", autoFocus: true }, { name: "method", label: "Method", type: "select", allowEmpty: false, options: enumOptions(PAYMENT_METHODS, { ach: "ACH", sepa: "SEPA" }) }, { name: "received_at", label: "Received", type: "datetime" }, { name: "reference", label: "Reference", placeholder: "wire ref / cheque no." }, { name: "notes", label: "Notes", type: "textarea", span: 2 }],
    defaults: (row) => ({ amount: typeof row.balance_cents === "number" ? row.balance_cents / 100 : NaN, method: "wire", received_at: nowLocalInput(), reference: "", notes: "" }),
    submit: (v, row) => ({ method: "post", path: "/payments", body: { account_holder_id: row.account_holder_id, invoice_id: row.id, method: v.method, status: "cleared", amount_cents: cents(v.amount as number), currency: s(row.currency) || "USD", received_at: new Date(String(v.received_at)).toISOString(), cleared_at: new Date(String(v.received_at)).toISOString(), reference: nul(v.reference as string), notes: nul(v.notes as string) } }),
    success: "Payment recorded", refresh: ["payments"] },
  { key: "void", label: "Void", icon: XCircle, permission: "invoices.edit", kind: "dialog", hidden: (row) => !invoiceOpen(row), title: "Void invoice", schema: z.object({ void_reason: reqText("Give a reason") }), fields: [{ name: "void_reason", label: "Reason", type: "textarea", span: 2, autoFocus: true }], defaults: () => ({ void_reason: "" }), submit: (v, row) => ({ method: "patch", path: `/invoices/${row.id}`, body: { status: "void", voided_at: new Date().toISOString(), void_reason: String(v.void_reason).trim() } }), success: "Invoice voided" },
  { key: "pdf", label: "Download PDF", icon: FileDown, permission: "invoices.view", kind: "planned", reason: "PDF rendering is not in the API yet" },
]
const invoiceSections: SectionSpec[] = [
  { key: "line-items", title: "Line items", list: (id) => `/invoices/${id}/line-items`, permission: "invoices.view", empty: "No line items yet.",
    columns: [{ key: "line_type", label: "Type", kind: "status" }, { key: "description", label: "Description" }, { key: "quantity", label: "Qty" }, { key: "unit_price_cents", label: "Unit price", kind: "money" }, { key: "amount_cents", label: "Amount", kind: "money" }, { key: "tax_cents", label: "Tax", kind: "money" }],
    add: { label: "Add line item", permission: "invoices.edit", schema: lineSchema, fields: [{ name: "line_type", label: "Type", type: "select", allowEmpty: false, options: enumOptions(LINE_ITEM_TYPES) }, { name: "description", label: "Description" }, { name: "quantity", label: "Quantity", type: "number" }, { name: "unit_price", label: "Unit price", type: "number" }, { name: "is_taxable", label: "Taxable", type: "checkbox", span: 2 }], defaults: { line_type: "flight_hours", description: "", quantity: 1, unit_price: NaN, is_taxable: true }, body: lineBody, post: (id) => `/invoices/${id}/line-items`, success: "Line item added" } },
  { key: "payments", title: "Payments", icon: Banknote, list: (id) => `/invoices/${id}/payments`, permission: "payments.view", empty: "No payments received yet.",
    columns: [{ key: "received_at", label: "Received", kind: "datetime" }, { key: "method", label: "Method", kind: "status" }, { key: "amount_cents", label: "Amount", kind: "money" }, { key: "status", label: "Status", kind: "status" }, { key: "reference", label: "Reference" }] },
]
registerEntity<Row, Record<string, unknown>>({ kind: "invoice", label: "Invoice", plural: "Invoices", endpoint: "/invoices", path: "/invoices", queryKey: "invoices", permissionPrefix: "invoices", graphType: "invoice", icon: ScrollText, statuses: ["draft", "issued", "sent", "partially_paid", "paid", "overdue", "void", "refunded", "written_off"], nameOf: (i) => s(i.invoice_number) || "Invoice", moreActions: invoiceActions, sections: invoiceSections, hideFields: ["pdf_document_id", "billing_address_id", "parent_invoice_id", "external_ref", "exchange_rate"] })

export const _lightEntitiesRegistered = true
void numOrNull
