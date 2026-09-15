/** /contacts/:id -- header actions (log activity, edit, delete), tabs, the Relationship graph. */

import * as React from "react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { Building2, Users } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PageHeader } from "@/components/common/PageHeader"
import { EmptyState, ErrorState, LoadingState } from "@/components/common/States"
import { RelationshipGraph } from "@/components/RelationshipGraph"
import { DeleteButton, EditButton, MoreMenu } from "@/components/actions"
import { BackLink } from "@/components/common/BackLink"
import { api } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { ago, fmtDate, fmtDateTime, money, titleCase } from "@/lib/format"
import { useSegmentOptions, useUserOptions } from "@/lib/lookups"
import type { Activity, Contact, ContactChannel, Document, Passenger } from "@/lib/types"
import { LogActivityButtons } from "./LogActivity"
import { ContactStatusBadge } from "./contactShared"

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "passengers", label: "Passengers" },
  { key: "documents", label: "Documents" },
  { key: "activities", label: "Activities" },
  { key: "relationship", label: "Relationship" },
] as const
type TabKey = (typeof TABS)[number]["key"]

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 py-2 sm:flex-row sm:gap-4">
      <dt className="w-40 shrink-0 text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-sm">{children ?? <span className="text-muted-foreground">—</span>}</dd>
    </div>
  )
}

function Kpi({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <Card className="gap-1 py-4" data-testid="kpi">
      <CardHeader className="px-4"><CardDescription>{label}</CardDescription></CardHeader>
      <CardContent className="px-4"><div className="text-2xl font-semibold tabular-nums">{value}</div>{hint && <div className="text-xs text-muted-foreground">{hint}</div>}</CardContent>
    </Card>
  )
}

