import { FileBadge, Link2, UserRound, UserX } from "lucide-react"
import { z } from "zod"
import { registerEntity, type FieldDef, type MoreAction, type SectionSpec } from "@/components/actions/registry"
import { useContactOptions } from "@/lib/lookups"
import type { Passenger } from "@/lib/types"
import { csvToList, dateOrNull, enumOptions, listToCsv, nul, numOr, numOrNull, optDate, optNum, optText, optUuid, reqText, toDateInput, TRAVEL_DOCUMENT_TYPES, upperOrNull } from "./_shared"

export const PASSENGER_STATUSES = ["active", "inactive", "deceased"] as const

const schema = z.object({
  contact_id: optUuid,
  first_name: reqText("First name is required"),
  last_name: reqText("Last name is required"),
  preferred_name: optText,
  status: z.enum(PASSENGER_STATUSES),
  date_of_birth: optDate,
  nationality_code: z.string().trim().max(2, "2-letter ISO code").optional().or(z.literal("")),
  gender_marker: optText,
  weight_kg: optNum,
  dietary_restrictions: optText,
  allergies: optText,
  mobility_assistance: z.boolean(),
  travels_with_pet: z.boolean(),
  emergency_contact_name: optText,
  emergency_contact_phone: optText,
  notes: optText,
})
type V = z.infer<typeof schema>

const defaults: V = { contact_id: "", first_name: "", last_name: "", preferred_name: "", status: "active", date_of_birth: "", nationality_code: "", gender_marker: "", weight_kg: NaN, dietary_restrictions: "", allergies: "", mobility_assistance: false, travels_with_pet: false, emergency_contact_name: "", emergency_contact_phone: "", notes: "" }

const fields: FieldDef[] = [
  { name: "first_name", label: "First name", autoFocus: true },
  { name: "last_name", label: "Last name" },
  { name: "preferred_name", label: "Preferred name" },
  { name: "status", label: "Status", type: "select", allowEmpty: false, options: enumOptions(PASSENGER_STATUSES) },
  { name: "contact_id", label: "Linked contact", type: "select", useOptions: useContactOptions, emptyLabel: "No contact (guest)", span: 2 },
  { name: "date_of_birth", label: "Date of birth", type: "date" },
  { name: "nationality_code", label: "Nationality (ISO-2)", placeholder: "US" },
  { name: "gender_marker", label: "Gender marker (as on document)", placeholder: "M / F / X" },
  { name: "weight_kg", label: "Weight (kg)", type: "number", description: "For weight & balance" },
  { name: "dietary_restrictions", label: "Dietary restrictions", placeholder: "vegetarian, no shellfish", description: "Comma-separated" },
  { name: "allergies", label: "Allergies", placeholder: "peanuts", description: "Comma-separated" },
  { name: "mobility_assistance", label: "Needs mobility assistance", type: "checkbox" },
  { name: "travels_with_pet", label: "Travels with a pet", type: "checkbox" },
  { name: "emergency_contact_name", label: "Emergency contact" },
  { name: "emergency_contact_phone", label: "Emergency phone", type: "tel" },
  { name: "notes", label: "Notes", type: "textarea", span: 2 },
]

type PaxRow = Passenger & Record<string, unknown>

function fromRecord(p: PaxRow): V {
  return {
    contact_id: p.contact_id ?? "", first_name: p.first_name, last_name: p.last_name, preferred_name: (p.preferred_name as string | null) ?? "",
    status: (PASSENGER_STATUSES as readonly string[]).includes(p.status) ? (p.status as V["status"]) : "active",
    date_of_birth: toDateInput(p.date_of_birth), nationality_code: p.nationality_code ?? "", gender_marker: (p.gender_marker as string | null) ?? "",
    weight_kg: numOr(p.weight_kg as number | null), dietary_restrictions: listToCsv(p.dietary_restrictions as string[] | null), allergies: listToCsv(p.allergies as string[] | null),
    mobility_assistance: Boolean(p.mobility_assistance), travels_with_pet: Boolean(p.travels_with_pet),
    emergency_contact_name: (p.emergency_contact_name as string | null) ?? "", emergency_contact_phone: (p.emergency_contact_phone as string | null) ?? "", notes: (p.notes as string | null) ?? "",
  }
}

function toPayload(v: V): Record<string, unknown> {
  return {
    contact_id: nul(v.contact_id), first_name: v.first_name.trim(), last_name: v.last_name.trim(), preferred_name: nul(v.preferred_name), status: v.status,
    date_of_birth: dateOrNull(v.date_of_birth), nationality_code: upperOrNull(v.nationality_code), gender_marker: upperOrNull(v.gender_marker), weight_kg: numOrNull(v.weight_kg),
    dietary_restrictions: csvToList(v.dietary_restrictions), allergies: csvToList(v.allergies), mobility_assistance: v.mobility_assistance, travels_with_pet: v.travels_with_pet,
    emergency_contact_name: nul(v.emergency_contact_name), emergency_contact_phone: nul(v.emergency_contact_phone), notes: nul(v.notes),
  }
}

