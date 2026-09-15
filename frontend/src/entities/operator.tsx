import { Building, ShieldCheck, ShieldPlus, UserPlus } from "lucide-react"
import { z } from "zod"
import { registerEntity, type FieldDef, type MoreAction, type SectionSpec } from "@/components/actions/registry"
import { useContactOptions } from "@/lib/lookups"
import { dateOrNull, enumOptions, fromCents, nul, numOr, numOrNull, optDate, optEmail, optNum, optText, optUuid, reqText, toCents, toDateInput, upperOrNull } from "./_shared"

export const OPERATOR_STATUSES = ["prospect", "under_review", "approved", "conditional", "suspended", "blacklisted"] as const
const REGULATORY_PARTS = ["part_91", "part_91k", "part_121", "part_135", "easa_cat", "easa_nco", "easa_spo", "other"] as const
const PAYMENT_TERMS = ["prepaid", "due_on_receipt", "net_7", "net_15", "net_30", "net_45", "net_60", "on_account"] as const
const SAFETY_PROGRAMS = ["argus", "wyvern", "isbao", "isbah", "acsf", "tsa_twelve_five", "easa_sms", "other"] as const
const RATING_LEVELS = ["not_rated", "argus_gold", "argus_gold_plus", "argus_platinum", "wyvern_registered", "wyvern_wingman", "wyvern_wingman_plus", "isbao_stage_1", "isbao_stage_2", "isbao_stage_3", "acsf_registered", "other"] as const

const schema = z.object({
  legal_name: reqText("Legal name is required"),
  dba_name: optText,
  operator_code: optText,
  status: z.enum(OPERATOR_STATUSES),
  country_code: z.string().trim().max(2).optional().or(z.literal("")),
  regulatory_part: z.enum(REGULATORY_PARTS).optional().or(z.literal("")),
  aoc_number: optText,
  aoc_expiry: optDate,
  primary_contact_id: optUuid,
  ops_email: optEmail,
  ops_phone: optText,
  accounts_email: optEmail,
  website: optText,
  insurance_expiry: optDate,
  insurance_limit: optNum,
  w9_on_file: z.boolean(),
  is_preferred: z.boolean(),
  payment_terms: z.enum(PAYMENT_TERMS),
  commission_pct: optNum,
  blocklist_reason: optText,
  notes: optText,
}).superRefine((v, ctx) => {
  if (v.status === "blacklisted" && !v.blocklist_reason) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["blocklist_reason"], message: "A reason is required to blacklist" })
})
type V = z.infer<typeof schema>
const defaults: V = { legal_name: "", dba_name: "", operator_code: "", status: "prospect", country_code: "", regulatory_part: "", aoc_number: "", aoc_expiry: "", primary_contact_id: "", ops_email: "", ops_phone: "", accounts_email: "", website: "", insurance_expiry: "", insurance_limit: NaN, w9_on_file: false, is_preferred: false, payment_terms: "prepaid", commission_pct: NaN, blocklist_reason: "", notes: "" }

const fields: FieldDef[] = [
  { name: "legal_name", label: "Legal name", autoFocus: true },
  { name: "dba_name", label: "Trading as (DBA)" },
  { name: "operator_code", label: "Internal code", placeholder: "ALP" },
  { name: "status", label: "Status", type: "select", allowEmpty: false, options: enumOptions(OPERATOR_STATUSES) },
  { name: "blocklist_reason", label: "Blocklist reason", span: 2, when: (v) => v.status === "blacklisted" },
  { name: "country_code", label: "Country (ISO-2)", placeholder: "US" },
  { name: "regulatory_part", label: "Regulatory part", type: "select", options: enumOptions(REGULATORY_PARTS, { part_91: "Part 91", part_91k: "Part 91K", part_121: "Part 121", part_135: "Part 135", easa_cat: "EASA CAT", easa_nco: "EASA NCO", easa_spo: "EASA SPO" }), emptyLabel: "Unknown" },
  { name: "aoc_number", label: "AOC number" },
  { name: "aoc_expiry", label: "AOC expiry", type: "date" },
  { name: "primary_contact_id", label: "Primary contact", type: "select", useOptions: useContactOptions, emptyLabel: "None" },
  { name: "payment_terms", label: "Payment terms", type: "select", allowEmpty: false, options: enumOptions(PAYMENT_TERMS) },
  { name: "ops_email", label: "Ops email", type: "email" },
  { name: "ops_phone", label: "Ops phone", type: "tel" },
  { name: "accounts_email", label: "Accounts email", type: "email" },
  { name: "website", label: "Website", placeholder: "https://" },
  { name: "insurance_expiry", label: "Insurance expiry", type: "date" },
  { name: "insurance_limit", label: "Insurance limit (USD)", type: "number" },
  { name: "commission_pct", label: "Commission (%)", type: "number", placeholder: "7.5" },
  { name: "w9_on_file", label: "W-9 on file", type: "checkbox" },
  { name: "is_preferred", label: "Preferred operator", type: "checkbox" },
  { name: "notes", label: "Notes", type: "textarea", span: 2 },
]

