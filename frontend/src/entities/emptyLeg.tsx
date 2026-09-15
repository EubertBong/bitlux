import { CalendarX2, Megaphone, PauseCircle, PlaneTakeoff, Ticket } from "lucide-react"
import { z } from "zod"
import { registerEntity, type FieldDef, type MoreAction } from "@/components/actions/registry"
import { useAircraftOptions, useAirportOptions, useOperatorOptions } from "@/lib/lookups"
import { fmtDate } from "@/lib/format"
import { cents, CURRENCIES, currency, enumOptions, fromCents, intOrNull, isoOrNull, nul, numOr, optNum, optText, optUuid, reqNum, toCents, toLocalInput } from "./_shared"

export const EMPTY_LEG_STATUSES = ["draft", "available", "on_hold", "booked", "expired", "cancelled"] as const
const SOURCES = ["manual", "operator_feed", "avinode", "email_parse", "api_partner"] as const

const schema = z.object({
  operator_id: z.string().min(1, "Choose the operator"),
  aircraft_id: optUuid,
  departure_airport_id: z.string().min(1, "Choose the departure airport"),
  arrival_airport_id: z.string().min(1, "Choose the arrival airport"),
  earliest_departure_at: z.string().min(1, "Earliest departure is required"),
  latest_departure_at: z.string().min(1, "Latest departure is required"),
  seats_available: optNum,
  asking_price: reqNum("Asking price is required").positive("Asking price must be positive"),
  floor_price: optNum,
  currency,
  status: z.enum(EMPTY_LEG_STATUSES),
  source: z.enum(SOURCES),
  is_flexible_routing: z.boolean(),
  routing_radius_nm: optNum,
  expires_at: optText,
  notes: optText,
}).superRefine((v, ctx) => {
  if (v.earliest_departure_at && v.latest_departure_at && v.latest_departure_at < v.earliest_departure_at) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["latest_departure_at"], message: "Latest cannot be before earliest" })
  if (v.departure_airport_id && v.departure_airport_id === v.arrival_airport_id) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["arrival_airport_id"], message: "Arrival must differ from departure" })
})
type V = z.infer<typeof schema>
const defaults: V = { operator_id: "", aircraft_id: "", departure_airport_id: "", arrival_airport_id: "", earliest_departure_at: "", latest_departure_at: "", seats_available: NaN, asking_price: NaN, floor_price: NaN, currency: "USD", status: "draft", source: "manual", is_flexible_routing: false, routing_radius_nm: NaN, expires_at: "", notes: "" }

const fields: FieldDef[] = [
  { name: "operator_id", label: "Operator", type: "select", useOptions: useOperatorOptions, allowEmpty: false },
  { name: "aircraft_id", label: "Aircraft", type: "select", useOptions: useAircraftOptions, emptyLabel: "Type only / TBD" },
  { name: "departure_airport_id", label: "From", type: "select", useOptions: useAirportOptions, allowEmpty: false },
  { name: "arrival_airport_id", label: "To", type: "select", useOptions: useAirportOptions, allowEmpty: false },
  { name: "earliest_departure_at", label: "Earliest departure", type: "datetime" },
  { name: "latest_departure_at", label: "Latest departure", type: "datetime" },
  { name: "asking_price", label: "Asking price", type: "number" },
  { name: "floor_price", label: "Floor price (internal)", type: "number" },
  { name: "currency", label: "Currency", type: "select", allowEmpty: false, options: enumOptions(CURRENCIES) },
  { name: "seats_available", label: "Seats", type: "number" },
  { name: "status", label: "Status", type: "select", allowEmpty: false, options: enumOptions(EMPTY_LEG_STATUSES) },
  { name: "source", label: "Source", type: "select", allowEmpty: false, options: enumOptions(SOURCES) },
  { name: "is_flexible_routing", label: "Flexible routing", type: "checkbox" },
  { name: "routing_radius_nm", label: "Routing radius (nm)", type: "number", when: (v) => Boolean(v.is_flexible_routing) },
  { name: "expires_at", label: "Offer expires", type: "datetime" },
  { name: "notes", label: "Notes", type: "textarea", span: 2 },
]

