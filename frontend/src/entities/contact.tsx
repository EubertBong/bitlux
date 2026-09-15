/** The Contact entity: form schema, fields, payload mapping, archive semantics. */

import { GitMerge, Mail, MessageSquarePlus, Tags, Users } from "lucide-react"
import { z } from "zod"
import { registerEntity, type FieldDef, type MoreAction } from "@/components/actions/registry"
import { useSegmentOptions, useUserOptions } from "@/lib/lookups"
import { titleCase } from "@/lib/format"
import type { Contact, ContactStatus } from "@/lib/types"

export const CONTACT_STATUSES: ContactStatus[] = ["lead", "prospect", "active", "dormant", "churned", "blocked"]
export const LEAD_SOURCES = ["referral", "website", "inbound_call", "outbound", "broker_network", "event", "advertising", "partner", "empty_leg_alert", "import", "other"] as const

const optionalText = z.string().trim().max(200).optional().or(z.literal(""))

export const contactSchema = z
  .object({
    contact_type: z.enum(["individual", "company"]),
    first_name: optionalText,
    last_name: optionalText,
    company_name: optionalText,
    job_title: optionalText,
    primary_email: z.string().trim().email("Enter a valid email").optional().or(z.literal("")),
    primary_phone: optionalText,
    segment_id: z.string().optional().or(z.literal("")),
    owner_user_id: z.string().optional().or(z.literal("")),
    status: z.enum(["lead", "prospect", "active", "dormant", "churned", "blocked"]),
    source: z.enum(LEAD_SOURCES),
    do_not_contact: z.boolean(),
    vip_notes: z.string().trim().max(4000).optional().or(z.literal("")),
    preferences: z
      .string()
      .trim()
      .refine((s) => {
        if (!s) return true
        try {
          const v = JSON.parse(s)
          return typeof v === "object" && v !== null && !Array.isArray(v)
        } catch {
          return false
        }
      }, 'Must be a JSON object, e.g. {"seat": "window"}'),
  })
  .superRefine((v, ctx) => {
    if (v.contact_type === "individual" && !v.last_name) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["last_name"], message: "Last name is required for a person" })
    if (v.contact_type === "company" && !v.company_name) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["company_name"], message: "Company name is required" })
  })

export type ContactValues = z.infer<typeof contactSchema>

export const contactDefaults: ContactValues = {
  contact_type: "individual", first_name: "", last_name: "", company_name: "", job_title: "", primary_email: "", primary_phone: "",
  segment_id: "", owner_user_id: "", status: "lead", source: "other", do_not_contact: false, vip_notes: "", preferences: "",
}

const nul = (s: string | undefined) => (s && s.trim() ? s.trim() : null)

export function contactDisplayName(v: Pick<ContactValues, "contact_type" | "first_name" | "last_name" | "company_name">): string {
  if (v.contact_type === "company") return v.company_name?.trim() || "Company"
  return [v.first_name, v.last_name].map((s) => s?.trim()).filter(Boolean).join(" ") || "Contact"
}

export const contactFields: FieldDef[] = [
  { name: "contact_type", label: "Type", type: "select", allowEmpty: false, options: [{ value: "individual", label: "Person" }, { value: "company", label: "Company" }] },
  { name: "status", label: "Status", type: "select", allowEmpty: false, options: CONTACT_STATUSES.map((s) => ({ value: s, label: titleCase(s) })) },
  { name: "first_name", label: "First name", autoFocus: true, when: (v) => v.contact_type !== "company" },
  { name: "last_name", label: "Last name", when: (v) => v.contact_type !== "company" },
  { name: "company_name", label: "Company", span: 2 },
  { name: "job_title", label: "Job title", when: (v) => v.contact_type !== "company" },
  { name: "primary_email", label: "Email", type: "email", placeholder: "name@example.com" },
  { name: "primary_phone", label: "Phone", type: "tel", placeholder: "+1 212 555 0100" },
  { name: "segment_id", label: "Segment", type: "select", useOptions: useSegmentOptions, emptyLabel: "No segment" },
  { name: "owner_user_id", label: "Owner", type: "select", useOptions: useUserOptions, emptyLabel: "Unassigned" },
  { name: "source", label: "Lead source", type: "select", allowEmpty: false, options: LEAD_SOURCES.map((s) => ({ value: s, label: titleCase(s) })) },
  { name: "do_not_contact", label: "Do not contact", type: "checkbox" },
  { name: "vip_notes", label: "VIP notes", type: "textarea", span: 2 },
  { name: "preferences", label: "Preferences (JSON)", type: "json", span: 2, placeholder: '{"seat": "window", "catering": "kosher"}', description: "Free-form preference bag; must be a JSON object." },
]