function Overview({ contact }: { contact: Contact }) {
  const segments = useSegmentOptions()
  const users = useUserOptions()
  const channels = useQuery({ queryKey: ["contacts", contact.id, "channels"], queryFn: () => api.get<ContactChannel[]>(`/contacts/${contact.id}/channels`) })
  const prefs = contact.preferences && Object.keys(contact.preferences).length ? contact.preferences : null
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <Kpi label="Lifetime value" value={money(contact.lifetime_value_cents)} hint="sum of priced trips" />
        <Kpi label="Trips" value={contact.trip_count} />
        <Kpi label="Last activity" value={ago(contact.last_activity_at)} hint={contact.last_activity_at ? fmtDateTime(contact.last_activity_at) : undefined} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Details</CardTitle></CardHeader>
          <CardContent>
            <dl className="divide-y" data-testid="contact-details">
              <Row label="Type">{contact.contact_type === "company" ? "Company" : "Person"}</Row>
              <Row label="Status"><ContactStatusBadge status={contact.status} /></Row>
              <Row label="Email">{contact.primary_email ? <a className="hover:underline" href={`mailto:${contact.primary_email}`}>{contact.primary_email}</a> : null}</Row>
              <Row label="Phone">{contact.primary_phone}</Row>
              {contact.contact_type !== "company" && <Row label="Company">{contact.company_name}</Row>}
              {contact.contact_type !== "company" && <Row label="Job title">{contact.job_title}</Row>}
              <Row label="Segment">{contact.segment_id ? (segments.options.find((o) => o.value === contact.segment_id)?.label ?? "…") : null}</Row>
              <Row label="Owner">{contact.owner_user_id ? (users.options.find((o) => o.value === contact.owner_user_id)?.label ?? "…") : "Unassigned"}</Row>
              <Row label="Lead source">{contact.source ? titleCase(contact.source) : null}</Row>
              <Row label="Do not contact">{contact.do_not_contact ? <Badge variant="destructive">Yes</Badge> : "No"}</Row>
              <Row label="VIP notes">{contact.vip_notes}</Row>
              <Row label="Preferences">{prefs ? <pre className="whitespace-pre-wrap rounded bg-muted p-2 font-mono text-xs">{JSON.stringify(prefs, null, 2)}</pre> : null}</Row>
              <Row label="Created">{fmtDateTime(contact.created_at)}</Row>
            </dl>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Channels</CardTitle><CardDescription>Every way to reach them</CardDescription></CardHeader>
          <CardContent>
            {channels.isPending ? <LoadingState rows={3} /> : channels.isError ? <ErrorState error={channels.error} onRetry={() => void channels.refetch()} /> : channels.data.length === 0 ? <EmptyState>Only the primary email / phone above</EmptyState> : (
              <ul className="divide-y text-sm">
                {channels.data.map((ch) => (
                  <li key={ch.id} className="flex items-center justify-between gap-3 py-2">
                    <span><span className="text-muted-foreground">{titleCase(ch.channel_type)}{ch.label ? ` · ${ch.label}` : ""}</span> <span className="ml-2">{ch.value}</span></span>
                    {ch.is_primary && <Badge variant="secondary">Primary</Badge>}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function PassengersTab({ contact }: { contact: Contact }) {
  const { can } = useAuth()
  const q = useQuery({ queryKey: ["passengers", "for-contact", contact.id], queryFn: () => api.get<Passenger[]>(`/contacts/${contact.id}/passengers`), enabled: can("passengers.view") })
  if (!can("passengers.view")) return <EmptyState>Your role cannot view passengers.</EmptyState>
  if (q.isPending) return <LoadingState />
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />
  if (q.data.length === 0) return <EmptyState icon={Users} title="No passengers linked" description={`Passengers are the people who actually fly. Link ${contact.display_name}'s travellers here.`} />
  return (
    <div className="rounded-lg border bg-card">
      <Table>
        <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Nationality</TableHead><TableHead>Date of birth</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
        <TableBody>
          {q.data.map((p) => (
            <TableRow key={p.id} data-testid="related-row">
              <TableCell><Link className="font-medium hover:underline" to={`/passengers/${p.id}`}>{p.first_name} {p.last_name}</Link></TableCell>
              <TableCell>{p.nationality_code ?? "—"}</TableCell>
              <TableCell>{fmtDate(p.date_of_birth)}</TableCell>
              <TableCell><Badge variant="secondary">{titleCase(p.status)}</Badge></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function DocumentsTab({ contact }: { contact: Contact }) {
  const { can } = useAuth()
  const q = useQuery({ queryKey: ["documents", "for", "contact", contact.id], queryFn: () => api.get<Document[]>(`/documents/for/contact/${contact.id}`), enabled: can("documents.view") })
  if (!can("documents.view")) return <EmptyState>Your role cannot view documents.</EmptyState>
  if (q.isPending) return <LoadingState />
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />
  if (q.data.length === 0) return <EmptyState>No documents attached to {contact.display_name}</EmptyState>
  return (
    <div className="rounded-lg border bg-card">
      <Table>
        <TableHeader><TableRow><TableHead>Title</TableHead><TableHead>Type</TableHead><TableHead>Status</TableHead><TableHead>Expires</TableHead></TableRow></TableHeader>
        <TableBody>
          {q.data.map((d) => (
            <TableRow key={d.id} data-testid="related-row">
              <TableCell><Link className="font-medium hover:underline" to={`/documents/${d.id}`}>{d.title}</Link></TableCell>
              <TableCell>{titleCase(d.document_type)}</TableCell>
              <TableCell><Badge variant="secondary">{titleCase(d.status)}</Badge></TableCell>
              <TableCell>{fmtDate(d.expires_at)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function ActivitiesTab({ contact }: { contact: Contact }) {
  const { can } = useAuth()
  const q = useQuery({ queryKey: ["activities", "for-contact", contact.id], queryFn: () => api.get<Activity[]>(`/contacts/${contact.id}/activities?limit=100`), enabled: can("activities.view") })
  return (
    <div className="flex flex-col gap-3">
      <LogActivityButtons contactId={contact.id} contactName={contact.display_name} />
      {!can("activities.view") ? <EmptyState>Your role cannot view activities.</EmptyState> : q.isPending ? <LoadingState /> : q.isError ? <ErrorState error={q.error} onRetry={() => void q.refetch()} /> : q.data.length === 0 ? (
        <EmptyState title="No activity yet" description="Log the first call, email or meeting above; it lands here and in the audit trail." />
      ) : (
        <ul className="divide-y rounded-lg border bg-card text-sm" data-testid="activity-list">
          {q.data.map((a) => (
            <li key={a.id} className="flex flex-col gap-0.5 px-4 py-2">
              <div className="flex items-center justify-between gap-3"><span className="font-medium">{a.subject ?? titleCase(a.activity_type)}</span><span className="text-xs text-muted-foreground">{fmtDateTime(a.occurred_at)}</span></div>
              <div className="text-xs text-muted-foreground">{titleCase(a.activity_type)} · {a.direction}{a.body ? ` · ${a.body}` : ""}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function ContactDetailPage() {
  const { id = "" } = useParams()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const tab = (TABS.some((t) => t.key === params.get("tab")) ? params.get("tab") : "overview") as TabKey
  const contact = useQuery({ queryKey: ["contacts", id], queryFn: () => api.get<Contact>(`/contacts/${id}`), enabled: id.length > 0 })

  if (contact.isPending) return <div><PageHeader title="Contact" /><LoadingState /></div>
  if (contact.isError) return <div><PageHeader title="Contact" /><ErrorState error={contact.error} onRetry={() => void contact.refetch()} /></div>
  const c = contact.data
  const Icon = c.contact_type === "company" ? Building2 : Users

  return (
    <div>
      <BackLink to="/contacts" label="Contacts" />
      <PageHeader
        title={<span className="flex items-center gap-3"><Icon className="size-6 text-muted-foreground" aria-hidden />{c.display_name} <ContactStatusBadge status={c.status} /></span>}
        description={[c.job_title, c.contact_type !== "company" ? c.company_name : null, c.primary_email].filter(Boolean).join(" · ") || "No company or email on file"}
        actions={
          <>
            <EditButton entity="contact" id={c.id} mode="page" />
            <DeleteButton entity="contact" id={c.id} name={c.display_name} onDeleted={() => navigate("/contacts")} />
            <MoreMenu entity="contact" row={c as unknown as Record<string, unknown> & { id: string; status?: string }} />
          </>
        }
      >
        <LogActivityButtons contactId={c.id} contactName={c.display_name} />
      </PageHeader>
      <Tabs value={tab} onValueChange={(v) => setParams((prev) => { const next = new URLSearchParams(prev); if (v === "overview") next.delete("tab"); else next.set("tab", v); return next }, { replace: true })}>
        <TabsList aria-label="Contact sections">
          {TABS.map((t) => <TabsTrigger key={t.key} value={t.key} data-testid={`tab-${t.key}`}>{t.label}</TabsTrigger>)}
        </TabsList>
        <TabsContent value="overview"><Overview contact={c} /></TabsContent>
        <TabsContent value="passengers"><PassengersTab contact={c} /></TabsContent>
        <TabsContent value="documents"><DocumentsTab contact={c} /></TabsContent>
        <TabsContent value="activities"><ActivitiesTab contact={c} /></TabsContent>
        <TabsContent value="relationship"><RelationshipGraph entityType="contact" entityId={id} /></TabsContent>
      </Tabs>
    </div>
  )
}
