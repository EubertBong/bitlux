/** "Log call / email / meeting" on a contact: a small activity form that POSTs /activities. */

import * as React from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Mail, Phone, Users } from "lucide-react"
import { toast } from "sonner"
import { z } from "zod"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { ResourceForm } from "@/components/actions/ResourceForm"
import type { FieldDef } from "@/components/actions/registry"
import { api } from "@/lib/api"
import { RequirePermission, useAuth } from "@/lib/auth"
import type { Activity } from "@/lib/types"

export type LoggableType = "call" | "email" | "meeting"

const LABEL: Record<LoggableType, { verb: string; icon: typeof Phone; noun: string }> = {
  call: { verb: "Log call", icon: Phone, noun: "call" },
  email: { verb: "Log email", icon: Mail, noun: "email" },
  meeting: { verb: "Log meeting", icon: Users, noun: "meeting" },
}

const schema = z.object({
  subject: z.string().trim().min(2, "Give it a subject").max(200),
  direction: z.enum(["outbound", "inbound", "internal"]),
  occurred_at: z.string().min(1, "When did it happen?"),
  duration_minutes: z.number().int().min(0).max(24 * 60).optional().or(z.nan()),
  body: z.string().trim().max(4000).optional().or(z.literal("")),
})
type Values = z.infer<typeof schema>

const fields: FieldDef[] = [
  { name: "subject", label: "Subject", span: 2, autoFocus: true },
  { name: "direction", label: "Direction", type: "select", allowEmpty: false, options: [{ value: "outbound", label: "Outbound" }, { value: "inbound", label: "Inbound" }, { value: "internal", label: "Internal" }] },
  { name: "occurred_at", label: "When", type: "datetime" },
  { name: "duration_minutes", label: "Duration (minutes)", type: "number" },
  { name: "body", label: "Notes", type: "textarea", span: 2 },
]

function nowLocal(): string {
  const d = new Date()
  d.setSeconds(0, 0)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function LogActivityDialog({ contactId, contactName, type, open, onOpenChange }: { contactId: string; contactName: string; type: LoggableType; open: boolean; onOpenChange: (o: boolean) => void }) {
  const qc = useQueryClient()
  const { user } = useAuth()
  const create = useMutation({
    mutationFn: (v: Values) =>
      api.post<Activity>("/activities", {
        activity_type: type,
        direction: v.direction,
        subject: v.subject,
        body: v.body || null,
        contact_id: contactId,
        user_id: user?.id ?? null,
        occurred_at: new Date(v.occurred_at).toISOString(),
        duration_minutes: Number.isFinite(v.duration_minutes) ? v.duration_minutes : null,
      }),
    onSuccess: () => {
      toast.success(`${LABEL[type].noun[0]!.toUpperCase()}${LABEL[type].noun.slice(1)} logged`, { description: contactName })
      void qc.invalidateQueries({ queryKey: ["activities"] })
      void qc.invalidateQueries({ queryKey: ["contacts"] })
      void qc.invalidateQueries({ queryKey: ["graph"] })
      onOpenChange(false)
    },
  })
  const defaults = React.useMemo<Values>(() => ({ subject: "", direction: type === "email" ? "outbound" : "outbound", occurred_at: nowLocal(), duration_minutes: NaN, body: "" }), [type])
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="log-activity-dialog">
        <DialogHeader>
          <DialogTitle>{LABEL[type].verb}</DialogTitle>
          <DialogDescription>Recorded on {contactName}'s timeline and in the audit trail.</DialogDescription>
        </DialogHeader>
        <ResourceForm<Values> key={type} schema={schema} fields={fields} defaultValues={defaults} onSubmit={(v) => create.mutateAsync(v)} onCancel={() => onOpenChange(false)} submitLabel={LABEL[type].verb} />
      </DialogContent>
    </Dialog>
  )
}

/** The three inline buttons; each opens the dialog pre-typed. */
export function LogActivityButtons({ contactId, contactName, size = "sm" }: { contactId: string; contactName: string; size?: "sm" | "default" }) {
  const [openType, setOpenType] = React.useState<LoggableType | null>(null)
  return (
    <RequirePermission permission="activities.create" fallback={null}>
      <div className="flex flex-wrap items-center gap-2" data-testid="log-activity-buttons">
        {(Object.keys(LABEL) as LoggableType[]).map((t) => {
          const Icon = LABEL[t].icon
          return <Button key={t} variant="outline" size={size} onClick={() => setOpenType(t)} data-testid={`log-${t}`}><Icon /> {LABEL[t].verb}</Button>
        })}
      </div>
      {openType && <LogActivityDialog contactId={contactId} contactName={contactName} type={openType} open onOpenChange={(o) => !o && setOpenType(null)} />}
    </RequirePermission>
  )
}