export function contactFromRecord(c: Contact): ContactValues {
  return {
    contact_type: c.contact_type,
    first_name: c.first_name ?? "",
    last_name: c.last_name ?? "",
    company_name: c.company_name ?? "",
    job_title: c.job_title ?? "",
    primary_email: c.primary_email ?? "",
    primary_phone: c.primary_phone ?? "",
    segment_id: c.segment_id ?? "",
    owner_user_id: c.owner_user_id ?? "",
    status: c.status,
    source: (LEAD_SOURCES as readonly string[]).includes(c.source ?? "") ? (c.source as ContactValues["source"]) : "other",
    do_not_contact: Boolean(c.do_not_contact),
    vip_notes: c.vip_notes ?? "",
    preferences: c.preferences && Object.keys(c.preferences).length ? JSON.stringify(c.preferences, null, 2) : "",
  }
}

export function contactToPayload(v: ContactValues): Record<string, unknown> {
  const company = v.contact_type === "company"
  return {
    contact_type: v.contact_type,
    status: v.status,
    source: v.source,
    display_name: contactDisplayName(v),
    first_name: company ? null : nul(v.first_name),
    last_name: company ? null : nul(v.last_name),
    company_name: nul(v.company_name),
    job_title: company ? null : nul(v.job_title),
    primary_email: nul(v.primary_email),
    primary_phone: nul(v.primary_phone),
    segment_id: nul(v.segment_id),
    owner_user_id: nul(v.owner_user_id),
    do_not_contact: v.do_not_contact,
    vip_notes: nul(v.vip_notes),
    preferences: v.preferences.trim() ? (JSON.parse(v.preferences) as Record<string, unknown>) : {},
  }
}

const moreActions: MoreAction[] = [
  { key: "log-activity", label: "Log activity", icon: MessageSquarePlus, permission: "activities.create", kind: "link", to: (row) => `/contacts/${row.id}?tab=activities` },
  { key: "email", label: "Send email", icon: Mail, permission: "contacts.view", kind: "link", href: (row) => (typeof row.primary_email === "string" && row.primary_email ? `mailto:${row.primary_email}` : null) },
  { key: "segment", label: "Add to segment", icon: Tags, permission: "contacts.edit", kind: "dialog", title: "Add to segment", schema: z.object({ segment_id: z.string().optional().or(z.literal("")) }), fields: [{ name: "segment_id", label: "Segment", type: "select", useOptions: useSegmentOptions, emptyLabel: "No segment", span: 2 }], defaults: (row) => ({ segment_id: typeof row.segment_id === "string" ? row.segment_id : "" }), submit: (v, row) => ({ method: "patch", path: `/contacts/${row.id}`, body: { segment_id: v.segment_id ? String(v.segment_id) : null } }), success: "Segment updated" },
  { key: "merge", label: "Merge", icon: GitMerge, permission: "contacts.edit", kind: "planned", reason: "Merge (re-pointing passengers, trips and activities) is not in the API yet" },
]

export const contactEntity = registerEntity<Contact, ContactValues>({
  kind: "contact",
  icon: Users,
  statuses: CONTACT_STATUSES,
  moreActions,
  label: "Contact",
  plural: "Contacts",
  endpoint: "/contacts",
  path: "/contacts",
  queryKey: "contacts",
  permissionPrefix: "contacts",
  graphType: "contact",
  nameOf: (c) => c.display_name,
  // "Archive" keeps the record and its history but takes it out of the active book.
  archive: { status: "dormant", label: "Archive (mark dormant)", describe: (c) => `${c.display_name} is marked dormant. Trips, activities and documents stay attached; set the status back to reactivate.` },
  form: {
    schema: contactSchema,
    fields: contactFields,
    defaults: contactDefaults,
    fromRecord: contactFromRecord,
    toPayload: (v) => contactToPayload(v),
    duplicate: (c) => {
      const v = contactFromRecord(c)
      return c.contact_type === "company" ? { ...v, company_name: `${v.company_name} (copy)` } : { ...v, last_name: `${v.last_name} (copy)`, primary_email: "" }
    },
  },
})