type Row = { id: string } & Record<string, unknown>
const s = (v: unknown) => (typeof v === "string" ? v : "")
const n = (v: unknown) => (typeof v === "number" ? v : null)

function fromRecord(e: Row): V {
  return {
    operator_id: s(e.operator_id), aircraft_id: s(e.aircraft_id), departure_airport_id: s(e.departure_airport_id), arrival_airport_id: s(e.arrival_airport_id),
    earliest_departure_at: toLocalInput(s(e.earliest_departure_at)), latest_departure_at: toLocalInput(s(e.latest_departure_at)), seats_available: numOr(n(e.seats_available)),
    asking_price: fromCents(n(e.asking_price_cents)), floor_price: fromCents(n(e.floor_price_cents)), currency: s(e.currency) || "USD",
    status: (EMPTY_LEG_STATUSES as readonly string[]).includes(s(e.status)) ? (e.status as V["status"]) : "draft", source: (SOURCES as readonly string[]).includes(s(e.source)) ? (e.source as V["source"]) : "manual",
    is_flexible_routing: Boolean(e.is_flexible_routing), routing_radius_nm: numOr(n(e.routing_radius_nm)), expires_at: toLocalInput(s(e.expires_at)), notes: s(e.notes),
  }
}
function toPayload(v: V): Record<string, unknown> {
  return {
    operator_id: v.operator_id, aircraft_id: nul(v.aircraft_id), departure_airport_id: v.departure_airport_id, arrival_airport_id: v.arrival_airport_id,
    earliest_departure_at: isoOrNull(v.earliest_departure_at), latest_departure_at: isoOrNull(v.latest_departure_at), seats_available: intOrNull(v.seats_available),
    asking_price_cents: cents(v.asking_price), floor_price_cents: toCents(v.floor_price), currency: v.currency, status: v.status, source: v.source,
    is_flexible_routing: v.is_flexible_routing, routing_radius_nm: v.is_flexible_routing ? intOrNull(v.routing_radius_nm) : null, expires_at: isoOrNull(v.expires_at), notes: nul(v.notes),
  }
}

const moreActions: MoreAction[] = [
  { key: "publish", label: "Publish", icon: Megaphone, permission: "empty_legs.edit", kind: "patch", body: (row) => (row.status === "draft" || row.status === "on_hold" ? { status: "available", published_at: new Date().toISOString() } : null), title: () => "Publish this empty leg?", message: () => "It becomes available to book and shows up in empty-leg search.", success: "Empty leg published" },
  { key: "hold", label: "Hold", icon: PauseCircle, permission: "empty_legs.edit", kind: "patch", body: (row) => (row.status === "available" ? { status: "on_hold" } : null), title: () => "Put this empty leg on hold?", message: () => "It stays visible internally but cannot be booked until republished.", success: "Empty leg on hold" },
  { key: "expire", label: "Expire", icon: CalendarX2, permission: "empty_legs.edit", kind: "patch", body: (row) => (row.status === "available" || row.status === "on_hold" ? { status: "expired", expires_at: new Date().toISOString() } : null), title: () => "Expire this empty leg?", message: () => "Marks the offer expired as of now.", destructive: true, success: "Empty leg expired" },
  { key: "book", label: "Book", icon: Ticket, permission: "trips.create", kind: "planned", reason: "Booking an empty leg into a trip arrives with the trip workflow sprint" },
]

export const emptyLegEntity = registerEntity<Row, V>({
  kind: "empty_leg", label: "Empty leg", plural: "Empty legs", endpoint: "/empty_legs", path: "/empty-legs", queryKey: "empty_legs", permissionPrefix: "empty_legs", graphType: "empty_leg", icon: PlaneTakeoff,
  statuses: EMPTY_LEG_STATUSES,
  nameOf: (e) => `Empty leg · ${fmtDate(s(e.earliest_departure_at))}`,
  archive: { status: "cancelled", label: "Archive (cancel)" },
  form: { schema, fields, defaults, fromRecord, toPayload: (v) => toPayload(v), duplicate: (e) => ({ ...fromRecord(e), status: "draft" }) },
  moreActions,
  hideFields: ["source_leg_id", "booked_trip_id", "external_ref", "published_at"],
})
