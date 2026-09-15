import { ChevronsRight, FilePlus2, Route, UserPlus, Waypoints } from "lucide-react"
import { z } from "zod"
import { registerEntity, type FieldDef, type MoreAction, type SectionSpec } from "@/components/actions/registry"
import { useAccountHolderOptions, useContactOptions, useUserOptions } from "@/lib/lookups"
import type { Trip } from "@/lib/types"
import { cents, CURRENCIES, currency, dateOrNull, enumOptions, fromCents, intOrNull, nul, numOr, optDate, optNum, optText, optUuid, toDateInput } from "./_shared"
import { LEAD_SOURCES } from "./contact"

export const TRIP_STATUSES = ["draft", "sourcing", "quoted", "confirmed", "in_progress", "completed", "cancelled", "archived"] as const
export const TRIP_TYPES = ["charter", "owner_flight", "empty_reposition", "demo", "maintenance_ferry", "air_ambulance", "cargo", "group"] as const
/** The pipeline "Advance status" walks. */
export const TRIP_PIPELINE = ["draft", "sourcing", "quoted", "confirmed", "in_progress", "completed"] as const

const schema = z.object({
  trip_number: z.string().trim().min(3, "Trip number is required").max(40),
  trip_type: z.enum(TRIP_TYPES),
  status: z.enum(TRIP_STATUSES),
  primary_contact_id: optUuid,
  account_holder_id: optUuid,
  owner_user_id: optUuid,
  source: z.enum(LEAD_SOURCES),
  pax_count: optNum,
  departure_date: optDate,
  return_date: optDate,
  currency,
  total_sell: optNum,
  total_cost: optNum,
  special_requests: optText,
  internal_notes: optText,
}).superRefine((v, ctx) => {
  if (v.departure_date && v.return_date && v.return_date < v.departure_date) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["return_date"], message: "Return cannot be before departure" })
})
type V = z.infer<typeof schema>

const defaults: V = { trip_number: "", trip_type: "charter", status: "draft", primary_contact_id: "", account_holder_id: "", owner_user_id: "", source: "other", pax_count: NaN, departure_date: "", return_date: "", currency: "USD", total_sell: NaN, total_cost: NaN, special_requests: "", internal_notes: "" }

const fields: FieldDef[] = [
  { name: "trip_number", label: "Trip number", placeholder: "BLX-2026-0007", autoFocus: true },
  { name: "trip_type", label: "Type", type: "select", allowEmpty: false, options: enumOptions(TRIP_TYPES) },
  { name: "status", label: "Status", type: "select", allowEmpty: false, options: enumOptions(TRIP_STATUSES) },
  { name: "source", label: "Source", type: "select", allowEmpty: false, options: enumOptions(LEAD_SOURCES) },
  { name: "primary_contact_id", label: "Primary contact", type: "select", useOptions: useContactOptions, emptyLabel: "None yet" },
  { name: "account_holder_id", label: "Account holder (payer)", type: "select", useOptions: useAccountHolderOptions, emptyLabel: "Not yet booked" },
  { name: "owner_user_id", label: "Broker", type: "select", useOptions: useUserOptions, emptyLabel: "Unassigned" },
  { name: "pax_count", label: "Passengers", type: "number" },
  { name: "departure_date", label: "Departure date", type: "date" },
  { name: "return_date", label: "Return date", type: "date" },
  { name: "currency", label: "Currency", type: "select", allowEmpty: false, options: enumOptions(CURRENCIES) },
  { name: "total_sell", label: "Sell price", type: "number", description: "Major units, e.g. 44190.00" },
  { name: "total_cost", label: "Cost", type: "number" },
  { name: "special_requests", label: "Special requests", type: "textarea", span: 2 },
  { name: "internal_notes", label: "Internal notes", type: "textarea", span: 2 },
]

type TripRow = Trip & Record<string, unknown>

function fromRecord(t: TripRow): V {
  return {
    trip_number: t.trip_number, trip_type: (TRIP_TYPES as readonly string[]).includes(t.trip_type) ? (t.trip_type as V["trip_type"]) : "charter",
    status: (TRIP_STATUSES as readonly string[]).includes(t.status) ? (t.status as V["status"]) : "draft",
    primary_contact_id: t.primary_contact_id ?? "", account_holder_id: t.account_holder_id ?? "", owner_user_id: (t.owner_user_id as string | null) ?? "",
    source: (LEAD_SOURCES as readonly string[]).includes(String(t.source)) ? (t.source as V["source"]) : "other",
    pax_count: numOr(t.pax_count), departure_date: toDateInput(t.departure_date), return_date: toDateInput(t.return_date), currency: t.currency,
    total_sell: fromCents(t.total_sell_cents), total_cost: fromCents(t.total_cost_cents), special_requests: (t.special_requests as string | null) ?? "", internal_notes: (t.internal_notes as string | null) ?? "",
  }
}