const travelDocSchema = z.object({
  document_type: z.enum(TRAVEL_DOCUMENT_TYPES),
  number: z.string().trim().min(3, "Document number is required").max(64),
  full_name_on_document: reqText("Name as printed is required"),
  issuing_country: z.string().trim().length(2, "2-letter ISO code"),
  nationality_code: z.string().trim().max(2).optional().or(z.literal("")),
  issue_date: optDate,
  expiry_date: optDate,
  is_primary: z.boolean(),
})
const travelDocFields: FieldDef[] = [
  { name: "document_type", label: "Type", type: "select", allowEmpty: false, options: enumOptions(TRAVEL_DOCUMENT_TYPES) },
  { name: "number", label: "Number", description: "Encrypted at rest; only the last 4 are ever shown again.", autoFocus: true },
  { name: "full_name_on_document", label: "Name as printed", span: 2 },
  { name: "issuing_country", label: "Issuing country (ISO-2)", placeholder: "US" },
  { name: "nationality_code", label: "Nationality (ISO-2)" },
  { name: "issue_date", label: "Issued", type: "date" },
  { name: "expiry_date", label: "Expires", type: "date" },
  { name: "is_primary", label: "Primary document for this passenger", type: "checkbox", span: 2 },
]
const travelDocDefaults = { document_type: "passport", number: "", full_name_on_document: "", issuing_country: "", nationality_code: "", issue_date: "", expiry_date: "", is_primary: true }
const travelDocBody = (v: Record<string, unknown>, passengerId: string) => ({
  passenger_id: passengerId, document_type: v.document_type, number: String(v.number).trim(), full_name_on_document: String(v.full_name_on_document).trim(),
  issuing_country: String(v.issuing_country).toUpperCase(), nationality_code: upperOrNull(v.nationality_code as string), issue_date: dateOrNull(v.issue_date as string), expiry_date: dateOrNull(v.expiry_date as string), is_primary: Boolean(v.is_primary),
})

const moreActions: MoreAction[] = [
  { key: "travel-document", label: "Add travel document", icon: FileBadge, permission: "passengers.edit", kind: "dialog", title: "Add travel document", schema: travelDocSchema, fields: travelDocFields, defaults: (row) => ({ ...travelDocDefaults, full_name_on_document: `${row.first_name ?? ""} ${row.last_name ?? ""}`.trim() }), submit: (v, row) => ({ method: "post", path: `/passengers/${row.id}/travel-documents`, body: travelDocBody(v, row.id) }), success: "Travel document added", refresh: ["travel_documents"] },
  { key: "link-account", label: "Link to account", icon: Link2, permission: "passengers.edit", kind: "planned", reason: "Account-holder membership endpoint is not in the API yet" },
  { key: "mark-inactive", label: "Mark inactive", icon: UserX, permission: "passengers.edit", kind: "patch", body: (row) => (row.status === "inactive" ? null : { status: "inactive" }), title: (r) => `Mark ${r.first_name} ${r.last_name} inactive?`, message: () => "They stay on past manifests and in history; new bookings will not offer them.", success: "Passenger marked inactive" },
]

const sections: SectionSpec[] = [
  { key: "travel-documents", title: "Travel documents", icon: FileBadge, list: (id) => `/passengers/${id}/travel-documents`, permission: "passengers.view", empty: "No travel documents on file.",
    columns: [{ key: "document_type", label: "Type", kind: "status" }, { key: "number_last4", label: "Number" }, { key: "full_name_on_document", label: "Name as printed" }, { key: "issuing_country", label: "Issued by" }, { key: "expiry_date", label: "Expires", kind: "date" }],
    add: { label: "Add travel document", permission: "passengers.edit", schema: travelDocSchema, fields: travelDocFields, defaults: travelDocDefaults, body: travelDocBody, post: (id) => `/passengers/${id}/travel-documents`, success: "Travel document added" } },
  { key: "flight-history", title: "Flight history", list: (id) => `/passengers/${id}/flight-history`, permission: "trips.view", empty: "No flown or scheduled legs yet.",
    columns: [{ key: "scheduled_departure_at", label: "Departure", kind: "datetime" }, { key: "scheduled_arrival_at", label: "Arrival", kind: "datetime" }, { key: "status", label: "Status", kind: "status" }, { key: "flight_number", label: "Flight" }] },
]

export const passengerEntity = registerEntity<PaxRow, V>({
  kind: "passenger", label: "Passenger", plural: "Passengers", endpoint: "/passengers", path: "/passengers", queryKey: "passengers", permissionPrefix: "passengers", graphType: "passenger", icon: UserRound,
  statuses: PASSENGER_STATUSES,
  nameOf: (p) => `${p.first_name} ${p.last_name}`,
  archive: { status: "inactive", label: "Archive (mark inactive)" },
  form: { schema, fields, defaults, fromRecord, toPayload: (v) => toPayload(v), duplicate: (p) => ({ ...fromRecord(p), last_name: `${p.last_name} (copy)` }) },
  moreActions,
  sections,
  hideFields: ["ktn_last4", "redress_number", "known_traveler_number", "pet_details", "guardian_passenger_id"],
})