type Row = { id: string } & Record<string, unknown>
const s = (v: unknown) => (typeof v === "string" ? v : "")

function fromRecord(o: Row): V {
  return {
    legal_name: s(o.legal_name), dba_name: s(o.dba_name), operator_code: s(o.operator_code), status: (OPERATOR_STATUSES as readonly string[]).includes(s(o.status)) ? (o.status as V["status"]) : "prospect",
    country_code: s(o.country_code), regulatory_part: (REGULATORY_PARTS as readonly string[]).includes(s(o.regulatory_part)) ? (o.regulatory_part as V["regulatory_part"]) : "", aoc_number: s(o.aoc_number), aoc_expiry: toDateInput(s(o.aoc_expiry)),
    primary_contact_id: s(o.primary_contact_id), ops_email: s(o.ops_email), ops_phone: s(o.ops_phone), accounts_email: s(o.accounts_email), website: s(o.website),
    insurance_expiry: toDateInput(s(o.insurance_expiry)), insurance_limit: fromCents(o.insurance_limit_cents as number | null), w9_on_file: Boolean(o.w9_on_file), is_preferred: Boolean(o.is_preferred),
    payment_terms: (PAYMENT_TERMS as readonly string[]).includes(s(o.payment_terms)) ? (o.payment_terms as V["payment_terms"]) : "prepaid",
    commission_pct: typeof o.commission_rate === "number" ? o.commission_rate * 100 : numOr(null), blocklist_reason: s(o.blocklist_reason), notes: s(o.notes),
  }
}
function toPayload(v: V): Record<string, unknown> {
  const pct = numOrNull(v.commission_pct)
  return {
    legal_name: v.legal_name.trim(), dba_name: nul(v.dba_name), operator_code: upperOrNull(v.operator_code), status: v.status, country_code: upperOrNull(v.country_code), regulatory_part: nul(v.regulatory_part),
    aoc_number: nul(v.aoc_number), aoc_expiry: dateOrNull(v.aoc_expiry), primary_contact_id: nul(v.primary_contact_id), ops_email: nul(v.ops_email), ops_phone: nul(v.ops_phone), accounts_email: nul(v.accounts_email), website: nul(v.website),
    insurance_expiry: dateOrNull(v.insurance_expiry), insurance_limit_cents: toCents(v.insurance_limit), w9_on_file: v.w9_on_file, is_preferred: v.is_preferred, payment_terms: v.payment_terms,
    commission_rate: pct === null ? null : Math.round(pct * 100) / 10000, blocklist_reason: nul(v.blocklist_reason), notes: nul(v.notes),
  }
}

const ratingSchema = z.object({ program: z.enum(SAFETY_PROGRAMS), rating_level: z.enum(RATING_LEVELS), issued_date: optDate, expiry_date: optDate, auditor_name: optText, audit_reference: optText })
const ratingFields: FieldDef[] = [
  { name: "program", label: "Program", type: "select", allowEmpty: false, options: enumOptions(SAFETY_PROGRAMS, { argus: "ARGUS", wyvern: "Wyvern", isbao: "IS-BAO", isbah: "IS-BAH", acsf: "ACSF", tsa_twelve_five: "TSA 12-5", easa_sms: "EASA SMS" }) },
  { name: "rating_level", label: "Rating", type: "select", allowEmpty: false, options: enumOptions(RATING_LEVELS, { argus_gold: "ARGUS Gold", argus_gold_plus: "ARGUS Gold+", argus_platinum: "ARGUS Platinum", wyvern_registered: "Wyvern Registered", wyvern_wingman: "Wyvern Wingman", wyvern_wingman_plus: "Wyvern Wingman+", isbao_stage_1: "IS-BAO Stage 1", isbao_stage_2: "IS-BAO Stage 2", isbao_stage_3: "IS-BAO Stage 3", acsf_registered: "ACSF Registered" }) },
  { name: "issued_date", label: "Issued", type: "date" },
  { name: "expiry_date", label: "Expires", type: "date" },
  { name: "auditor_name", label: "Auditor" },
  { name: "audit_reference", label: "Audit reference" },
]
const ratingDefaults = { program: "argus", rating_level: "argus_gold", issued_date: "", expiry_date: "", auditor_name: "", audit_reference: "" }
const ratingBody = (v: Record<string, unknown>, operatorId: string) => ({ operator_id: operatorId, program: v.program, rating_level: v.rating_level, issued_date: dateOrNull(v.issued_date as string), expiry_date: dateOrNull(v.expiry_date as string), auditor_name: nul(v.auditor_name as string), audit_reference: nul(v.audit_reference as string), is_current: true })