function toPayload(v: V): Record<string, unknown> {
  return {
    trip_number: v.trip_number.trim(), trip_type: v.trip_type, status: v.status, source: v.source,
    primary_contact_id: nul(v.primary_contact_id), account_holder_id: nul(v.account_holder_id), owner_user_id: nul(v.owner_user_id),
    pax_count: intOrNull(v.pax_count) ?? 0, departure_date: dateOrNull(v.departure_date), return_date: dateOrNull(v.return_date), currency: v.currency,
    total_sell_cents: cents(v.total_sell), total_cost_cents: cents(v.total_cost), special_requests: nul(v.special_requests), internal_notes: nul(v.internal_notes),
  }
}

export function nextTripStatus(status: string): string | null {
  const i = TRIP_PIPELINE.indexOf(status as (typeof TRIP_PIPELINE)[number])
  return i >= 0 && i < TRIP_PIPELINE.length - 1 ? TRIP_PIPELINE[i + 1]! : null
}

const moreActions: MoreAction[] = [
  { key: "add-leg", label: "Add leg", icon: Waypoints, permission: "legs.create", kind: "planned", reason: "Leg builder (airports, times, aircraft) arrives with the trip workflow sprint" },
  { key: "add-passenger", label: "Add passenger", icon: UserPlus, permission: "trips.edit", kind: "planned", reason: "Manifest picker arrives with the trip workflow sprint" },
  { key: "generate-quote", label: "Generate quote", icon: FilePlus2, permission: "quotes.create", kind: "planned", reason: "Quote-from-trip endpoint is not in the API yet" },
  { key: "advance", label: "Advance status", icon: ChevronsRight, permission: "trips.edit", kind: "patch",
    body: (row) => { const next = nextTripStatus(String(row.status)); return next ? { status: next } : null },
    title: (row) => `Move ${row.trip_number} to ${nextTripStatus(String(row.status))?.replace("_", " ")}?`,
    message: (row) => `Status goes from ${String(row.status).replace("_", " ")} to ${nextTripStatus(String(row.status))?.replace("_", " ")}. The change is audited and the pipeline board updates.`,
    success: "Trip advanced" },
]

const sections: SectionSpec[] = [
  { key: "legs", title: "Legs", icon: Waypoints, list: (id) => `/trips/${id}/legs`, permission: "legs.view", empty: "No legs added to this trip yet.",
    columns: [{ key: "leg_number", label: "#" }, { key: "scheduled_departure_at", label: "Departure", kind: "datetime" }, { key: "scheduled_arrival_at", label: "Arrival", kind: "datetime" }, { key: "status", label: "Status", kind: "status" }, { key: "pax_count", label: "Pax" }, { key: "sell_cents", label: "Sell", kind: "money" }],
    add: { label: "Add leg", permission: "legs.create", planned: true } },
  { key: "quotes", title: "Quotes", icon: FilePlus2, list: (id) => `/trips/${id}/quotes`, permission: "quotes.view", empty: "No quotes for this trip yet.",
    columns: [{ key: "quote_number", label: "Quote", kind: "link", to: (r) => `/quotes/${r.id}` }, { key: "revision", label: "Rev" }, { key: "status", label: "Status", kind: "status" }, { key: "total_cents", label: "Total", kind: "money" }, { key: "valid_until", label: "Valid until", kind: "date" }],
    add: { label: "Add quote", permission: "quotes.create", planned: true } },
]

export const tripEntity = registerEntity<TripRow, V>({
  kind: "trip", label: "Trip", plural: "Trips", endpoint: "/trips", path: "/trips", queryKey: "trips", permissionPrefix: "trips", graphType: "trip", icon: Route,
  statuses: TRIP_STATUSES,
  nameOf: (t) => t.trip_number,
  archive: { status: "archived" },
  form: { schema, fields, defaults, fromRecord, toPayload: (v) => toPayload(v), duplicate: (t) => ({ ...fromRecord(t), trip_number: `${t.trip_number}-COPY`, status: "draft" }) },
  moreActions,
  sections,
  hideFields: ["accepted_quote_id", "booking_id", "source_empty_leg_id", "lead_passenger_id", "ops_user_id", "cancelled_at", "cancellation_reason", "leg_count"],
})
