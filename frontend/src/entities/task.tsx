import { AlarmClockPlus, CalendarClock, CheckCircle2, CheckSquare, UserCog } from "lucide-react"
import { z } from "zod"
import { registerEntity, type FieldDef, type MoreAction } from "@/components/actions/registry"
import { useUserOptions } from "@/lib/lookups"
import { enumOptions, isoOrNull, nul, optText, optUuid, reqText, toLocalInput } from "./_shared"

export const TASK_STATUSES = ["open", "in_progress", "blocked", "completed", "cancelled"] as const
const PRIORITIES = ["low", "normal", "high", "urgent"] as const
const TYPES = ["call", "email", "follow_up", "document_request", "document_expiry", "payment_chase", "quote_prep", "ops_check", "compliance_review", "other"] as const

const schema = z.object({
  title: reqText("Title is required"),
  description: optText,
  task_type: z.enum(TYPES),
  status: z.enum(TASK_STATUSES),
  priority: z.enum(PRIORITIES),
  assigned_to_user_id: optUuid,
  due_at: optText,
  reminder_at: optText,
  blocked_reason: optText,
}).superRefine((v, ctx) => {
  if (v.status === "blocked" && !v.blocked_reason) ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["blocked_reason"], message: "Say what it is blocked on" })
})
type V = z.infer<typeof schema>
const defaults: V = { title: "", description: "", task_type: "follow_up", status: "open", priority: "normal", assigned_to_user_id: "", due_at: "", reminder_at: "", blocked_reason: "" }

const fields: FieldDef[] = [
  { name: "title", label: "Title", span: 2, autoFocus: true },
  { name: "task_type", label: "Type", type: "select", allowEmpty: false, options: enumOptions(TYPES) },
  { name: "priority", label: "Priority", type: "select", allowEmpty: false, options: enumOptions(PRIORITIES) },
  { name: "status", label: "Status", type: "select", allowEmpty: false, options: enumOptions(TASK_STATUSES) },
  { name: "assigned_to_user_id", label: "Assignee", type: "select", useOptions: useUserOptions, emptyLabel: "Unassigned" },
  { name: "blocked_reason", label: "Blocked on", span: 2, when: (v) => v.status === "blocked" },
  { name: "due_at", label: "Due", type: "datetime" },
  { name: "reminder_at", label: "Reminder", type: "datetime" },
  { name: "description", label: "Description", type: "textarea", span: 2 },
]

type Row = { id: string } & Record<string, unknown>
const s = (v: unknown) => (typeof v === "string" ? v : "")
const inEnum = <T extends readonly string[]>(vals: T, v: unknown, fallback: T[number]): T[number] => ((vals as readonly string[]).includes(s(v)) ? (v as T[number]) : fallback)

function fromRecord(t: Row): V {
  return { title: s(t.title), description: s(t.description), task_type: inEnum(TYPES, t.task_type, "other"), status: inEnum(TASK_STATUSES, t.status, "open"), priority: inEnum(PRIORITIES, t.priority, "normal"), assigned_to_user_id: s(t.assigned_to_user_id), due_at: toLocalInput(s(t.due_at)), reminder_at: toLocalInput(s(t.reminder_at)), blocked_reason: s(t.blocked_reason) }
}
function toPayload(v: V): Record<string, unknown> {
  return { title: v.title.trim(), description: nul(v.description), task_type: v.task_type, status: v.status, priority: v.priority, assigned_to_user_id: nul(v.assigned_to_user_id), due_at: isoOrNull(v.due_at), reminder_at: isoOrNull(v.reminder_at), blocked_reason: v.status === "blocked" ? nul(v.blocked_reason) : null }
}

const done = (row: Row) => row.status === "completed" || row.status === "cancelled"

const moreActions: MoreAction[] = [
  { key: "complete", label: "Complete", icon: CheckCircle2, permission: "tasks.edit", kind: "patch", post: (row) => `/tasks/${row.id}/complete`, body: (row) => (done(row) ? null : {}), title: (r) => `Complete "${s(r.title)}"?`, message: () => "Marks it completed now, by you.", success: "Task completed" },
  { key: "reassign", label: "Reassign", icon: UserCog, permission: "tasks.edit", kind: "dialog", title: "Reassign task", schema: z.object({ assigned_to_user_id: optUuid }), fields: [{ name: "assigned_to_user_id", label: "Assignee", type: "select", useOptions: useUserOptions, emptyLabel: "Unassigned", span: 2 }], defaults: (row) => ({ assigned_to_user_id: s(row.assigned_to_user_id) }), submit: (v, row) => ({ method: "patch", path: `/tasks/${row.id}`, body: { assigned_to_user_id: nul(v.assigned_to_user_id as string) } }), success: "Task reassigned" },
  { key: "snooze", label: "Snooze 1 day", icon: AlarmClockPlus, permission: "tasks.edit", kind: "patch", body: (row) => { if (done(row)) return null; const base = row.due_at ? new Date(s(row.due_at)) : new Date(); return { due_at: new Date(Math.max(base.getTime(), Date.now()) + 86_400_000).toISOString() } }, title: (r) => `Snooze "${s(r.title)}"?`, message: () => "Pushes the due date one day out.", success: "Task snoozed" },
  { key: "due-date", label: "Set due date", icon: CalendarClock, permission: "tasks.edit", kind: "dialog", title: "Set due date", schema: z.object({ due_at: z.string().min(1, "Pick a date and time") }), fields: [{ name: "due_at", label: "Due", type: "datetime", span: 2 }], defaults: (row) => ({ due_at: toLocalInput(s(row.due_at)) }), submit: (v, row) => ({ method: "patch", path: `/tasks/${row.id}`, body: { due_at: isoOrNull(v.due_at as string) } }), success: "Due date set" },
]

export const taskEntity = registerEntity<Row, V>({
  kind: "task", label: "Task", plural: "Tasks", endpoint: "/tasks", path: "/tasks", queryKey: "tasks", permissionPrefix: "tasks", graphType: "task", icon: CheckSquare,
  statuses: TASK_STATUSES,
  nameOf: (t) => s(t.title) || "Task",
  archive: { status: "cancelled", label: "Archive (cancel)" },
  form: { schema, fields, defaults, fromRecord, toPayload: (v) => toPayload(v), duplicate: (t) => ({ ...fromRecord(t), title: `${s(t.title)} (copy)`, status: "open" }) },
  moreActions,
  hideFields: ["dedupe_key", "source_system", "recurrence_rule", "sla_due_at", "sla_breached_at", "parent_task_id", "completed_by_user_id", "started_at", "assigned_team"],
})
