import { Building, Plane, RefreshCw, Upload } from "lucide-react"
import { z } from "zod"
import { registerEntity, type FieldDef, type MoreAction, type SectionSpec } from "@/components/actions/registry"
import { useAircraftModelOptions, useAirportOptions, useOperatorOptions } from "@/lib/lookups"
import { enumOptions, fromCents, intOrNull, nul, numOr, optNum, optText, optUuid, toCents, upperOrNull } from "./_shared"

export const AIRCRAFT_STATUSES = ["active", "maintenance", "aog", "stored", "for_sale", "sold", "retired"] as const

const schema = z.object({
  tail_number: z.string().trim().min(2, "Tail number is required").max(12),
  aircraft_model_id: z.string().min(1, "Choose a model"),
  operator_id: optUuid,
  status: z.enum(AIRCRAFT_STATUSES),
  year_of_manufacture: optNum,
  registration_country: z.string().trim().max(2).optional().or(z.literal("")),
  home_base_airport_id: optUuid,
  max_passengers: optNum,
  configured_seats: optNum,
  wifi_provider: optText,
  pets_allowed: z.boolean(),
  hourly_rate: optNum,
  is_available_for_charter: z.boolean(),
  notes: optText,
})
type V = z.infer<typeof schema>
const defaults: V = { tail_number: "", aircraft_model_id: "", operator_id: "", status: "active", year_of_manufacture: NaN, registration_country: "", home_base_airport_id: "", max_passengers: NaN, configured_seats: NaN, wifi_provider: "", pets_allowed: false, hourly_rate: NaN, is_available_for_charter: true, notes: "" }

const fields: FieldDef[] = [
  { name: "tail_number", label: "Tail number", placeholder: "N650BX", autoFocus: true },
  { name: "aircraft_model_id", label: "Model", type: "select", useOptions: useAircraftModelOptions, allowEmpty: false },
  { name: "operator_id", label: "Operator", type: "select", useOptions: useOperatorOptions, emptyLabel: "Unassigned" },
  { name: "status", label: "Status", type: "select", allowEmpty: false, options: enumOptions(AIRCRAFT_STATUSES, { aog: "AOG" }) },
  { name: "home_base_airport_id", label: "Home base", type: "select", useOptions: useAirportOptions, emptyLabel: "Unknown" },
  { name: "registration_country", label: "Registration country (ISO-2)", placeholder: "US" },
  { name: "year_of_manufacture", label: "Year of manufacture", type: "number" },
  { name: "max_passengers", label: "Max passengers", type: "number" },
  { name: "configured_seats", label: "Configured seats", type: "number" },
  { name: "hourly_rate", label: "Hourly rate (USD)", type: "number" },
  { name: "wifi_provider", label: "Wi-Fi", placeholder: "Starlink" },
  { name: "pets_allowed", label: "Pets allowed", type: "checkbox" },
  { name: "is_available_for_charter", label: "Available for charter", type: "checkbox" },
  { name: "notes", label: "Notes", type: "textarea", span: 2 },
]

type Row = { id: string } & Record<string, unknown>
const s = (v: unknown) => (typeof v === "string" ? v : "")

function fromRecord(a: Row): V {
  return {
    tail_number: s(a.tail_number), aircraft_model_id: s(a.aircraft_model_id), operator_id: s(a.operator_id), status: (AIRCRAFT_STATUSES as readonly string[]).includes(s(a.status)) ? (a.status as V["status"]) : "active",
    year_of_manufacture: numOr(a.year_of_manufacture as number | null), registration_country: s(a.registration_country), home_base_airport_id: s(a.home_base_airport_id),
    max_passengers: numOr(a.max_passengers as number | null), configured_seats: numOr(a.configured_seats as number | null), wifi_provider: s(a.wifi_provider), pets_allowed: Boolean(a.pets_allowed),
    hourly_rate: fromCents(a.hourly_rate_cents as number | null), is_available_for_charter: a.is_available_for_charter !== false, notes: s(a.notes),
  }
}
function toPayload(v: V): Record<string, unknown> {
  return {
    tail_number: v.tail_number.trim().toUpperCase(), aircraft_model_id: v.aircraft_model_id, operator_id: nul(v.operator_id), status: v.status,
    year_of_manufacture: intOrNull(v.year_of_manufacture), registration_country: upperOrNull(v.registration_country), home_base_airport_id: nul(v.home_base_airport_id),
    max_passengers: intOrNull(v.max_passengers), configured_seats: intOrNull(v.configured_seats), wifi_provider: nul(v.wifi_provider), pets_allowed: v.pets_allowed,
    hourly_rate_cents: toCents(v.hourly_rate), is_available_for_charter: v.is_available_for_charter, notes: nul(v.notes),
  }
}

const moreActions: MoreAction[] = [
  { key: "change-status", label: "Change status", icon: RefreshCw, permission: "aircraft.edit", kind: "dialog", title: "Change status", schema: z.object({ status: z.enum(AIRCRAFT_STATUSES) }), fields: [{ name: "status", label: "New status", type: "select", allowEmpty: false, options: enumOptions(AIRCRAFT_STATUSES, { aog: "AOG" }), span: 2 }], defaults: (row) => ({ status: row.status ?? "active" }), submit: (v, row) => ({ method: "patch", path: `/aircraft/${row.id}`, body: { status: v.status } }), success: "Status changed" },
  { key: "assign-operator", label: "Assign operator", icon: Building, permission: "aircraft.edit", kind: "dialog", title: "Assign operator", schema: z.object({ operator_id: optUuid }), fields: [{ name: "operator_id", label: "Operator", type: "select", useOptions: useOperatorOptions, emptyLabel: "Unassigned", span: 2 }], defaults: (row) => ({ operator_id: s(row.operator_id) }), submit: (v, row) => ({ method: "patch", path: `/aircraft/${row.id}`, body: { operator_id: nul(v.operator_id as string) } }), success: "Operator assigned" },
  { key: "upload-document", label: "Upload document", icon: Upload, permission: "documents.upload", kind: "planned", reason: "File upload (S3 presign) is not in the API yet" },
]

const sections: SectionSpec[] = [
  { key: "double-booked", title: "Double-booked legs", list: (id) => `/aircraft/${id}/double-booked`, permission: "legs.view", empty: "No scheduling conflicts.",
    columns: [{ key: "scheduled_departure_at", label: "Departure", kind: "datetime" }, { key: "scheduled_arrival_at", label: "Arrival", kind: "datetime" }, { key: "status", label: "Status", kind: "status" }, { key: "trip_id", label: "Trip", kind: "link", to: (r) => `/trips/${String(r.trip_id)}` }] },
]

export const aircraftEntity = registerEntity<Row, V>({
  kind: "aircraft", label: "Aircraft", plural: "Aircraft", endpoint: "/aircraft", path: "/aircraft", queryKey: "aircraft", permissionPrefix: "aircraft", graphType: "aircraft", icon: Plane,
  statuses: AIRCRAFT_STATUSES,
  nameOf: (a) => s(a.tail_number) || "Aircraft",
  archive: { status: "retired", label: "Archive (retire)" },
  form: { schema, fields, defaults, fromRecord, toPayload: (v) => toPayload(v), duplicate: (a) => ({ ...fromRecord(a), tail_number: `${s(a.tail_number)}X` }) },
  moreActions,
  sections,
  hideFields: ["amenities", "last_verified_at", "owner_contact_id", "serial_number", "interior_refurb_year", "exterior_refurb_year", "divans", "berths", "lavatory_type", "cargo_capacity_cuft", "smoking_allowed"],
})