const moreActions: MoreAction[] = [
  { key: "safety-rating", label: "Add safety rating", icon: ShieldPlus, permission: "operators.edit", kind: "dialog", title: "Add safety rating", schema: ratingSchema, fields: ratingFields, defaults: () => ratingDefaults, submit: (v, row) => ({ method: "post", path: `/operators/${row.id}/safety-ratings`, body: ratingBody(v, row.id) }), success: "Safety rating added", refresh: ["operator_safety_ratings"] },
  { key: "insurance", label: "Update insurance", icon: ShieldCheck, permission: "operators.edit", kind: "dialog", title: "Update insurance", schema: z.object({ insurance_expiry: optDate, insurance_limit: optNum }), fields: [{ name: "insurance_expiry", label: "Insurance expiry", type: "date" }, { name: "insurance_limit", label: "Limit (USD)", type: "number" }], defaults: (row) => ({ insurance_expiry: toDateInput(s(row.insurance_expiry)), insurance_limit: fromCents(row.insurance_limit_cents as number | null) }), submit: (v, row) => ({ method: "patch", path: `/operators/${row.id}`, body: { insurance_expiry: dateOrNull(v.insurance_expiry as string), insurance_limit_cents: toCents(v.insurance_limit as number) } }), success: "Insurance updated" },
  { key: "add-contact", label: "Add contact", icon: UserPlus, permission: "operators.edit", kind: "dialog", title: "Set primary contact", schema: z.object({ primary_contact_id: optUuid }), fields: [{ name: "primary_contact_id", label: "Primary contact", type: "select", useOptions: useContactOptions, emptyLabel: "None", span: 2 }], defaults: (row) => ({ primary_contact_id: s(row.primary_contact_id) }), submit: (v, row) => ({ method: "patch", path: `/operators/${row.id}`, body: { primary_contact_id: nul(v.primary_contact_id as string) } }), success: "Primary contact set" },
]

const sections: SectionSpec[] = [
  { key: "safety-ratings", title: "Safety ratings", icon: ShieldCheck, list: (id) => `/operators/${id}/safety-ratings`, permission: "operators.view", empty: "No safety ratings recorded.",
    columns: [{ key: "program", label: "Program", kind: "status" }, { key: "rating_level", label: "Rating", kind: "status" }, { key: "issued_date", label: "Issued", kind: "date" }, { key: "expiry_date", label: "Expires", kind: "date" }, { key: "auditor_name", label: "Auditor" }],
    add: { label: "Add safety rating", permission: "operators.edit", schema: ratingSchema, fields: ratingFields, defaults: ratingDefaults, body: ratingBody, post: (id) => `/operators/${id}/safety-ratings`, success: "Safety rating added" } },
]

export const operatorEntity = registerEntity<Row, V>({
  kind: "operator", label: "Operator", plural: "Operators", endpoint: "/operators", path: "/operators", queryKey: "operators", permissionPrefix: "operators", graphType: "operator", icon: Building,
  statuses: OPERATOR_STATUSES,
  nameOf: (o) => s(o.dba_name) || s(o.legal_name) || "Operator",
  archive: { status: "suspended", label: "Archive (suspend)" },
  form: { schema, fields, defaults, fromRecord, toPayload: (v) => toPayload(v), duplicate: (o) => ({ ...fromRecord(o), legal_name: `${s(o.legal_name)} (copy)`, operator_code: "" }) },
  moreActions,
  sections,
  hideFields: ["fleet_size", "ops_24h_phone"],
})
